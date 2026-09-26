"""Optional bounded semantic retrieval for the CPU-first Phase 2 blocker.

The lexical blocker remains the default and has no ML dependency.  This module
is imported only by explicit semantic CLI commands.  Target embeddings are
written to SQLite batch by batch and retrieved through deterministic random-
hyperplane buckets, so neither indexing nor querying materializes all pairs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import resource
import sqlite3
import time
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterator, Protocol, Sequence

from .generate import CANDIDATE_HEADER, load_requested_ids
from .index import sha256_file
from .phase2 import CanonicalView, _source_rows, canonicalize


SEMANTIC_SCHEMA_VERSION = "phase2-semantic-lsh-v1"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEMANTIC_PROVENANCE_HEADER = (
    "source1_entity_id",
    "candidate_entity_id",
    "target_source",
    "semantic_score",
    "semantic_rank",
)


class Encoder(Protocol):
    model_name: str
    dimension: int
    device: str

    def encode(self, texts: Sequence[str], batch_size: int): ...


@dataclass(frozen=True)
class SemanticConfig:
    device: str = "cpu"
    batch_size: int = 64
    top_k: int = 10
    union_cap: int = 60
    max_pool_per_source: int = 2_000
    lsh_bits: int = 16
    probe_radius: int = 1
    lsh_seed: int = 42

    def validate(self) -> None:
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")
        for name in ("batch_size", "top_k", "union_cap", "max_pool_per_source", "lsh_bits"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.lsh_bits > 62:
            raise ValueError("lsh_bits must be at most 62 for SQLite INTEGER signatures")
        if self.probe_radius not in {0, 1, 2}:
            raise ValueError("probe_radius must be 0, 1, or 2")


@dataclass(frozen=True)
class SemanticHit:
    entity_id: str
    source: str
    score: float


class SentenceTransformerEncoder:
    """Lazy SentenceTransformers wrapper; construction is the dependency boundary."""

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu"):
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "semantic retrieval requires PyTorch and sentence-transformers; "
                "install src/blocking/requirements-semantic.txt"
            ) from error
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested but torch.cuda.is_available() is false")
        self.model_name = model_name
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)
        dimension = self.model.get_sentence_embedding_dimension()
        if not dimension:
            raise ValueError("the sentence-transformer did not report an embedding dimension")
        self.dimension = int(dimension)

    def encode(self, texts: Sequence[str], batch_size: int):
        return self.model.encode(
            list(texts),
            batch_size=batch_size,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )


def semantic_text(item: CanonicalView) -> str:
    """Model input contains only normalized names and addresses."""
    parts = []
    if item.normalized_name:
        parts.append(f"name: {item.normalized_name}")
    if item.normalized_address:
        parts.append(f"address: {item.normalized_address}")
    return " ; ".join(parts)


def _torch():
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("semantic retrieval requires PyTorch") from error
    return torch


def _planes(dimension: int, bits: int, seed: int, device: str):
    torch = _torch()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    planes = torch.randn((bits, dimension), generator=generator, dtype=torch.float32)
    planes = torch.nn.functional.normalize(planes, p=2, dim=1)
    return planes.to(device)


def _signatures(vectors, planes) -> list[int]:
    signs = (vectors.to(planes.device) @ planes.T) >= 0
    result = []
    for row in signs.detach().cpu().tolist():
        signature = 0
        for bit, enabled in enumerate(row):
            signature |= int(enabled) << bit
        result.append(signature)
    return result


def _probe_signatures(signature: int, bits: int, radius: int) -> tuple[int, ...]:
    values = {signature}
    for distance in range(1, radius + 1):
        for positions in combinations(range(bits), distance):
            candidate = signature
            for position in positions:
                candidate ^= 1 << position
            values.add(candidate)
    return tuple(sorted(values))


def _connect(path: Path, writable: bool) -> sqlite3.Connection:
    if writable:
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_vectors(vectors, expected_rows: int, dimension: int):
    torch = _torch()
    if not isinstance(vectors, torch.Tensor):
        vectors = torch.as_tensor(vectors, dtype=torch.float32)
    vectors = vectors.detach().to(dtype=torch.float32)
    if vectors.ndim != 2 or vectors.shape != (expected_rows, dimension):
        raise ValueError(
            f"encoder returned shape {tuple(vectors.shape)}, expected {(expected_rows, dimension)}"
        )
    return torch.nn.functional.normalize(vectors, p=2, dim=1)


def build_semantic_index(
    source_paths: tuple[Path, Path],
    output: Path,
    manifest_path: Path,
    config: SemanticConfig,
    model_name: str = DEFAULT_MODEL,
    encoder: Encoder | None = None,
) -> dict:
    """Stream target records through the encoder and append each batch to SQLite."""
    config.validate()
    encoder = encoder or SentenceTransformerEncoder(model_name, config.device)
    if encoder.device != config.device:
        raise ValueError("encoder device does not match semantic config")
    output.parent.mkdir(parents=True, exist_ok=True)
    for path in (output, Path(f"{output}-wal"), Path(f"{output}-shm")):
        if path.exists():
            path.unlink()
    started = time.monotonic()
    connection = _connect(output, writable=True)
    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE lsh_planes (id INTEGER PRIMARY KEY CHECK(id=1), data BLOB NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE records (country TEXT NOT NULL, source TEXT NOT NULL, "
        "signature INTEGER NOT NULL, entity_id TEXT NOT NULL, embedding BLOB NOT NULL, "
        "PRIMARY KEY(country, source, entity_id))"
    )
    planes = _planes(encoder.dimension, config.lsh_bits, config.lsh_seed, config.device)
    counts: dict[str, int] = {"S2": 0, "S3": 0}
    inputs = []
    pending_batches = 0

    def flush(rows: list[tuple[str, str, str, str]]) -> None:
        nonlocal pending_batches
        if not rows:
            return
        texts = [row[3] for row in rows]
        vectors = _prepare_vectors(
            encoder.encode(texts, config.batch_size), len(rows), encoder.dimension
        )
        signatures = _signatures(vectors, planes)
        host = vectors.detach().cpu().contiguous().numpy().astype("<f4", copy=False)
        connection.executemany(
            "INSERT INTO records(country, source, signature, entity_id, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (country, source, signature, entity_id, memoryview(host[index]).tobytes())
                for index, ((country, source, entity_id, _text), signature) in enumerate(
                    zip(rows, signatures)
                )
            ),
        )
        pending_batches += 1
        # Keep memory bounded while avoiding one SQLite fsync per GPU batch.
        if pending_batches >= 100:
            connection.commit()
            pending_batches = 0

    try:
        for source_number, path in enumerate(source_paths, start=2):
            source = f"S{source_number}"
            batch: list[tuple[str, str, str, str]] = []
            for row in _source_rows(path):
                item = canonicalize(
                    row["entity_id"], row["business_name"], row["business_address"], row["country"]
                )
                text = semantic_text(item)
                if not text:
                    continue
                batch.append((item.country, source, item.entity_id, text))
                counts[source] += 1
                if len(batch) >= config.batch_size:
                    flush(batch)
                    batch.clear()
            flush(batch)
            connection.commit()
            pending_batches = 0
            inputs.append({"path": str(path), "sha256": sha256_file(path)})
        connection.execute(
            "CREATE INDEX records_lookup ON records(country, source, signature, entity_id)"
        )
        metadata = {
            "schema_version": SEMANTIC_SCHEMA_VERSION,
            "model_name": encoder.model_name,
            "dimension": encoder.dimension,
            "lsh_bits": config.lsh_bits,
            "lsh_seed": config.lsh_seed,
        }
        plane_bytes = (
            planes.detach().cpu().contiguous().numpy().astype("<f4", copy=False).tobytes()
        )
        connection.execute("INSERT INTO lsh_planes(id, data) VALUES (1, ?)", (plane_bytes,))
        metadata["lsh_planes_sha256"] = hashlib.sha256(plane_bytes).hexdigest()
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            ((key, str(value)) for key, value in metadata.items()),
        )
        connection.commit()
    finally:
        connection.close()
    manifest = {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "model_name": encoder.model_name,
        "dimension": encoder.dimension,
        "device_used_for_build": config.device,
        "batch_size": config.batch_size,
        "lsh_bits": config.lsh_bits,
        "lsh_seed": config.lsh_seed,
        "lsh_planes_sha256": metadata["lsh_planes_sha256"],
        "rows": counts,
        "inputs": inputs,
        "index_path": str(output),
        "index_bytes": output.stat().st_size,
        "index_sha256": sha256_file(output),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    _write_json(manifest_path, manifest)
    return manifest


class SemanticIndex:
    def __init__(self, path: Path, device: str):
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'")
        torch = _torch()
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested but torch.cuda.is_available() is false")
        self.path = path
        self.device = device
        self.connection = _connect(path, writable=False)
        metadata = dict(self.connection.execute("SELECT key, value FROM metadata"))
        if metadata.get("schema_version") != SEMANTIC_SCHEMA_VERSION:
            self.connection.close()
            raise ValueError(f"not a {SEMANTIC_SCHEMA_VERSION} index: {path}")
        self.model_name = metadata["model_name"]
        self.dimension = int(metadata["dimension"])
        self.lsh_bits = int(metadata["lsh_bits"])
        self.lsh_seed = int(metadata["lsh_seed"])
        plane_bytes = self.connection.execute(
            "SELECT data FROM lsh_planes WHERE id=1"
        ).fetchone()[0]
        if hashlib.sha256(plane_bytes).hexdigest() != metadata["lsh_planes_sha256"]:
            self.connection.close()
            raise ValueError("semantic index LSH planes fail their stored fingerprint")
        import numpy as np

        plane_values = np.frombuffer(plane_bytes, dtype="<f4").astype(np.float32, copy=True)
        plane_values = plane_values.reshape(self.lsh_bits, self.dimension)
        self.planes = torch.from_numpy(plane_values).to(device)

    def close(self) -> None:
        self.connection.close()

    def search(
        self,
        query_vector,
        country: str,
        top_k: int,
        max_pool_per_source: int,
        probe_radius: int,
    ) -> list[SemanticHit]:
        torch = _torch()
        query = _prepare_vectors(query_vector.reshape(1, -1), 1, self.dimension)[0]
        signature = _signatures(query.reshape(1, -1), self.planes)[0]
        probes = _probe_signatures(signature, self.lsh_bits, probe_radius)
        placeholders = ",".join("?" for _ in probes)
        candidates: list[tuple[str, str, bytes]] = []
        for source in ("S2", "S3"):
            candidates.extend(
                self.connection.execute(
                    "SELECT entity_id, source, embedding FROM records "
                    f"WHERE country=? AND source=? AND signature IN ({placeholders}) "
                    "ORDER BY entity_id LIMIT ?",
                    (country, source, *probes, max_pool_per_source),
                )
            )
        if not candidates:
            return []
        import numpy as np

        matrix = np.frombuffer(
            b"".join(row[2] for row in candidates), dtype="<f4"
        ).astype(np.float32, copy=True)
        matrix = matrix.reshape(len(candidates), self.dimension)
        target = torch.from_numpy(matrix).to(self.device)
        scores = (target @ query.to(self.device)).detach().cpu().tolist()
        hits = [
            SemanticHit(entity_id, source, float(score))
            for (entity_id, source, _embedding), score in zip(candidates, scores)
        ]
        return sorted(hits, key=lambda hit: (-hit.score, hit.entity_id))[:top_k]


def _candidate_rows(path: Path) -> Iterator[tuple[str, list[str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header != list(CANDIDATE_HEADER):
            raise ValueError(f"unexpected candidate header: {header}")
        for row in reader:
            if len(row) != 2:
                raise ValueError(f"malformed candidate row for {row[0] if row else '<empty>'}")
            yield row[0], [value for value in row[1].split(",") if value]


def union_semantic_candidates(
    semantic_index_path: Path,
    source1_path: Path,
    lexical_path: Path,
    output_path: Path,
    report_path: Path,
    config: SemanticConfig,
    ids_path: Path | None = None,
    provenance_path: Path | None = None,
    model_name: str | None = None,
    encoder: Encoder | None = None,
) -> dict:
    """Stream lexical rows, union bounded semantic top-K, and preserve lexical order."""
    config.validate()
    started = time.monotonic()
    index = SemanticIndex(semantic_index_path, config.device)
    if config.lsh_bits != index.lsh_bits or config.lsh_seed != index.lsh_seed:
        index.close()
        raise ValueError("semantic query LSH configuration does not match the index")
    expected_model = model_name or index.model_name
    encoder = encoder or SentenceTransformerEncoder(expected_model, config.device)
    if encoder.device != config.device:
        index.close()
        raise ValueError("encoder device does not match semantic config")
    if encoder.model_name != index.model_name or encoder.dimension != index.dimension:
        index.close()
        raise ValueError("query encoder does not match the semantic index")
    requested = load_requested_ids(ids_path) if ids_path else None
    candidates = _candidate_rows(lexical_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_handle = None
    entities = 0
    lexical_pairs = 0
    semantic_pairs = 0
    added_pairs = 0

    def source_items() -> Iterator[CanonicalView]:
        for row in _source_rows(source1_path):
            if requested is None or row["entity_id"] in requested:
                yield canonicalize(
                    row["entity_id"], row["business_name"], row["business_address"], row["country"]
                )

    try:
        if provenance_path:
            provenance_path.parent.mkdir(parents=True, exist_ok=True)
            provenance_handle = provenance_path.open("w", encoding="utf-8", newline="")
            provenance_writer = csv.writer(
                provenance_handle, delimiter="\t", lineterminator="\n"
            )
            provenance_writer.writerow(SEMANTIC_PROVENANCE_HEADER)
        else:
            provenance_writer = None
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output, delimiter="\t", lineterminator="\n")
            writer.writerow(CANDIDATE_HEADER)
            item_iter = source_items()
            while True:
                batch_items: list[CanonicalView] = []
                batch_lexical: list[list[str]] = []
                for _ in range(config.batch_size):
                    try:
                        item = next(item_iter)
                    except StopIteration:
                        break
                    try:
                        candidate_id, lexical_ids = next(candidates)
                    except StopIteration as error:
                        raise ValueError("candidate file ended before Source 1") from error
                    if candidate_id != item.entity_id:
                        raise ValueError(
                            f"candidate/source order mismatch: {candidate_id} != {item.entity_id}"
                        )
                    if len(lexical_ids) > config.union_cap:
                        raise ValueError("union cap is smaller than an existing lexical row")
                    batch_items.append(item)
                    batch_lexical.append(lexical_ids)
                if not batch_items:
                    break
                texts = [semantic_text(item) for item in batch_items]
                nonempty = [position for position, text in enumerate(texts) if text]
                vectors_by_position = {}
                if nonempty:
                    encoded = _prepare_vectors(
                        encoder.encode(
                            [texts[position] for position in nonempty], config.batch_size
                        ),
                        len(nonempty),
                        encoder.dimension,
                    )
                    vectors_by_position = dict(zip(nonempty, encoded))
                for position, (item, lexical_ids) in enumerate(
                    zip(batch_items, batch_lexical)
                ):
                    vector = vectors_by_position.get(position)
                    hits = (
                        index.search(
                            vector,
                            item.country,
                            config.top_k,
                            config.max_pool_per_source,
                            config.probe_radius,
                        )
                        if vector is not None
                        else []
                    )
                    combined = list(lexical_ids)
                    seen = set(combined)
                    for rank, hit in enumerate(hits, start=1):
                        if provenance_writer:
                            provenance_writer.writerow(
                                (
                                    item.entity_id,
                                    hit.entity_id,
                                    hit.source,
                                    f"{hit.score:.9f}",
                                    rank,
                                )
                            )
                        if hit.entity_id not in seen and len(combined) < config.union_cap:
                            combined.append(hit.entity_id)
                            seen.add(hit.entity_id)
                            added_pairs += 1
                    writer.writerow((item.entity_id, ",".join(combined)))
                    entities += 1
                    lexical_pairs += len(lexical_ids)
                    semantic_pairs += len(hits)
            try:
                extra_candidate = next(candidates)
            except StopIteration:
                extra_candidate = None
            if extra_candidate is not None:
                raise ValueError(
                    "candidate file has rows not present in the requested Source 1 set"
                )
    finally:
        index.close()
        if provenance_handle:
            provenance_handle.close()
    if requested is not None and entities != len(requested):
        raise ValueError(
            f"requested ids contain {len(requested)} entities but only {entities} were generated"
        )
    report = {
        "schema_version": "phase2-semantic-union-v1",
        "semantic_index": str(semantic_index_path),
        "semantic_index_sha256": sha256_file(semantic_index_path),
        "model_name": encoder.model_name,
        "config": asdict(config),
        "source1_sha256": sha256_file(source1_path),
        "requested_ids_sha256": sha256_file(ids_path) if ids_path else None,
        "lexical_candidate_sha256": sha256_file(lexical_path),
        "candidate_file": str(output_path),
        "candidate_file_sha256": sha256_file(output_path),
        "provenance_sha256": sha256_file(provenance_path) if provenance_path else None,
        "entities": entities,
        "lexical_pairs": lexical_pairs,
        "semantic_hits": semantic_pairs,
        "semantic_pairs_added": added_pairs,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    _write_json(report_path, report)
    return report
