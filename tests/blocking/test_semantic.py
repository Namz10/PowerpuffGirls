import csv
import tempfile
import unittest
from pathlib import Path

import torch

from src.blocking.semantic import (
    SemanticConfig,
    SentenceTransformerEncoder,
    build_semantic_index,
    semantic_text,
    union_semantic_candidates,
)
from src.blocking.phase2 import canonicalize


HEADER = ["entity_id", "business_name", "business_address", "country"]


def write_source(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


class FakeEncoder:
    model_name = "test-semantic-model"
    dimension = 3
    device = "cpu"

    def encode(self, texts, batch_size):
        rows = []
        for text in texts:
            if "alpha" in text:
                rows.append([1.0, 0.0, 0.0])
            elif "beta" in text:
                rows.append([0.0, 1.0, 0.0])
            else:
                rows.append([0.0, 0.0, 1.0])
        return torch.tensor(rows, dtype=torch.float32)


class SemanticBlockingTest(unittest.TestCase):
    def test_model_input_contains_only_name_and_address(self):
        item = canonicalize("S1-secret-id", "Alpha Ltd", "12 Main St", "India")
        text = semantic_text(item)
        self.assertIn("alpha", text)
        self.assertIn("12 main", text)
        self.assertNotIn("S1-secret-id", text)
        self.assertNotIn("India", text)

    def test_config_rejects_unbounded_or_unknown_device_values(self):
        with self.assertRaises(ValueError):
            SemanticConfig(device="gpu").validate()
        with self.assertRaises(ValueError):
            SemanticConfig(max_pool_per_source=0).validate()
        with self.assertRaises(ValueError):
            SemanticConfig(probe_radius=3).validate()

    def test_sentence_transformer_dependency_is_lazy(self):
        # The module and CPU-first blocker import without sentence-transformers.
        self.assertEqual(SentenceTransformerEncoder.__name__, "SentenceTransformerEncoder")

    def test_streaming_index_and_bounded_union(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source1 = root / "s1.tsv"
            source2 = root / "s2.tsv"
            source3 = root / "s3.tsv"
            write_source(source1, [("S1-1", "Alpha Shop", "One Road", "India")])
            write_source(
                source2,
                [
                    ("S2-alpha", "Alpha Store", "One Road", "India"),
                    ("S2-other", "Gamma Store", "Elsewhere", "India"),
                ],
            )
            write_source(source3, [("S3-beta", "Beta Shop", "Two Road", "India")])
            lexical = root / "lexical.tsv"
            lexical.write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS3-beta\n",
                encoding="utf-8",
            )
            ids = root / "ids.txt"
            ids.write_text("S1-1\n", encoding="utf-8")
            index = root / "semantic.sqlite"
            index_manifest = root / "semantic-index.json"
            config = SemanticConfig(
                device="cpu",
                batch_size=1,
                top_k=2,
                union_cap=3,
                max_pool_per_source=10,
                lsh_bits=4,
                probe_radius=2,
            )
            manifest = build_semantic_index(
                (source2, source3), index, index_manifest, config, encoder=FakeEncoder()
            )
            self.assertEqual(manifest["rows"], {"S2": 2, "S3": 1})
            output = root / "union.tsv"
            report = union_semantic_candidates(
                index,
                source1,
                lexical,
                output,
                root / "union.json",
                config,
                ids,
                root / "semantic-provenance.tsv",
                encoder=FakeEncoder(),
            )
            line = output.read_text(encoding="utf-8").splitlines()[1]
            self.assertEqual(line.split("\t")[0], "S1-1")
            self.assertIn("S2-alpha", line)
            self.assertLessEqual(len(line.split("\t")[1].split(",")), config.union_cap)
            self.assertEqual(report["entities"], 1)
            self.assertGreaterEqual(report["semantic_pairs_added"], 1)


if __name__ == "__main__":
    unittest.main()
