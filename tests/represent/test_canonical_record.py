"""Unit tests for CanonicalRecord transformation and open-country support."""

import unittest
from src.represent.canonical_record import transform_single_record


class CanonicalRecordTests(unittest.TestCase):
    def test_india_record_transformation(self):
        rec = transform_single_record(
            entity_id="S1-001",
            raw_name="M/S Infosys Limited",
            raw_address="Electronics City, Hosur Rd, Bengaluru, Karnataka 560100",
            raw_country="India",
        )
        self.assertEqual(rec.entity_id, "S1-001")
        self.assertEqual(rec.source, "source1")
        self.assertEqual(rec.country, "India")
        self.assertIn("infosys", rec.normalized_name)
        self.assertEqual(rec.postal_code, "560100")
        self.assertFalse(rec.is_empty_address)

    def test_france_record_transformation(self):
        rec = transform_single_record(
            entity_id="S1-002",
            raw_name="Danone S.A.",
            raw_address="17 Boulevard Haussmann, 75009 Paris",
            raw_country="France",
        )
        self.assertEqual(rec.country, "France")
        self.assertEqual(rec.postal_code, "75009")
        self.assertIn("danone sa", rec.accent_folded_name)

    def test_open_unseen_country(self):
        rec = transform_single_record(
            entity_id="S1-003",
            raw_name="Siemens AG",
            raw_address="Werner-von-Siemens-Straße 1, Munich",
            raw_country="Germany",
        )
        # Open country label preserved
        self.assertEqual(rec.country, "Germany")
        self.assertIn("siemens ag", rec.accent_folded_name)

    def test_empty_address(self):
        rec = transform_single_record(
            entity_id="S1-004",
            raw_name="Ghost Co",
            raw_address="",
            raw_country="US",
        )
        self.assertTrue(rec.is_empty_address)
        self.assertEqual(rec.normalized_address, "")
        self.assertIsNone(rec.postal_code)


if __name__ == "__main__":
    unittest.main()
