import csv
import tempfile
import unittest
from pathlib import Path

from src.blocking.phase2 import (
    INDEX_SCHEMA_VERSION,
    Phase2Config,
    Phase2Evidence,
    Phase2Index,
    build_phase2_index,
    canonicalize,
    generate_phase2,
    paired_bootstrap_delta,
    pareto_frontier,
    phonetic_name,
    retrieve_phase2,
    select_phase2,
)


HEADER = ["entity_id", "business_name", "business_address", "country"]


def write_source(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


class Phase2BlockingTest(unittest.TestCase):
    def test_canonicalize_requires_no_dataframe_or_parquet(self):
        item = canonicalize(
            "S1-1", "Café कंसल्टेंसी", "12 Boîte Postale, 75001 Paris", "fr"
        )
        self.assertEqual(item.country, "France")
        self.assertEqual(item.postal_code, "75001")
        self.assertTrue(item.romanized_name)
        self.assertTrue(item.name_ngrams)

    def test_phonetic_key_handles_common_spelling_variants(self):
        self.assertEqual(phonetic_name("Katar Trading"), phonetic_name("Qatar Trading"))
        self.assertEqual(phonetic_name("Photo Center"), phonetic_name("Foto Center"))

    def test_index_and_cross_script_retrieval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source2 = root / "s2.tsv"
            source3 = root / "s3.tsv"
            write_source(
                source2,
                [
                    ("S2-1", "taataa kamsaltemsee", "Mumbai 400001", "India"),
                    ("S2-2", "Catarina Atelier", "12 Rue Paix 75001", "France"),
                    ("S2-3", "Wrong Country", "12 Rue Paix 75001", "US"),
                ],
            )
            write_source(source3, [("S3-1", "Qatar Trading", "Doha", "India")])
            index_path = root / "phase2.sqlite"
            manifest = build_phase2_index((source2, source3), index_path)
            self.assertEqual(manifest["schema_version"], INDEX_SCHEMA_VERSION)
            index = Phase2Index(index_path)
            try:
                indic = canonicalize("S1-1", "टाटा कंसल्टेंसी", "Mumbai 400001", "India")
                ranked = retrieve_phase2(index, indic, Phase2Config(cap=20))
                evidence = dict(ranked)["S2-1"]
                self.assertIn("romanized_exact", evidence.channels)
                self.assertNotIn("S2-3", dict(ranked))

                typo = canonicalize("S1-2", "Katarina Atelier", "", "France")
                typo_ranked = retrieve_phase2(index, typo, Phase2Config(cap=20))
                self.assertIn("romanized_ngram", dict(typo_ranked)["S2-2"].channels)

                phonetic = canonicalize("S1-3", "Katar Trading", "", "India")
                phonetic_ranked = retrieve_phase2(index, phonetic, Phase2Config(cap=20))
                self.assertIn("phonetic_exact", dict(phonetic_ranked)["S3-1"].channels)
            finally:
                index.close()

    def test_rescue_quota_is_strict_and_strong_evidence_survives(self):
        ranked = [
            ("S2-1", Phase2Evidence("S2", channels={"canonical_name_exact"})),
            ("S2-2", Phase2Evidence("S2", channels={"romanized_ngram"})),
            ("S3-1", Phase2Evidence("S3", channels={"phonetic_exact"})),
        ]
        selected = select_phase2(
            ranked, Phase2Config(cap=3, source_floor=0, rescue_quota=1)
        )
        self.assertEqual([item[0] for item in selected], ["S2-1", "S2-2"])

    def test_bootstrap_and_pareto_are_deterministic(self):
        first = paired_bootstrap_delta([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], seed=7)
        second = paired_bootstrap_delta([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], seed=7)
        self.assertEqual(first, second)
        self.assertTrue(first["promote"])
        frontier = pareto_frontier(
            [
                {"name": "a", "link_recall": 0.8, "mean_width": 10.0},
                {"name": "b", "link_recall": 0.7, "mean_width": 12.0},
                {"name": "c", "link_recall": 0.9, "mean_width": 20.0},
            ]
        )
        self.assertEqual([point["name"] for point in frontier], ["a", "c"])

    def test_generation_reports_variants_channels_sweeps_and_slices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source1, source2, source3 = root / "s1.tsv", root / "s2.tsv", root / "s3.tsv"
            write_source(source1, [("S1-1", "Katar Trading", "Doha", "India")])
            write_source(source2, [("S2-1", "Qatar Trading", "Doha", "India")])
            write_source(source3, [("S3-1", "Unrelated", "Elsewhere", "India")])
            index_path = root / "phase2.sqlite"
            build_phase2_index((source2, source3), index_path)
            report = generate_phase2(
                index_path,
                source1,
                root / "candidates.tsv",
                Phase2Config(cap=10, source_floor=0, rescue_quota=5),
                {"S1-1"},
                {"S1-1": {"S2-1"}},
                root / "provenance.tsv",
                root / "misses.tsv",
                (5, 10),
                (0, 5),
                Path(__file__).resolve().parents[2] / "artifacts" / "resources",
                workers=2,
            )
            self.assertTrue(report["provisional"])
            self.assertIn("raw_only", report["variants"])
            self.assertIn("phonetic_exact", report["channels"])
            self.assertIn("5", report["cap_sweep"])
            self.assertIn("cap=5,rescue_quota=0", report["selection_surface"])
            self.assertIn("latin", report["script_slices"])
            self.assertIsNotNone(report["boilerplate_sha256"])
            self.assertIn("eligible", report["promotion_check"])
            self.assertGreaterEqual(
                report["variants"]["union"]["link_recall"],
                report["variants"]["raw_only"]["link_recall"],
            )


if __name__ == "__main__":
    unittest.main()
