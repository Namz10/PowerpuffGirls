"""Unit tests for TokenResource IDF computation and boilerplate mining."""

import unittest
from pathlib import Path
import tempfile
from src.represent.token_resource import (
    TokenResource,
    compute_idf_and_boilerplate_from_tokens,
)


class TokenResourceTests(unittest.TestCase):
    def test_compute_idf_and_boilerplate(self):
        docs = {
            "India": [
                ["reliance", "industries", "limited"],
                ["tata", "consultancy", "limited"],
                ["infosys", "technologies", "limited"],
            ],
            "US": [
                ["apple", "inc"],
                ["microsoft", "corporation"],
                ["amazon", "inc"],
            ],
        }

        name_idf, bp = compute_idf_and_boilerplate_from_tokens(
            docs, boilerplate_df_threshold=0.5
        )

        # 'limited' appears in 100% of India docs -> should be boilerplate
        self.assertIn("limited", bp["India"])
        # 'reliance' appears in 1/3 of India docs -> should not be boilerplate
        self.assertNotIn("reliance", bp["India"])

        # High-frequency tokens have lower IDF than rare tokens
        self.assertLess(name_idf["India"]["limited"], name_idf["India"]["reliance"])

    def test_token_resource_serialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            res = TokenResource(
                name_idf={"US": {"apple": 5.2, "inc": 1.1}, "global": {"apple": 5.0}},
                address_idf={"US": {"street": 1.2}},
                boilerplate_tokens={"US": {"inc", "street"}},
            )
            res.save(p)

            loaded = TokenResource.load(p)
            self.assertTrue(loaded.is_boilerplate("inc", "US"))
            self.assertFalse(loaded.is_boilerplate("apple", "US"))
            self.assertEqual(loaded.get_name_idf("apple", "US"), 5.2)


if __name__ == "__main__":
    unittest.main()
