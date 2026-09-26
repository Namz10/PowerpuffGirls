"""Unit tests for normalization idempotency f(f(x)) == f(x)."""

import unittest
from src.represent.normalize_name import normalize_name
from src.represent.normalize_address import normalize_address


class IdempotencyTests(unittest.TestCase):
    def test_name_normalization_idempotency(self):
        cases = [
            "M/S Reliance Industries Pvt. Ltd.",
            "L'Oréal Société Anonyme & Co.",
            "Tata Consultancy Services Limited",
            "123 Tech Solutions Inc.",
            "नमस्ते भारत प्राइवेट लिमिटेड",
        ]
        for c in cases:
            norm1, rom1, fold1, _, _ = normalize_name(c)
            # Re-normalizing the output must yield the exact same output
            norm2, rom2, fold2, _, _ = normalize_name(fold1)
            self.assertEqual(fold1, fold2, f"Idempotency failed on name: {c}")

    def test_address_normalization_idempotency(self):
        cases = [
            "Flat 402, 4th Flr, Opp. Metro Station, MG Rd, Bangalore 560001",
            "15 Boulevard Haussmann, 75440 CEDEX 09, Paris",
            "100 Main St., Suite 500, New York, NY 10001",
            "",
            None,
        ]
        for c in cases:
            clean1, toks1, empty1, land1, ced1, post1 = normalize_address(c, country="India")
            clean2, toks2, empty2, land2, ced2, post2 = normalize_address(clean1, country="India")
            self.assertEqual(clean1, clean2, f"Idempotency failed on address: {c}")
            self.assertEqual(toks1, toks2)


if __name__ == "__main__":
    unittest.main()
