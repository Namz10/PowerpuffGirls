import unittest

from src.matching.features_raw import jaccard, raw_feature_row


class FeatureTests(unittest.TestCase):
    def test_same_inputs_are_identical(self):
        provenance = {
            "retrieval_score": "1.5",
            "rank": "2",
            "exact_name": "1",
            "exact_address": "0",
            "name_token": "1",
            "address_token": "0",
            "target_source": "S3",
        }
        first = raw_feature_row("Acme Corp", "1 Main St", "Acme Corporation", "", provenance)
        second = raw_feature_row("Acme Corp", "1 Main St", "Acme Corporation", "", provenance)
        self.assertEqual(first, second)
        self.assertEqual(first[4], 1.0)
        self.assertEqual(first[-1], 1.0)

    def test_empty_token_sets_have_jaccard_one(self):
        self.assertEqual(jaccard((), ()), 1.0)

    def test_feature_width(self):
        provenance = {
            "retrieval_score": "0",
            "rank": "1",
            "exact_name": "0",
            "exact_address": "0",
            "name_token": "0",
            "address_token": "0",
            "target_source": "S2",
        }
        self.assertEqual(len(raw_feature_row("a", "b", "a", "b", provenance)), 12)


if __name__ == "__main__":
    unittest.main()
