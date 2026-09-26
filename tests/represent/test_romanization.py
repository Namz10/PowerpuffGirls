"""Comprehensive tests for deterministic Indic romanization across all 7 scripts."""

import unittest
from src.represent.romanization import romanize_indic_text
from src.represent.unicode_utils import detect_script, fold_accents


class RomanizationTests(unittest.TestCase):
    def test_devanagari_romanization(self):
        # Hindi: नमस्ते -> namaste, भारत -> bhaarat, कंपनी -> kampanee / kampani
        res = romanize_indic_text("भारत")
        self.assertIn("bhaarat", res.lower())
        
        res = romanize_indic_text("नमस्ते")
        self.assertIn("namaste", res.lower())

    def test_bengali_romanization(self):
        # Bengali: ভারত -> bhaarat, ঢাকা -> dhaakaa
        res = romanize_indic_text("ভারত")
        self.assertIn("bhaarat", res.lower())

    def test_gujarati_romanization(self):
        # Gujarati: ભારત -> bhaarat, નમસ્તે -> namaste
        res = romanize_indic_text("ભારત")
        self.assertIn("bhaarat", res.lower())

    def test_tamil_romanization(self):
        # Tamil: தமிழ்நாடு -> tamizhnaadu, சென்னை -> chennai
        res = romanize_indic_text("சென்னை")
        self.assertIn("chen", res.lower())

    def test_telugu_romanization(self):
        # Telugu: భారత్ -> bhaarat, నమస్కారం -> namaskaaram
        res = romanize_indic_text("భారత్")
        self.assertIn("bhaarat", res.lower())

    def test_kannada_romanization(self):
        # Kannada: ಭಾರತ -> bhaarat, ನಮಸ್ಕಾರ -> namaskaara
        res = romanize_indic_text("ಭಾರತ")
        self.assertIn("bhaarat", res.lower())

    def test_malayalam_romanization(self):
        # Malayalam: ഭാരതം -> bhaaratam
        res = romanize_indic_text("ഭാരതം")
        self.assertIn("bhaarat", res.lower())

    def test_preserves_unknown_code_points_and_ascii(self):
        # Mixed string with numbers, punctuation, and emoji / unmapped symbols
        text = "ABC 123 !@# भारत 🚀 XYZ"
        res = romanize_indic_text(text)
        self.assertTrue(res.startswith("ABC 123 !@#"))
        self.assertTrue(res.endswith("🚀 XYZ"))
        self.assertIn("bhaarat", res.lower())

    def test_script_detection(self):
        self.assertEqual(detect_script("भारत एंटरप्राइजेज"), "devanagari")
        self.assertEqual(detect_script("ಕರ್ನಾಟಕ ಎಂಟರ್ಪ್ರೈಸಸ್"), "kannada")
        self.assertEqual(detect_script("தமிழ்நாடு நிறுவனம்"), "tamil")
        self.assertEqual(detect_script("తెలుగు సంస్థ"), "telugu")
        self.assertEqual(detect_script("বাংলা সংস্থা"), "bengali")
        self.assertEqual(detect_script("ગુજરાત લિમિટેડ"), "gujarati")
        self.assertEqual(detect_script("കേരളം പ്രൈവറ്റ് ലിമിറ്റഡ്"), "malayalam")
        self.assertEqual(detect_script("Amazon Retail LLC"), "latin")


if __name__ == "__main__":
    unittest.main()
