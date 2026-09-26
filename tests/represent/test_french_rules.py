"""Unit tests for French legal forms, ordinals, BP, CEDEX, and postal codes."""

import unittest
from src.represent.normalize_name import normalize_name
from src.represent.normalize_address import normalize_address


class FrenchRulesTests(unittest.TestCase):
    def test_french_legal_entities(self):
        cases = [
            ("L'Oréal SAS", "l oreal sas"),
            ("Tech Solutions SASU", "tech solutions sasu"),
            ("Boulangerie EURL", "boulangerie eurl"),
            ("Immobilier SCI", "immobilier sci"),
            ("Transport SNC", "transport snc"),
            ("Conseil SC", "conseil sc"),
            ("Société Civile Immobilière Moderne", "sci moderne"),
            ("Société Anonyme de Paris", "sa de paris"),
        ]
        for raw, expected_substr in cases:
            _, _, folded_name, _, _ = normalize_name(raw)
            self.assertIn(expected_substr, folded_name)

    def test_french_boite_postale(self):
        addr1 = "12 Rue de la Paix, Boîte Postale 45, Paris"
        clean1, _, _, _, _, _ = normalize_address(addr1, country="France")
        self.assertIn("bp 45", clean1)

        addr2 = "BP 102, 75008 Paris"
        clean2, _, _, _, _, _ = normalize_address(addr2, country="France")
        self.assertIn("bp 102", clean2)

    def test_french_ordinals(self):
        addr = "12 1er étage, 3ème rue"
        clean, _, _, _, _, _ = normalize_address(addr, country="France")
        self.assertIn("1", clean)
        self.assertIn("3", clean)
        self.assertNotIn("1er", clean)
        self.assertNotIn("3ème", clean)

    def test_french_cedex_and_postal_code(self):
        addr = "15 Boulevard Haussmann, 75440 CEDEX 09, Paris"
        clean, toks, is_empty, has_landmark, is_cedex, postal = normalize_address(addr, country="France")
        self.assertTrue(is_cedex)
        self.assertEqual(postal, "75440")
        self.assertFalse(is_empty)


if __name__ == "__main__":
    unittest.main()
