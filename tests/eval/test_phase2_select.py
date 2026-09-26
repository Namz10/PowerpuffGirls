import json
import tempfile
import unittest
from pathlib import Path

from src.eval.phase2_select import build_report, decide, paired_bootstrap_delta


class DecisionTests(unittest.TestCase):
    def test_promote_only_when_lower_bound_and_pareto(self):
        self.assertEqual(decide({"ci95_lower": 0.01}, True), "promote_phase2")
        self.assertEqual(decide({"ci95_lower": 0.01}, False), "keep_phase1_raw")
        self.assertEqual(decide({"ci95_lower": 0.0}, True), "keep_phase1_raw")
        self.assertEqual(decide({"ci95_lower": -0.1}, True), "keep_phase1_raw")

    def test_bootstrap_requires_2000_and_is_deterministic(self):
        incumbent = [0.0, 1.0, 0.5, 0.2]
        challenger = [1.0, 1.0, 0.5, 0.4]
        with self.assertRaises(ValueError):
            paired_bootstrap_delta(incumbent, challenger, resamples=10)
        first = paired_bootstrap_delta(incumbent, challenger)
        second = paired_bootstrap_delta(incumbent, challenger)
        self.assertEqual(first, second)
        self.assertGreater(first["ci95_upper"], first["ci95_lower"])


class ReportTests(unittest.TestCase):
    def test_synthetic_keep_and_script_misses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "p1.tsv").write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS2-1\nS1-2\t\n",
                encoding="utf-8",
            )
            (root / "p2.tsv").write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS2-1\nS1-2\tS3-9\n",
                encoding="utf-8",
            )
            (root / "gold.tsv").write_text(
                "source1_entity_id\tmatched_entity_ids\nS1-1\tS2-1\nS1-2\tS3-2\n",
                encoding="utf-8",
            )
            (root / "join.tsv").write_text(
                "source1_entity_id\tgold_list_length\tscript_class\tindic_targets\taccented_latin_targets\n"
                "S1-1\t1\tindic\t1\t0\nS1-2\t1\taccented_latin\t0\t1\n",
                encoding="utf-8",
            )
            (root / "s1.tsv").write_text(
                "entity_id\tbusiness_name\tbusiness_address\tcountry\nS1-1\tA\tB\tUS\nS1-2\tC\tD\tIndia\n",
                encoding="utf-8",
            )
            (root / "miss.tsv").write_text(
                "source1_entity_id\ttruth_entity_ids\tcandidate_entity_ids\tmissed_truth_ids\tstatus\tmiss_reason\n"
                "S1-1\tS2-1\tS2-1\t\tcomplete\t\n"
                "S1-2\tS3-2\tS3-9\tS3-2\tmiss\tno_retrieval_evidence\n",
                encoding="utf-8",
            )
            (root / "blocker.json").write_text(
                json.dumps({"promotion_check": {"selected_point_on_pareto_frontier": False}}),
                encoding="utf-8",
            )
            report = build_report(
                root / "p1.tsv", root / "p2.tsv", root / "gold.tsv", root / "join.tsv",
                root / "s1.tsv", root / "miss.tsv", root / "blocker.json", ["S1-1", "S1-2"],
            )
            self.assertEqual(report["decision"], "keep_phase1_raw")
            self.assertIsNone(report["dominant_miss_reason"]["indic"])
            self.assertEqual(report["dominant_miss_reason"]["accented_latin"], "no_retrieval_evidence")
            self.assertIn("US", report["country_slices"])
            self.assertIn("indic", report["script_slices"])


if __name__ == "__main__":
    unittest.main()
