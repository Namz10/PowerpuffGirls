import random
import unittest

from src.matching.sample_fit import allocate, assert_no_leak, assert_split_disjoint, draw


class SampleTests(unittest.TestCase):
    def test_allocation_sums_and_respects_size(self):
        sizes = {("India", "0"): 10, ("India", "1"): 3, ("US", "6+"): 7}
        counts = allocate(sizes, 11)
        self.assertEqual(sum(counts.values()), 11)
        for key, count in counts.items():
            self.assertLessEqual(count, sizes[key])

    def test_draw_is_deterministic_and_sorted(self):
        strata = {("US", "0"): ["S1-2", "S1-1", "S1-3"], ("India", "1"): ["S1-9", "S1-8"]}
        first = draw(strata, 3, seed=42)
        second = draw(dict(strata), 3, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))
        self.assertEqual(len(first), 3)

    def test_seed_changes_the_draw(self):
        strata = {("US", "0"): [f"S1-{index}" for index in range(30)]}
        self.assertNotEqual(draw(strata, 5, seed=42), draw(strata, 5, seed=7))

    def test_overlap_is_refused(self):
        with self.assertRaises(ValueError):
            assert_split_disjoint({"S1-1"}, {"S1-1"}, set())
        with self.assertRaises(ValueError):
            assert_no_leak(["S1-1"], {"S1-1", "S1-2"}, {"S1-1"}, set())

    def test_rng_is_the_stdlib_generator(self):
        self.assertEqual(random.Random(42).random(), random.Random(42).random())


if __name__ == "__main__":
    unittest.main()
