"""Disk-backed, same-country and source-separated raw blocking index."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from .normalize import normalize_raw
from .normalize import raw_tokens

INDEX_SCHEMA_VERSION = "phase1-raw-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _connect(path: Path, writable: bool) -> sqlite3.Connection:
    if writable:
        connection = sqlite3.connect(path)
        connection.executescript(
            "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; "
            "PRAGMA temp_store=FILE; PRAGMA cache_size=-262144;"
        )
    else:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA cache_size=-131072")
    return connection


def _create_shard(connection: sqlite3.Connection, number: int) -> None:
    records = f"records_{number}"
    fts = f"fts_{number}"
    connection.execute(
        f"CREATE TABLE {records} (entity_id TEXT NOT NULL, name TEXT NOT NULL, address TEXT NOT NULL)"
    )
    connection.execute(
        f"CREATE VIRTUAL TABLE {fts} USING fts5(name, address, "
        f"content='{records}', content_rowid='rowid', "
        "tokenize='unicode61 remove_diacritics 0')"
    )


def build_index(source_paths: tuple[Path, Path], output: Path) -> dict:
    """Build one SQLite shard per (country, source) without outside data."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    started = time.monotonic()
    connection = _connect(output, writable=True)
    connection.execute(
        "CREATE TABLE shards (shard_id INTEGER PRIMARY KEY, country TEXT NOT NULL, "
        "source TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0, UNIQUE(country, source))"
    )
    shard_ids: dict[tuple[str, str], int] = {}
    counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    inputs = []
    try:
        for source_number, path in enumerate(source_paths, start=2):
            source = f"S{source_number}"
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                if reader.fieldnames != ["entity_id", "business_name", "business_address", "country"]:
                    raise ValueError(f"unexpected source header in {path}: {reader.fieldnames}")
                buffers: defaultdict[int, list[tuple[str, str, str]]] = defaultdict(list)
                for row in reader:
                    key = (row["country"].strip(), source)
                    shard_id = shard_ids.get(key)
                    if shard_id is None:
                        cursor = connection.execute(
                            "INSERT INTO shards(country, source) VALUES (?, ?)", key
                        )
                        shard_id = int(cursor.lastrowid)
                        shard_ids[key] = shard_id
                        _create_shard(connection, shard_id)
                    buffers[shard_id].append(
                        (
                            row["entity_id"],
                            normalize_raw(row["business_name"]),
                            normalize_raw(row["business_address"]),
                        )
                    )
                    counts[key] += 1
                    if len(buffers[shard_id]) >= 10_000:
                        connection.executemany(
                            f"INSERT INTO records_{shard_id}(entity_id, name, address) VALUES (?, ?, ?)",
                            buffers[shard_id],
                        )
                        buffers[shard_id].clear()
                for shard_id, rows in buffers.items():
                    if rows:
                        connection.executemany(
                            f"INSERT INTO records_{shard_id}(entity_id, name, address) VALUES (?, ?, ?)", rows
                        )
                connection.commit()
            inputs.append({"path": str(path), "sha256": sha256_file(path)})

        for (country, source), shard_id in sorted(shard_ids.items()):
            records = f"records_{shard_id}"
            fts = f"fts_{shard_id}"
            connection.execute(f"CREATE INDEX {records}_name ON {records}(name)")
            connection.execute(f"CREATE INDEX {records}_address ON {records}(address)")
            connection.execute(f"INSERT INTO {fts}({fts}) VALUES ('rebuild')")
            connection.execute(
                f"CREATE VIRTUAL TABLE vocab_{shard_id} USING fts5vocab({fts}, 'row')"
            )
            connection.execute(
                "UPDATE shards SET row_count=? WHERE shard_id=?", (counts[(country, source)], shard_id)
            )
        connection.commit()
    finally:
        connection.close()
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "inputs": inputs,
        "shards": [
            {"country": country, "source": source, "rows": counts[(country, source)]}
            for country, source in sorted(counts)
        ],
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "index_bytes": output.stat().st_size,
    }


def write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class RawIndex:
    """Read-only query interface over a built index."""

    def __init__(self, path: Path):
        self.connection = _connect(path, writable=False)
        self.shards = {
            (country, source): (int(shard_id), int(row_count))
            for shard_id, country, source, row_count in self.connection.execute(
                "SELECT shard_id, country, source, row_count FROM shards"
            )
        }

    def close(self) -> None:
        self.connection.close()

    @lru_cache(maxsize=50_000)
    def exact(self, country: str, source: str, field: str, value: str, limit: int) -> tuple[str, ...]:
        if not value or field not in {"name", "address"}:
            return ()
        shard = self.shards.get((country, source))
        if shard is None:
            return ()
        shard_id, _ = shard
        rows = self.connection.execute(
            f"SELECT entity_id FROM records_{shard_id} WHERE {field}=? ORDER BY entity_id LIMIT ?",
            (value, limit),
        )
        return tuple(row[0] for row in rows)

    @lru_cache(maxsize=50_000)
    def rare(self, country: str, source: str, field: str, tokens: tuple[str, ...], limit: int) -> tuple[tuple[str, float], ...]:
        if not tokens or field not in {"name", "address"}:
            return ()
        shard = self.shards.get((country, source))
        if shard is None:
            return ()
        shard_id, _ = shard
        placeholders = ",".join("?" for _ in tokens)
        frequencies = self.connection.execute(
            f"SELECT term, doc FROM vocab_{shard_id} WHERE term IN ({placeholders})",
            tokens,
        )
        # Common terms are neither rare nor tractable blocking keys. Choose the
        # three rarest usable query tokens by measured shard document frequency.
        rare_tokens = [
            (term, document_count)
            for term, document_count in sorted(frequencies, key=lambda row: (row[1], row[0]))
            if document_count <= limit
        ][:3]
        if not rare_tokens:
            return ()
        fts = f"fts_{shard_id}"
        scored: defaultdict[str, float] = defaultdict(float)
        for token, document_count in rare_tokens:
            quoted = f'"{token.replace(chr(34), chr(34) * 2)}"'
            expression = f"{field} : {quoted}"
            rows = self.connection.execute(
                f"SELECT r.entity_id FROM {fts} "
                f"JOIN records_{shard_id} r ON r.rowid={fts}.rowid "
                f"WHERE {fts} MATCH ? LIMIT ?",
                (expression, limit),
            )
            weight = 1.0 / math.log2(document_count + 2.0)
            for entity_id, in rows:
                scored[entity_id] += weight
        return tuple(sorted(scored.items(), key=lambda pair: (-pair[1], pair[0])))

    @lru_cache(maxsize=50_000)
    def rare_fields(
        self,
        country: str,
        source: str,
        name_tokens: tuple[str, ...],
        address_tokens: tuple[str, ...],
        limit: int,
    ) -> tuple[tuple[str, str, float], ...]:
        """Retrieve both fields with one DF lookup and one FTS query per field."""
        shard = self.shards.get((country, source))
        all_tokens = tuple(dict.fromkeys(name_tokens + address_tokens))
        if shard is None or not all_tokens:
            return ()
        shard_id, _ = shard
        placeholders = ",".join("?" for _ in all_tokens)
        frequencies = {
            term: int(documents)
            for term, documents in self.connection.execute(
                f"SELECT term, doc FROM vocab_{shard_id} WHERE term IN ({placeholders})",
                all_tokens,
            )
        }
        fts = f"fts_{shard_id}"
        results: list[tuple[str, str, float]] = []
        for field, tokens in (("name", name_tokens), ("address", address_tokens)):
            chosen = sorted(
                (
                    (frequencies[token], token)
                    for token in tokens
                    if token in frequencies and frequencies[token] <= limit
                ),
                key=lambda item: (item[0], item[1]),
            )[:3]
            if not chosen:
                continue
            terms = [f'"{token.replace(chr(34), chr(34) * 2)}"' for _, token in chosen]
            expression = f"{field} : (" + " OR ".join(terms) + ")"
            rows = self.connection.execute(
                f"SELECT r.entity_id, r.{field} FROM {fts} "
                f"JOIN records_{shard_id} r ON r.rowid={fts}.rowid "
                f"WHERE {fts} MATCH ? LIMIT ?",
                (expression, sum(documents for documents, _ in chosen)),
            )
            weights = {token: 1.0 / math.log2(documents + 2.0) for documents, token in chosen}
            for entity_id, text in rows:
                target_tokens = set(raw_tokens(text))
                score = sum(weight for token, weight in weights.items() if token in target_tokens)
                results.append((entity_id, field, score))
        return tuple(results)

    def comparison_space(self, country_counts: dict[str, int]) -> int:
        target_counts: defaultdict[str, int] = defaultdict(int)
        for (country, _source), (_shard, rows) in self.shards.items():
            target_counts[country] += rows
        return sum(count * target_counts[country] for country, count in country_counts.items())
