"""Golden smoke tests for representation subsystem."""

import unittest
from src.represent.canonical_record import transform_single_record


class GoldenSmokeTests(unittest.TestCase):
    def test_golden_indic_transliterations(self):
        # Verify 7 Indic scripts
        indic_cases = [
            ("S1-1", "भारत", "devanagari", "bhaarat"),
            ("S1-2", "বাংলা", "bengali", "baanglaa"),
            ("S1-3", "ગુજરાતી", "gujarati", "gujaraatee"),
            ("S1-4", "தமிழ்", "tamil", "tamizh"),
            ("S1-5", "తెలుగు", "telugu", "telugu"),
            ("S1-6", "ಕನ್ನಡ", "kannada", "kannada"),
            ("S1-7", "മലയാളം", "malayalam", "malayaalam"),
        ]
        for eid, raw, exp_script, exp_sub in indic_cases:
            rec = transform_single_record(eid, raw, "", "India")
            self.assertEqual(rec.source_script, exp_script)
            self.assertIn(exp_sub, rec.romanized_name.lower())

    def test_golden_french_entities(self):
        rec1 = transform_single_record(
            "S1-F1", "TotalEnergies S.A.S.U.", "2 Place Jean Millier, 92400 Courbevoie", "France"
        )
        self.assertEqual(rec1.country, "France")
        self.assertIn("sasu", rec1.accent_folded_name)
        self.assertEqual(rec1.postal_code, "92400")

        rec2 = transform_single_record(
            "S1-F2", "Pharmacie Centrale E.U.R.L.", "15 Rue de la République, Boîte Postale 10, 75001 Paris", "France"
        )
        self.assertIn("eurl", rec2.accent_folded_name)
        self.assertIn("bp 10", rec2.normalized_address)
        self.assertEqual(rec2.postal_code, "75001")


if __name__ == "__main__":
    unittest.main()
