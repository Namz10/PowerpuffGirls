"""Provisional Phase 2 canonical, cross-script, and rescue blocker.

This module intentionally lives beside the frozen Phase 1 raw blocker.  It
does not change ``phase1-raw-v1`` artifacts or write a phase gate.  All model
selection inputs are expected to come from the frozen ``loop`` split.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import resource
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from src.represent.country_rules import normalize_country
from src.represent.normalize_address import normalize_address
from src.represent.normalize_name import normalize_name

from .generate import CANDIDATE_HEADER, MISS_HEADER, MetricAccumulator
from .index import sha256_file
from .normalize import normalize_raw, raw_tokens


INDEX_SCHEMA_VERSION = "phase2-canonical-v1"
NORMALIZER_VERSION = "2.0.0"
_REPO_ROOT = Path(__file__).resolve().parents[2]
CAP_SWEEP = (10, 20, 30, 50, 75, 100)
RESCUE_QUOTA_SWEEP = (0, 2, 5, 10, 20)
RESCUE_CHANNELS = frozenset({"postal_exact", "romanized_ngram", "phonetic_exact"})
CHANNEL_ORDER = (
    "raw_name_exact",
    "raw_address_exact",
    "canonical_name_exact",
    "accent_name_exact",
    "canonical_address_exact",
    "romanized_exact",
    "raw_name_token",
    "raw_address_token",
    "canonical_name_token",
    "canonical_address_token",
    "romanized_token",
    "postal_exact",
    "romanized_ngram",
    "phonetic_exact",
)
CHANNEL_WEIGHTS = {
    "raw_name_exact": 9.0,
    "raw_address_exact": 8.0,
    "canonical_name_exact": 10.0,
    "accent_name_exact": 8.5,
    "canonical_address_exact": 9.0,
    "romanized_exact": 9.5,
    "raw_name_token": 3.0,
    "raw_address_token": 2.5,
    "canonical_name_token": 4.0,
    "canonical_address_token": 3.5,
    "romanized_token": 4.5,
    "postal_exact": 1.5,
    "romanized_ngram": 2.0,
    "phonetic_exact": 1.75,
}
RAW_CHANNELS = frozenset(channel for channel in CHANNEL_ORDER if channel.startswith("raw_"))
CANONICAL_CHANNELS = frozenset(CHANNEL_ORDER) - RAW_CHANNELS
PROVENANCE_HEADER = (
    "source1_entity_id",
    "candidate_entity_id",
    "target_source",
    "provenance",
    "rank",
    "retrieval_score",
    "strongest_channel",
    "target_script",
)


@dataclass(frozen=True)
class CanonicalView:
    entity_id: str
    country: str
    raw_name: str
    raw_address: str
    normalized_name: str
    romanized_name: str
    accent_name: str
    normalized_address: str
    postal_code: str
    source_script: str
    name_tokens: tuple[str, ...]
    address_tokens: tuple[str, ...]
    phonetic_name: str
    name_ngrams: tuple[str, ...]


@dataclass
class Phase2Evidence:
    source: str
    target_script: str = "latin"
    channels: set[str] = field(default_factory=set)
    retrieval_score: float = 0.0

    @property
    def provenance(self) -> str:
        return ",".join(channel for channel in CHANNEL_ORDER if channel in self.channels)

    @property
    def strongest_channel(self) -> str:
        return min(
            self.channels,
            key=lambda channel: (-CHANNEL_WEIGHTS[channel], CHANNEL_ORDER.index(channel)),
        )

    @property
    def rescue_only(self) -> bool:
        return bool(self.channels) and self.channels <= RESCUE_CHANNELS

    def rank_key(self, entity_id: str) -> tuple[float, float, int, float, str]:
        strongest = max(CHANNEL_WEIGHTS[channel] for channel in self.channels)
        total = sum(CHANNEL_WEIGHTS[channel] for channel in self.channels)
        return (-strongest, -total, -len(self.channels), -self.retrieval_score, entity_id)


def _encode_gram(gram: str) -> str:
    # Alphanumeric-only encoding stays a single unicode61 token in SQLite FTS.
    return "g" + "".join(f"{ord(character):06x}" for character in gram)


def character_ngrams(text: str, size: int = 3, limit: int = 48) -> tuple[str, ...]:
    """Return deterministic boundary-aware character n-grams."""
    grams: list[str] = []
    seen: set[str] = set()
    for token in text.split():
        padded = f"^{token}$"
        if len(padded) < size:
            candidates = (padded,)
        else:
            candidates = (padded[i : i + size] for i in range(len(padded) - size + 1))
        for raw_gram in candidates:
            gram = _encode_gram(raw_gram)
            if gram not in seen:
                seen.add(gram)
                grams.append(gram)
                if len(grams) >= limit:
                    return tuple(grams)
    return tuple(grams)


_PHONETIC_GROUP = {
    **dict.fromkeys("bfpv", "1"),
    **dict.fromkeys("cgjkqsxz", "2"),
    **dict.fromkeys("dt", "3"),
    **dict.fromkeys("l", "4"),
    **dict.fromkeys("mn", "5"),
    **dict.fromkeys("r", "6"),
}


def phonetic_token(token: str) -> str:
    """Conservative deterministic phonetic key for romanized name tokens."""
    letters = "".join(character for character in token.casefold() if "a" <= character <= "z")
    if not letters:
        return ""
    for before, after in (("ph", "f"), ("ck", "k"), ("sh", "s"), ("ch", "c"), ("th", "t")):
        letters = letters.replace(before, after)
    initial = {
        "c": "k", "q": "k", "j": "g", "b": "p", "v": "f", "w": "f",
        "d": "t", "z": "s", "x": "s",
    }.get(letters[0], letters[0])
    result = [initial]
    previous = _PHONETIC_GROUP.get(letters[0], "")
    for character in letters[1:]:
        code = _PHONETIC_GROUP.get(character, "")
        if code and code != previous:
            result.append(code)
        previous = code
    return "".join(result)[:8]


def phonetic_name(text: str) -> str:
    keys = [phonetic_token(token) for token in text.split()]
    # Business-name token order is frequently unstable across sources.
    return " ".join(sorted(set(key for key in keys if len(key) >= 2)))


def canonicalize(
    entity_id: str,
    raw_name: str,
    raw_address: str,
    raw_country: str,
) -> CanonicalView:
    country = normalize_country(raw_country)
    normalized_name, romanized, accent, script, name_tokens = normalize_name(raw_name)
    address, address_tokens, _empty, _landmark, _cedex, postal = normalize_address(
        raw_address, country
    )
    return CanonicalView(
        entity_id=entity_id,
        country=country,
        raw_name=normalize_raw(raw_name),
        raw_address=normalize_raw(raw_address),
        normalized_name=normalized_name,
        romanized_name=romanized,
        accent_name=accent,
        normalized_address=address,
        postal_code=postal or "",
        source_script=script,
        name_tokens=tuple(dict.fromkeys(name_tokens)),
        address_tokens=tuple(dict.fromkeys(address_tokens)),
        phonetic_name=phonetic_name(romanized),
        name_ngrams=character_ngrams(romanized),
    )


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


_RECORD_COLUMNS = (
    "entity_id",
    "raw_name",
    "raw_address",
    "normalized_name",
    "romanized_name",
    "accent_name",
    "normalized_address",
    "postal_code",
    "source_script",
    "phonetic_name",
    "name_ngrams",
)
_FTS_FIELDS = (
    "raw_name",
    "raw_address",
    "normalized_name",
    "romanized_name",
    "normalized_address",
    "name_ngrams",
)
_EXACT_FIELDS = frozenset(
    {
        "raw_name",
        "raw_address",
        "normalized_name",
        "romanized_name",
        "accent_name",
        "normalized_address",
        "postal_code",
        "phonetic_name",
    }
)


def _create_shard(connection: sqlite3.Connection, shard_id: int) -> None:
    columns = ", ".join(f"{column} TEXT NOT NULL" for column in _RECORD_COLUMNS)
    connection.execute(f"CREATE TABLE records_{shard_id} ({columns})")
    fts_columns = ", ".join(_FTS_FIELDS)
    connection.execute(
        f"CREATE VIRTUAL TABLE fts_{shard_id} USING fts5({fts_columns}, "
        f"content='records_{shard_id}', content_rowid='rowid', "
        "tokenize='unicode61 remove_diacritics 0')"
    )


def _source_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected = ["entity_id", "business_name", "business_address", "country"]
        if reader.fieldnames != expected:
            raise ValueError(f"unexpected source header in {path}: {reader.fieldnames}")
        yield from reader


def build_phase2_index(source_paths: tuple[Path, Path], output: Path) -> dict:
    """Build a source-separated canonical index directly from raw TSV inputs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    started = time.monotonic()
    connection = _connect(output, writable=True)
    connection.execute(
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)",
        (("schema_version", INDEX_SCHEMA_VERSION), ("normalizer_version", NORMALIZER_VERSION)),
    )
    connection.execute(
        "CREATE TABLE shards (shard_id INTEGER PRIMARY KEY, country TEXT NOT NULL, "
        "source TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0, UNIQUE(country, source))"
    )
    shard_ids: dict[tuple[str, str], int] = {}
    counts: Counter[tuple[str, str]] = Counter()
    inputs = []
    try:
        for source_number, path in enumerate(source_paths, start=2):
            source = f"S{source_number}"
            buffers: defaultdict[int, list[tuple[str, ...]]] = defaultdict(list)
            for row in _source_rows(path):
                item = canonicalize(
                    row["entity_id"], row["business_name"], row["business_address"], row["country"]
                )
                key = (item.country, source)
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
                        item.entity_id,
                        item.raw_name,
                        item.raw_address,
                        item.normalized_name,
                        item.romanized_name,
                        item.accent_name,
                        item.normalized_address,
                        item.postal_code,
                        item.source_script,
                        item.phonetic_name,
                        " ".join(item.name_ngrams),
                    )
                )
                counts[key] += 1
                if len(buffers[shard_id]) >= 10_000:
                    placeholders = ",".join("?" for _ in _RECORD_COLUMNS)
                    connection.executemany(
                        f"INSERT INTO records_{shard_id} VALUES ({placeholders})", buffers[shard_id]
                    )
                    buffers[shard_id].clear()
            for shard_id, rows in buffers.items():
                if rows:
                    placeholders = ",".join("?" for _ in _RECORD_COLUMNS)
                    connection.executemany(
                        f"INSERT INTO records_{shard_id} VALUES ({placeholders})", rows
                    )
            connection.commit()
            inputs.append({"path": str(path), "sha256": sha256_file(path)})

        for (country, source), shard_id in sorted(shard_ids.items()):
            for field_name in _EXACT_FIELDS | {"entity_id"}:
                connection.execute(
                    f"CREATE INDEX records_{shard_id}_{field_name} "
                    f"ON records_{shard_id}({field_name})"
                )
            connection.execute(f"INSERT INTO fts_{shard_id}(fts_{shard_id}) VALUES ('rebuild')")
            connection.execute(
                f"CREATE VIRTUAL TABLE vocab_{shard_id} USING fts5vocab(fts_{shard_id}, 'row')"
            )
            connection.execute(
                "UPDATE shards SET row_count=? WHERE shard_id=?", (counts[(country, source)], shard_id)
            )
        connection.commit()
    finally:
        connection.close()
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "inputs": inputs,
        "shards": [
            {"country": country, "source": source, "rows": counts[(country, source)]}
            for country, source in sorted(counts)
        ],
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "index_bytes": output.stat().st_size,
        "index_sha256": sha256_file(output),
        "implementation_sha256": {
            str(path.relative_to(_REPO_ROOT)): sha256_file(path)
            for path in (
                Path(__file__).resolve(),
                _REPO_ROOT / "src/represent/normalize_name.py",
                _REPO_ROOT / "src/represent/normalize_address.py",
                _REPO_ROOT / "src/represent/romanization.py",
                _REPO_ROOT / "src/represent/country_rules.py",
            )
        },
    }


class Phase2Index:
    def __init__(self, path: Path):
        self.path = path
        self.connection = _connect(path, writable=False)
        metadata = dict(self.connection.execute("SELECT key, value FROM metadata"))
        if metadata.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise ValueError(f"not a {INDEX_SCHEMA_VERSION} index: {path}")
        self.shards = {
            (country, source): (int(shard_id), int(rows))
            for shard_id, country, source, rows in self.connection.execute(
                "SELECT shard_id, country, source, row_count FROM shards"
            )
        }

    def close(self) -> None:
        self.connection.close()

    def comparison_space(self, country_counts: Mapping[str, int]) -> int:
        targets: Counter[str] = Counter()
        for (country, _source), (_shard_id, rows) in self.shards.items():
            targets[country] += rows
        return sum(count * targets[country] for country, count in country_counts.items())

    def exact(
        self, country: str, source: str, field_name: str, value: str, limit: int
    ) -> tuple[tuple[str, str], ...]:
        if not value or field_name not in _EXACT_FIELDS:
            return ()
        shard = self.shards.get((country, source))
        if shard is None:
            return ()
        shard_id, _rows = shard
        rows = self.connection.execute(
            f"SELECT entity_id, source_script FROM records_{shard_id} "
            f"WHERE {field_name}=? ORDER BY entity_id LIMIT ?",
            (value, limit),
        )
        return tuple(rows)

    def entity_script(self, country: str, entity_id: str) -> str:
        source = entity_id.split("-", 1)[0]
        shard = self.shards.get((country, source))
        if shard is None:
            return "unknown"
        shard_id, _rows = shard
        row = self.connection.execute(
            f"SELECT source_script FROM records_{shard_id} WHERE entity_id=?",
            (entity_id,),
        ).fetchone()
        return str(row[0]) if row else "unknown"

    def rare_tokens(
        self,
        country: str,
        source: str,
        field_name: str,
        tokens: Sequence[str],
        posting_limit: int,
        token_limit: int = 4,
    ) -> tuple[tuple[str, str, float], ...]:
        shard = self.shards.get((country, source))
        unique_tokens = tuple(dict.fromkeys(token for token in tokens if token))
        if shard is None or not unique_tokens or field_name not in _FTS_FIELDS:
            return ()
        shard_id, _rows = shard
        placeholders = ",".join("?" for _ in unique_tokens)
        frequencies = {
            term: int(documents)
            for term, documents in self.connection.execute(
                f"SELECT term, doc FROM vocab_{shard_id} WHERE term IN ({placeholders})",
                unique_tokens,
            )
        }
        chosen = sorted(
            (
                (documents, token)
                for token, documents in frequencies.items()
                if documents <= posting_limit
            ),
            key=lambda item: (item[0], item[1]),
        )[:token_limit]
        if not chosen:
            return ()
        terms = [f'"{token.replace(chr(34), chr(34) * 2)}"' for _, token in chosen]
        expression = f"{field_name} : (" + " OR ".join(terms) + ")"
        weights = {token: 1.0 / math.log2(documents + 2.0) for documents, token in chosen}
        result = []
        for entity_id, script, text in self.connection.execute(
            f"SELECT r.entity_id, r.source_script, r.{field_name} FROM fts_{shard_id} "
            f"JOIN records_{shard_id} r ON r.rowid=fts_{shard_id}.rowid "
            f"WHERE fts_{shard_id} MATCH ? LIMIT ?",
            (expression, sum(documents for documents, _ in chosen)),
        ):
            present = set(text.split())
            score = sum(weight for token, weight in weights.items() if token in present)
            result.append((entity_id, script, score))
        return tuple(sorted(result, key=lambda item: (-item[2], item[0])))


@dataclass(frozen=True)
class Phase2Config:
    cap: int = 50
    source_floor: int = 2
    rescue_quota: int = 10
    exact_pool: int = 250
    token_posting_limit: int = 250
    ngram_posting_limit: int = 400
    max_tokens_per_field: int = 4


def _add_exact(
    index: Phase2Index,
    query: CanonicalView,
    source: str,
    evidence: dict[str, Phase2Evidence],
    field_name: str,
    value: str,
    channel: str,
    limit: int,
) -> None:
    for entity_id, script in index.exact(query.country, source, field_name, value, limit):
        item = evidence.setdefault(entity_id, Phase2Evidence(source, script))
        item.channels.add(channel)


def _add_tokens(
    index: Phase2Index,
    query: CanonicalView,
    source: str,
    evidence: dict[str, Phase2Evidence],
    field_name: str,
    tokens: Sequence[str],
    channel: str,
    posting_limit: int,
    token_limit: int,
) -> None:
    for entity_id, script, score in index.rare_tokens(
        query.country, source, field_name, tokens, posting_limit, token_limit
    ):
        item = evidence.setdefault(entity_id, Phase2Evidence(source, script))
        item.channels.add(channel)
        item.retrieval_score += score


def retrieve_phase2(
    index: Phase2Index,
    query: CanonicalView,
    config: Phase2Config = Phase2Config(),
    boilerplate: frozenset[str] = frozenset(),
) -> list[tuple[str, Phase2Evidence]]:
    evidence: dict[str, Phase2Evidence] = {}
    exact_channels = (
        ("raw_name", query.raw_name, "raw_name_exact"),
        ("raw_address", query.raw_address, "raw_address_exact"),
        ("normalized_name", query.normalized_name, "canonical_name_exact"),
        ("accent_name", query.accent_name, "accent_name_exact"),
        ("normalized_address", query.normalized_address, "canonical_address_exact"),
        ("romanized_name", query.romanized_name, "romanized_exact"),
        ("postal_code", query.postal_code, "postal_exact"),
        ("phonetic_name", query.phonetic_name, "phonetic_exact"),
    )
    token_channels = (
        ("raw_name", raw_tokens(query.raw_name), "raw_name_token", config.token_posting_limit),
        ("raw_address", raw_tokens(query.raw_address), "raw_address_token", config.token_posting_limit),
        ("normalized_name", query.name_tokens, "canonical_name_token", config.token_posting_limit),
        (
            "normalized_address",
            query.address_tokens,
            "canonical_address_token",
            config.token_posting_limit,
        ),
        ("romanized_name", tuple(query.romanized_name.split()), "romanized_token", config.token_posting_limit),
        ("name_ngrams", query.name_ngrams, "romanized_ngram", config.ngram_posting_limit),
    )
    for source in ("S2", "S3"):
        for field_name, value, channel in exact_channels:
            _add_exact(
                index, query, source, evidence, field_name, value, channel, config.exact_pool
            )
        for field_name, tokens, channel, posting_limit in token_channels:
            filtered_tokens = (
                tokens
                if channel == "romanized_ngram"
                else tuple(token for token in tokens if token not in boilerplate)
            )
            _add_tokens(
                index,
                query,
                source,
                evidence,
                field_name,
                filtered_tokens,
                channel,
                posting_limit,
                config.max_tokens_per_field,
            )
    return sorted(evidence.items(), key=lambda pair: pair[1].rank_key(pair[0]))


def _filtered_evidence(
    ranked: Sequence[tuple[str, Phase2Evidence]], channels: frozenset[str]
) -> list[tuple[str, Phase2Evidence]]:
    result = []
    for entity_id, evidence in ranked:
        overlap = evidence.channels & channels
        if overlap:
            result.append(
                (
                    entity_id,
                    Phase2Evidence(
                        evidence.source,
                        evidence.target_script,
                        set(overlap),
                        evidence.retrieval_score,
                    ),
                )
            )
    return sorted(result, key=lambda pair: pair[1].rank_key(pair[0]))


def select_phase2(
    ranked: Sequence[tuple[str, Phase2Evidence]], config: Phase2Config
) -> list[tuple[str, Phase2Evidence]]:
    if config.cap < 0 or config.source_floor < 0 or config.rescue_quota < 0:
        raise ValueError("cap, source floor, and rescue quota must be non-negative")
    selected: list[tuple[str, Phase2Evidence]] = []
    selected_ids: set[str] = set()
    rescue_count = 0

    def add(item: tuple[str, Phase2Evidence]) -> bool:
        nonlocal rescue_count
        entity_id, evidence = item
        if entity_id in selected_ids or len(selected) >= config.cap:
            return False
        if evidence.rescue_only and rescue_count >= config.rescue_quota:
            return False
        selected.append(item)
        selected_ids.add(entity_id)
        rescue_count += int(evidence.rescue_only)
        return True

    if config.source_floor:
        for source in ("S2", "S3"):
            source_count = 0
            for item in ranked:
                if item[1].source == source and add(item):
                    source_count += 1
                    if source_count >= config.source_floor:
                        break
    for item in ranked:
        add(item)
        if len(selected) >= config.cap:
            break
    return sorted(selected, key=lambda pair: pair[1].rank_key(pair[0]))


def paired_bootstrap_delta(
    incumbent: Sequence[float],
    challenger: Sequence[float],
    resamples: int = 2000,
    seed: int = 42,
) -> dict[str, float | int]:
    """Paired entity bootstrap with a deterministic percentile interval."""
    if len(incumbent) != len(challenger) or not incumbent:
        raise ValueError("paired non-empty samples must have equal length")
    if resamples < 2000:
        raise ValueError("the selection protocol requires at least 2,000 resamples")
    differences = [new - old for old, new in zip(incumbent, challenger)]
    rng = random.Random(seed)
    size = len(differences)
    sampled = []
    for _ in range(resamples):
        sampled.append(sum(differences[rng.randrange(size)] for _ in range(size)) / size)
    sampled.sort()
    lower = sampled[math.floor(0.025 * (resamples - 1))]
    upper = sampled[math.ceil(0.975 * (resamples - 1))]
    delta = sum(differences) / size
    return {
        "delta": delta,
        "ci95_lower": lower,
        "ci95_upper": upper,
        "resamples": resamples,
        "seed": seed,
        "promote": lower > 0.0,
    }


def pareto_frontier(points: Sequence[Mapping[str, float | int]]) -> list[dict[str, float | int]]:
    """Keep points not dominated on recall (high) and mean width (low)."""
    frontier = []
    for point in points:
        dominated = any(
            other is not point
            and float(other["link_recall"]) >= float(point["link_recall"])
            and float(other["mean_width"]) <= float(point["mean_width"])
            and (
                float(other["link_recall"]) > float(point["link_recall"])
                or float(other["mean_width"]) < float(point["mean_width"])
            )
            for other in points
        )
        if not dominated:
            frontier.append(dict(point))
    return sorted(frontier, key=lambda item: (float(item["mean_width"]), -float(item["link_recall"])))


def _entity_recall(ids: Sequence[str], truth: set[str]) -> float:
    return len(set(ids) & truth) / len(truth) if truth else 1.0


def _mapping_sha256(mapping: Mapping[str, set[str]]) -> str:
    digest = hashlib.sha256()
    for entity_id in sorted(mapping):
        digest.update(entity_id.encode("utf-8"))
        digest.update(b"\t")
        digest.update(",".join(sorted(mapping[entity_id])).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ids_sha256(ids: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for entity_id in sorted(ids):
        digest.update(entity_id.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_boilerplate(resource_path: Path | None) -> tuple[dict[str, frozenset[str]], str | None]:
    if resource_path is None:
        return {}, None
    path = resource_path / "boilerplate_tokens.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {country: frozenset(tokens) for country, tokens in raw.items()}, sha256_file(path)


def generate_phase2(
    index_path: Path,
    source1_path: Path,
    output_path: Path,
    config: Phase2Config = Phase2Config(),
    requested_ids: set[str] | None = None,
    truth: Mapping[str, set[str]] | None = None,
    provenance_path: Path | None = None,
    misses_path: Path | None = None,
    sweep_caps: Iterable[int] = CAP_SWEEP,
    sweep_quotas: Iterable[int] = RESCUE_QUOTA_SWEEP,
    resource_path: Path | None = None,
) -> dict:
    """Stream union candidates and produce a leakage-safe diagnostic report."""
    started = time.monotonic()
    index = Phase2Index(index_path)
    boilerplate_by_country, boilerplate_sha256 = _load_boilerplate(resource_path)
    if truth is not None and requested_ids is None:
        raise ValueError("truth requires an explicit frozen requested-id set")
    if truth is not None and set(truth) != requested_ids:
        raise ValueError("truth must exactly cover the frozen requested Source 1 ids")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_handle = None
    misses_handle = None
    if provenance_path:
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_handle = provenance_path.open("w", encoding="utf-8", newline="")
        provenance_writer = csv.writer(provenance_handle, delimiter="\t", lineterminator="\n")
        provenance_writer.writerow(PROVENANCE_HEADER)
    else:
        provenance_writer = None
    if misses_path:
        if truth is None:
            raise ValueError("miss output requires truth")
        misses_path.parent.mkdir(parents=True, exist_ok=True)
        misses_handle = misses_path.open("w", encoding="utf-8", newline="")
        misses_writer = csv.writer(misses_handle, delimiter="\t", lineterminator="\n")
        misses_writer.writerow(MISS_HEADER)
    else:
        misses_writer = None

    country_counts: Counter[str] = Counter()
    remaining_ids = set(requested_ids) if requested_ids is not None else None
    source_order_ids = hashlib.sha256()
    entity_count = 0
    comparison_space = 0
    variants = {
        "raw_only": MetricAccumulator(),
        "canonical_only": MetricAccumulator(),
        "union": MetricAccumulator(),
    }
    cap_metrics = {cap: MetricAccumulator() for cap in sweep_caps}
    quota_metrics = {quota: MetricAccumulator() for quota in sweep_quotas}
    surface_metrics = {
        (cap, quota): MetricAccumulator()
        for cap in cap_metrics
        for quota in quota_metrics
    }
    channel_truth: Counter[str] = Counter()
    channel_pairs: Counter[str] = Counter()
    channel_incremental: Counter[str] = Counter()
    script_totals: Counter[str] = Counter()
    script_hits: Counter[str] = Counter()
    script_raw_hits: Counter[str] = Counter()
    country_entities: Counter[str] = Counter()
    country_truth: Counter[str] = Counter()
    country_hits: Counter[str] = Counter()
    country_raw_hits: Counter[str] = Counter()
    country_pairs: Counter[str] = Counter()
    cardinality_entities: Counter[str] = Counter()
    cardinality_complete: Counter[str] = Counter()
    cardinality_pairs: Counter[str] = Counter()
    raw_entity_scores: list[float] = []
    union_entity_scores: list[float] = []

    try:
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output, delimiter="\t", lineterminator="\n")
            writer.writerow(CANDIDATE_HEADER)
            for row in _source_rows(source1_path):
                entity_id = row["entity_id"]
                if requested_ids is not None and entity_id not in requested_ids:
                    continue
                if remaining_ids is not None:
                    if entity_id not in remaining_ids:
                        raise ValueError(f"duplicate requested Source 1 id: {entity_id}")
                    remaining_ids.remove(entity_id)
                query = canonicalize(
                    entity_id, row["business_name"], row["business_address"], row["country"]
                )
                entity_count += 1
                country_counts[query.country] += 1
                source_order_ids.update(f"{query.entity_id}\n".encode("utf-8"))
                boilerplate = boilerplate_by_country.get(
                    query.country, boilerplate_by_country.get("global", frozenset())
                )
                ranked = retrieve_phase2(index, query, config, boilerplate)
                selected = select_phase2(ranked, config)
                ids = [entity_id for entity_id, _ in selected]
                writer.writerow((query.entity_id, ",".join(ids)))
                if provenance_writer:
                    for rank, (entity_id, evidence) in enumerate(selected, start=1):
                        provenance_writer.writerow(
                            (
                                query.entity_id,
                                entity_id,
                                evidence.source,
                                evidence.provenance,
                                rank,
                                f"{evidence.retrieval_score:.9f}",
                                evidence.strongest_channel,
                                evidence.target_script,
                            )
                        )
                if truth is None:
                    continue
                truth_ids = truth[query.entity_id]
                raw_ranked = _filtered_evidence(ranked, RAW_CHANNELS)
                canonical_ranked = _filtered_evidence(ranked, CANONICAL_CHANNELS)
                raw_ids = [item[0] for item in select_phase2(raw_ranked, config)]
                canonical_ids = [item[0] for item in select_phase2(canonical_ranked, config)]
                variants["raw_only"].add(raw_ids, truth_ids)
                variants["canonical_only"].add(canonical_ids, truth_ids)
                variants["union"].add(ids, truth_ids)
                if truth_ids:
                    raw_entity_scores.append(_entity_recall(raw_ids, truth_ids))
                    union_entity_scores.append(_entity_recall(ids, truth_ids))
                for cap, accumulator in cap_metrics.items():
                    swept = select_phase2(ranked, Phase2Config(**{**config.__dict__, "cap": cap}))
                    accumulator.add([item[0] for item in swept], truth_ids)
                for quota, accumulator in quota_metrics.items():
                    swept = select_phase2(
                        ranked, Phase2Config(**{**config.__dict__, "rescue_quota": quota})
                    )
                    accumulator.add([item[0] for item in swept], truth_ids)
                for (cap, quota), accumulator in surface_metrics.items():
                    swept = select_phase2(
                        ranked,
                        Phase2Config(
                            **{**config.__dict__, "cap": cap, "rescue_quota": quota}
                        ),
                    )
                    accumulator.add([item[0] for item in swept], truth_ids)

                recovered_so_far: set[str] = set()
                for channel in CHANNEL_ORDER:
                    channel_ids = {
                        entity_id for entity_id, evidence in ranked if channel in evidence.channels
                    }
                    channel_pairs[channel] += len(channel_ids)
                    hits = channel_ids & truth_ids
                    channel_truth[channel] += len(hits)
                    channel_incremental[channel] += len(hits - recovered_so_far)
                    recovered_so_far |= hits
                raw_id_set = set(raw_ids)
                selected_id_set = set(ids)
                for truth_id in truth_ids:
                    script = index.entity_script(query.country, truth_id)
                    script_totals[script] += 1
                    script_hits[script] += int(truth_id in selected_id_set)
                    script_raw_hits[script] += int(truth_id in raw_id_set)

                country_entities[query.country] += 1
                country_truth[query.country] += len(truth_ids)
                country_hits[query.country] += len(selected_id_set & truth_ids)
                country_raw_hits[query.country] += len(raw_id_set & truth_ids)
                country_pairs[query.country] += len(ids)
                cardinality = "empty" if not truth_ids else ("singleton" if len(truth_ids) == 1 else "multi")
                cardinality_entities[cardinality] += 1
                cardinality_complete[cardinality] += int(truth_ids <= selected_id_set)
                cardinality_pairs[cardinality] += len(ids)

                if misses_writer:
                    missed = truth_ids - set(ids)
                    status = "complete" if not missed else "miss"
                    reason = "" if not missed else (
                        "cap_or_quota" if missed <= {item[0] for item in ranked} else "no_retrieval_evidence"
                    )
                    misses_writer.writerow(
                        (
                            query.entity_id,
                            ",".join(sorted(truth_ids)),
                            ",".join(ids),
                            ",".join(sorted(missed)),
                            status,
                            reason,
                        )
                    )
            if remaining_ids:
                raise ValueError(
                    f"requested Source 1 ids are not fully covered ({len(remaining_ids)} missing)"
                )
            comparison_space = index.comparison_space(country_counts)
    finally:
        index.close()
        if provenance_handle:
            provenance_handle.close()
        if misses_handle:
            misses_handle.close()

    report: dict[str, object] = {
        "provisional": True,
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "config": config.__dict__,
        "config_sha256": _json_sha256(config.__dict__),
        "candidate_file": str(output_path),
        "candidate_file_sha256": sha256_file(output_path),
        "index_file": str(index_path),
        "index_sha256": sha256_file(index_path),
        "source1_file": str(source1_path),
        "source1_sha256": sha256_file(source1_path),
        "requested_ids_sha256": (
            _ids_sha256(requested_ids)
            if requested_ids is not None
            else source_order_ids.hexdigest()
        ),
        "requested_ids_hash_order": "sorted" if requested_ids is not None else "source1",
        "truth_sha256": _mapping_sha256(truth) if truth is not None else None,
        "boilerplate_sha256": boilerplate_sha256,
        "provenance_sha256": sha256_file(provenance_path) if provenance_path else None,
        "misses_sha256": sha256_file(misses_path) if misses_path else None,
        "entities": entity_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    if truth is not None:
        variant_reports = {
            name: accumulator.finish(comparison_space) for name, accumulator in variants.items()
        }
        cap_reports = {
            str(cap): accumulator.finish(comparison_space) for cap, accumulator in cap_metrics.items()
        }
        quota_reports = {
            str(quota): accumulator.finish(comparison_space)
            for quota, accumulator in quota_metrics.items()
        }
        surface_reports = {
            f"cap={cap},rescue_quota={quota}": accumulator.finish(comparison_space)
            for (cap, quota), accumulator in surface_metrics.items()
        }
        points = [
            {
                "cap": cap,
                "rescue_quota": quota,
                "link_recall": surface_reports[
                    f"cap={cap},rescue_quota={quota}"
                ]["link_recall"],
                "mean_width": surface_reports[
                    f"cap={cap},rescue_quota={quota}"
                ]["candidate_width"]["mean"],
            }
            for cap, quota in surface_metrics
        ]
        frontier = pareto_frontier(points)
        bootstrap = (
            paired_bootstrap_delta(raw_entity_scores, union_entity_scores)
            if raw_entity_scores
            else None
        )
        selected_point_supported = any(
            point["cap"] == config.cap and point["rescue_quota"] == config.rescue_quota
            for point in frontier
        )
        report.update(
            {
                "variants": variant_reports,
                "cap_sweep": cap_reports,
                "rescue_quota_sweep": quota_reports,
                "selection_surface": surface_reports,
                "pareto_frontier": frontier,
                "raw_to_union_bootstrap": bootstrap,
                "promotion_check": {
                    "selected_point_on_pareto_frontier": selected_point_supported,
                    "bootstrap_lower_bound_above_zero": bool(
                        bootstrap and bootstrap["promote"]
                    ),
                    "eligible": bool(
                        selected_point_supported and bootstrap and bootstrap["promote"]
                    ),
                },
                "channels": {
                    channel: {
                        "candidate_pairs": channel_pairs[channel],
                        "recovered_truth_links": channel_truth[channel],
                        "incremental_truth_links": channel_incremental[channel],
                    }
                    for channel in CHANNEL_ORDER
                },
                "script_slices": {
                    script: {
                        "truth_links": count,
                        "recovered_truth_links": script_hits[script],
                        "link_recall": script_hits[script] / count if count else 1.0,
                        "raw_recovered_truth_links": script_raw_hits[script],
                        "raw_link_recall": script_raw_hits[script] / count if count else 1.0,
                        "union_minus_raw_recall": (
                            (script_hits[script] - script_raw_hits[script]) / count if count else 0.0
                        ),
                    }
                    for script, count in sorted(script_totals.items())
                },
                "country_slices": {
                    country: {
                        "entities": entities,
                        "truth_links": country_truth[country],
                        "recovered_truth_links": country_hits[country],
                        "link_recall": (
                            country_hits[country] / country_truth[country]
                            if country_truth[country] else 1.0
                        ),
                        "raw_link_recall": (
                            country_raw_hits[country] / country_truth[country]
                            if country_truth[country] else 1.0
                        ),
                        "mean_width": country_pairs[country] / entities,
                    }
                    for country, entities in sorted(country_entities.items())
                },
                "truth_cardinality_slices": {
                    cardinality: {
                        "entities": entities,
                        "complete_entities": cardinality_complete[cardinality],
                        "complete_entity_recall": cardinality_complete[cardinality] / entities,
                        "mean_width": cardinality_pairs[cardinality] / entities,
                    }
                    for cardinality, entities in sorted(cardinality_entities.items())
                },
            }
        )
    return report


def load_truth(path: Path, requested_ids: set[str]) -> dict[str, set[str]]:
    result = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row["source1_entity_id"] in requested_ids:
                result[row["source1_entity_id"]] = set(
                    filter(None, row["matched_entity_ids"].split(","))
                )
    if set(result) != requested_ids:
        raise ValueError("truth does not exactly cover requested ids")
    return result


def write_json(value: Mapping[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
