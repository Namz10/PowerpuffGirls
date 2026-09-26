import random
import unittest

from src.eval.split_protocol import allocate, assign, bucket_name


class BucketTests(unittest.TestCase):
    def test_length_11_folds_into_6_plus(self):
        self.assertEqual(bucket_name(0), "0")
        self.assertEqual(bucket_name(1), "1")
        self.assertEqual(bucket_name(3), "2-3")
        self.assertEqual(bucket_name(5), "4-5")
        self.assertEqual(bucket_name(11), "6+")


class AllocationTests(unittest.TestCase):
    def test_report_is_floor_10_percent_and_loop_is_25000(self):
        sizes = {
            ("India", "0"): 20_000,
            ("India", "1"): 15_000,
            ("US", "0"): 40_000,
            ("US", "6+"): 8_000,
        }
        allocation = allocate(sizes)
        self.assertEqual(sum(item["loop"] for item in allocation.values()), 25_000)
        for key, size in sizes.items():
            self.assertEqual(allocation[key]["report"], (size * 10) // 100)
            self.assertEqual(
                allocation[key]["fit"] + allocation[key]["loop"] + allocation[key]["report"],
                size,
            )

    def test_assignment_is_disjoint_sorted_and_repeatable(self):
        rng = random.Random(1)
        strata = {}
        for country in ("India", "US"):
            for bucket in ("0", "1", "2-3", "4-5", "6+"):
                strata[(country, bucket)] = [f"S1-{country[0]}{bucket}-{index:05d}" for index in range(4_000)]
                rng.shuffle(strata[(country, bucket)])
        sizes = {key: len(ids) for key, ids in strata.items()}
        allocation = allocate(sizes)
        first = assign(strata, allocation, seed=42)
        second = assign(strata, allocation, seed=42)
        self.assertEqual(first, second)
        covered = []
        for name in ("fit", "loop", "report"):
            self.assertEqual(first[name], sorted(first[name]))
            covered.extend(first[name])
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(len(first["loop"]), 25_000)
        self.assertEqual(len(covered), sum(sizes.values()))


if __name__ == "__main__":
    unittest.main()
