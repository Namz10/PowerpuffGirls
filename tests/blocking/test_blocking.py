import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.blocking.generate import (
    Evidence,
    MetricAccumulator,
    choose_cap,
    generate,
    load_queries,
    load_truth,
    select,
)
from src.blocking.index import build_index
from src.blocking.normalize import normalize_raw, raw_tokens
from src.blocking.verify_subset import verify_subset


HEADER = ["entity_id", "business_name", "business_address", "country"]


def write_source(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


class BlockingTest(unittest.TestCase):
    def test_normalization_is_unicode_preserving(self):
        self.assertEqual(normalize_raw("  Café—मार्केट! "), "café मार्केट")
        self.assertEqual(raw_tokens("A Café café"), ("café",))

    def test_generation_country_sources_empty_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            s2, s3, s1 = root / "s2.tsv", root / "s3.tsv", root / "s1.tsv"
            write_source(s2, [
                ("S2-1", "Alpha Labs", "1 Main St", "US"),
                ("S2-2", "Alpha Labs", "1 Main St", "France"),
            ])
            write_source(s3, [("S3-1", "Alpha Laboratory", "1 Main St", "US")])
            write_source(s1, [
                ("S1-1", "ALPHA LABS", "1 Main St", "US"),
                ("S1-2", "Sans Correspondance", "Rue Vide", "France"),
            ])
            index = root / "index.sqlite"
            manifest = build_index((s2, s3), index)
            self.assertEqual(sum(item["rows"] for item in manifest["shards"]), 3)
            output, provenance = root / "candidate.tsv", root / "provenance.tsv"
            report = generate(index, load_queries(s1), output, 5, provenance)
            with output.open(encoding="utf-8") as handle:
                rows = list(csv.reader(handle, delimiter="\t"))
            self.assertEqual(rows[0], ["source1_entity_id", "candidate_entity_ids"])
            self.assertEqual(rows[1][0], "S1-1")
            self.assertIn("S2-1", rows[1][1].split(","))
            self.assertNotIn("S2-2", rows[1][1].split(","))
            self.assertEqual(rows[2], ["S1-2", ""])
            with provenance.open(encoding="utf-8") as handle:
                self.assertEqual(len(list(csv.reader(handle, delimiter="\t"))[0]), 10)
            self.assertEqual(report["candidate_header"], ["source1_entity_id", "candidate_entity_ids"])

    def test_cap_choice_uses_measured_tradeoff(self):
        sweep = {
            5: {"recovered_truth_links": 100, "total_candidate_pairs": 500},
            10: {"recovered_truth_links": 110, "total_candidate_pairs": 600},
            20: {"recovered_truth_links": 111, "total_candidate_pairs": 800},
        }
        self.assertEqual(choose_cap(sweep), 10)

    def test_source_floor_never_exceeds_strict_global_cap(self):
        ranked = [
            ("S2-1", Evidence("S2", exact_name=True)),
            ("S2-2", Evidence("S2", name_token=True)),
            ("S3-1", Evidence("S3", exact_name=True)),
            ("S3-2", Evidence("S3", name_token=True)),
        ]
        self.assertEqual(len(select(ranked, cap=3, source_floor=2)), 3)
        self.assertEqual(select(ranked, cap=0), [])
        with self.assertRaises(ValueError):
            select(ranked, cap=-1)

    def test_strict_subset_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matching = root / "matching.tsv"
            candidates = root / "candidates.tsv"
            matching.write_text(
                "source1_entity_id\tmatched_entity_ids\nS1-1\tS2-1\nS1-2\t\n", encoding="utf-8"
            )
            candidates.write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS2-1,S3-1\nS1-2\t\n", encoding="utf-8"
            )
            self.assertEqual(verify_subset(matching, candidates), 2)
            matching.write_text(
                "source1_entity_id\tmatched_entity_ids\nS1-1\tS2-9\nS1-2\t\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                verify_subset(matching, candidates)

    def test_metrics_report_each_target_source(self):
        accumulator = MetricAccumulator()
        accumulator.add(["S2-1", "S3-9"], {"S2-1", "S3-1"})
        report = accumulator.finish(100)
        self.assertEqual(report["link_recall_by_source"]["S2"]["link_recall"], 1.0)
        self.assertEqual(report["link_recall_by_source"]["S3"]["link_recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
