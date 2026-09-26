import tempfile
import unittest
from pathlib import Path

from src.matching.pairs import iter_groups
from src.matching.predict import write_matching


class PredictTests(unittest.TestCase):
    def test_empty_list_keeps_the_tab_and_candidate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matching_results.tsv"
            write_matching(path, [("S1-b", []), ("S1-a", ["S3-1", "S2-2"])])
            text = path.read_text(encoding="utf-8")
        self.assertEqual(
            text,
            "source1_entity_id\tmatched_entity_ids\nS1-b\t\nS1-a\tS3-1,S2-2\n",
        )

    def test_s1_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matching_results.tsv"
            with self.assertRaises(ValueError):
                write_matching(path, [("S1-1", ["S1-2"])])

    def test_provenance_must_follow_candidate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = root / "candidate_pairs.tsv"
            provenance = root / "provenance.tsv"
            candidates.write_text(
                "source1_entity_id\tcandidate_entity_ids\nS1-1\tS2-1\n",
                encoding="utf-8",
            )
            provenance.write_text(
                "source1_entity_id\tcandidate_entity_id\ttarget_source\tprovenance\trank\t"
                "exact_name\texact_address\tname_token\taddress_token\tretrieval_score\n"
                "S1-1\tS2-9\tS2\texact_name\t1\t1\t0\t0\t0\t1.0\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                list(iter_groups(candidates, provenance))


if __name__ == "__main__":
    unittest.main()
