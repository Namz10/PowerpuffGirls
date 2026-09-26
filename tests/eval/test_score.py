import math
import tempfile
import unittest
from pathlib import Path

from src.eval.config import train_dir
from src.eval.score import (
    CANDIDATE_HEADER,
    entity_f05,
    load_id_lists,
    macro_f05,
    predict_nothing_score,
)

PDF_PREDICTED = {"S2-00047", "S2-00193", "S3-00812"}
PDF_TRUTH = {"S2-00047", "S3-00812"}
SINGLETON_RATE = 123247 / 2206821


class EntityScoreTests(unittest.TestCase):
    def test_pdf_example_rounds_to_published_value(self):
        score = entity_f05(PDF_PREDICTED, PDF_TRUTH)
        self.assertTrue(math.isfinite(score))
        self.assertEqual(round(score, 3), 0.714)
        self.assertAlmostEqual(score, 5 / 7, places=12)

    def test_empty_empty(self):
        self.assertEqual(entity_f05(set(), set()), 1.0)

    def test_truth_empty_prediction_nonempty(self):
        self.assertEqual(entity_f05({"S2-1"}, set()), 0.0)

    def test_truth_nonempty_prediction_empty(self):
        self.assertEqual(entity_f05(set(), {"S2-1"}), 0.0)

    def test_nonempty_disjoint_sets_are_finite_zero(self):
        score = entity_f05({"S2-1"}, {"S2-2"})
        self.assertEqual(score, 0.0)
        self.assertTrue(math.isfinite(score))

    def test_perfect_prediction(self):
        ids = {"S2-1", "S3-2"}
        self.assertEqual(entity_f05(ids, set(ids)), 1.0)

    def test_partial_overlap(self):
        score = entity_f05({"S2-1", "S2-2"}, {"S2-1", "S2-2", "S2-3"})
        self.assertTrue(math.isfinite(score))
        self.assertAlmostEqual(score, 10 / 11, places=12)


class MacroTests(unittest.TestCase):
    def test_unweighted_mean_not_link_weighted(self):
        truth = {"S1-a": {"S2-1"}, "S1-b": {"S2-2", "S2-3", "S2-4", "S2-5"}}
        predicted = {"S1-a": {"S2-1"}, "S1-b": {"S2-2"}}
        score = macro_f05(predicted, truth)
        self.assertAlmostEqual(score, (1.0 + 0.625) / 2, places=12)
        self.assertNotAlmostEqual(score, 0.7692307692307692, places=4)

    def test_repeated_execution_is_identical(self):
        truth = {"S1-a": PDF_TRUTH, "S1-b": set(), "S1-c": {"S2-9"}}
        predicted = {"S1-a": PDF_PREDICTED, "S1-b": set(), "S1-c": {"S3-8"}}
        first = macro_f05(predicted, truth)
        second = macro_f05(predicted, truth)
        self.assertEqual(first, second)
        self.assertEqual(entity_f05(PDF_PREDICTED, PDF_TRUTH), entity_f05(set(PDF_PREDICTED), set(PDF_TRUTH)))


class BaselineTests(unittest.TestCase):
    def test_predict_nothing_on_full_train(self):
        gold = train_dir() / "train_ground_truth.tsv"
        first = predict_nothing_score(gold)
        second = predict_nothing_score(gold)
        self.assertEqual(first, second)
        self.assertEqual(first, SINGLETON_RATE)
        self.assertTrue(math.isfinite(first))


class FileContractTests(unittest.TestCase):
    def test_empty_list_and_candidate_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate_pairs.tsv"
            path.write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS2-1,S3-2\nS1-2\t\n",
                encoding="utf-8",
                newline="\n",
            )
            rows = load_id_lists(path, CANDIDATE_HEADER)
        self.assertEqual(rows["S1-1"], {"S2-1", "S3-2"})
        self.assertEqual(rows["S1-2"], set())


if __name__ == "__main__":
    unittest.main()
