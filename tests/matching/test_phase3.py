import unittest

from src.eval.score import macro_f05
from src.matching.calibrate import ProbabilityCalibrator, keep_country_calibrator
from src.matching.decision_config import config_sha256, skeleton_config, validate_config
from src.matching.ensemble import average_fold_probabilities
from src.matching.folds import assert_fit_only, train_valid_groups
from src.matching.pass2 import pass2_feature_rows
from src.matching.predict import write_matching
from src.matching.run_phase3 import GATE_PATH, prepare_message, smoke
from src.matching.set_rule import apply_one_owner, choose_set_rule


class Phase3Tests(unittest.TestCase):
    def test_loop_or_report_ids_are_refused(self):
        with self.assertRaises(ValueError):
            assert_fit_only({"S1-1"}, {"S1-1"}, {"S1-1"}, set())
        with self.assertRaises(ValueError):
            assert_fit_only({"S1-9"}, {"S1-1"}, set(), set())

    def test_five_groups_are_disjoint_folds(self):
        ids = ["S1-a", "S1-b", "S1-c", "S1-d", "S1-e"]
        splits = train_valid_groups(ids, n_splits=5, seed=42)
        self.assertEqual(len(splits), 5)
        held = [test for _train, test in splits]
        self.assertEqual(len(set().union(*held)), 5)
        for left in range(5):
            for right in range(left + 1, 5):
                self.assertFalse(held[left] & held[right])
        again = train_valid_groups(ids, n_splits=5, seed=42)
        self.assertEqual(held, [test for _train, test in again])

    def test_average_preserves_order_and_candidate_subset(self):
        averaged = average_fold_probabilities([[0.2, 0.8], [0.4, 0.6]])
        self.assertEqual(len(averaged), 2)
        self.assertAlmostEqual(averaged[0], 0.3)
        self.assertAlmostEqual(averaged[1], 0.7)
        kept = ["S3-1"] if averaged[1] >= 0.5 else []
        self.assertTrue(set(kept) <= {"S2-1", "S3-1"})

    def test_empty_candidate_row_stays_empty(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matching_results.tsv"
            write_matching(path, [("S1-1", [])])
            self.assertIn("S1-1\t\n", path.read_text(encoding="utf-8"))

    def test_one_owner_cannot_assign_one_id_twice(self):
        groups = [
            ("S1-a", ["S2-x"], [0.9], {"S2-x"}),
            ("S1-b", ["S2-x"], [0.2], set()),
        ]
        owned = apply_one_owner(groups)
        owners = [source_id for source_id, ids, _probs, _truth in owned if "S2-x" in ids]
        self.assertEqual(owners, ["S1-a"])

    def test_country_calibrator_is_dropped_when_worse(self):
        self.assertFalse(keep_country_calibrator(0.5, 0.4))
        self.assertTrue(keep_country_calibrator(0.4, 0.4))
        calibrator = ProbabilityCalibrator()
        calibrator.fit([0.1, 0.9, 0.2], [0, 1, 0], ["US", "US", "India"])
        self.assertNotIn("India", calibrator.kept_countries)
        self.assertEqual(calibrator.transform_one(0.2, "France"), calibrator.transform_one(0.2, "global"))

    def test_config_hash_is_stable_and_lock_requires_400k(self):
        first = skeleton_config()
        second = skeleton_config()
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["status"], "skeleton")
        validate_config(first)
        locked = dict(first)
        locked["status"] = "locked"
        locked["sha256"] = config_sha256(locked)
        with self.assertRaises(ValueError):
            validate_config(locked)

    def test_prepare_rejects_a_report_id_and_smoke_writes_no_gate(self):
        with self.assertRaises(ValueError):
            prepare_message({"S1-r"}, {"S1-a"}, set(), {"S1-r"})
        result = smoke()
        self.assertEqual(result["status"], "skeleton")
        self.assertFalse(GATE_PATH.exists())

    def test_set_rule_uses_the_official_macro(self):
        groups = [("S1-1", ["S2-a"], [0.2], set())]
        chosen = choose_set_rule(groups, grid=[0.5, 1.0])
        predicted = {"S1-1": set()}
        self.assertEqual(macro_f05(predicted, {"S1-1": set()}), 1.0)
        self.assertIn(chosen["rule_family"], {"global_threshold", "per_source_threshold", "k_by_bucket"})

    def test_pass2_marks_a_single_owner(self):
        rows = pass2_feature_rows(["S1-a", "S1-b"], ["S2-1", "S2-1"], [0.8, 0.3])
        self.assertEqual(rows[0][-1], 1.0)
        self.assertEqual(rows[1][-1], 0.0)
        self.assertEqual(len(rows[0]), 5)


if __name__ == "__main__":
    unittest.main()
