import unittest

from src.matching.decide import choose_threshold, finite_disjoint_example, kept_ids


class DecideTests(unittest.TestCase):
    def test_empty_candidate_list_stays_empty(self):
        self.assertEqual(kept_ids([], [], 0.5), [])

    def test_only_candidate_ids_are_kept(self):
        kept = kept_ids(["S2-1", "S3-2"], [0.2, 0.9], 0.5)
        self.assertEqual(kept, ["S3-2"])

    def test_tie_keeps_the_higher_threshold(self):
        groups = [("S1-1", ["S2-a"], [0.4], set())]
        threshold, score = choose_threshold(groups)
        self.assertEqual(threshold, 1.0)
        self.assertEqual(score, 1.0)

    def test_disjoint_case_is_the_official_zero(self):
        self.assertEqual(finite_disjoint_example(), 0.0)


if __name__ == "__main__":
    unittest.main()
