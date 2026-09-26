import json
import unittest

from src.eval import slice_schema


class SliceSchemaTests(unittest.TestCase):
    def test_schema_validates(self):
        slice_schema.validate(slice_schema.schema())

    def test_expected_keys_present(self):
        keys = {entry["key"] for entry in slice_schema.schema()["slices"]}
        expected = {
            "country",
            "singleton",
            "gold_list_bucket",
            "target_empty_address",
            "source_composition",
            "short_name",
            "generic_name",
            "target_script_class",
            "cross_country_prediction",
            "false_id_type",
            "predicted_vs_gold_length",
        }
        self.assertEqual(keys, expected)

    def test_phase1_slices_are_entity_level(self):
        for entry in slice_schema.schema()["slices"]:
            if entry["phase_available"] == "phase1":
                self.assertEqual(entry["level"], "entity", entry["key"])

    def test_unfrozen_name_cutoffs_flagged(self):
        by_key = {entry["key"]: entry for entry in slice_schema.schema()["slices"]}
        self.assertFalse(by_key["short_name"]["parameters"]["frozen"])
        self.assertFalse(by_key["generic_name"]["parameters"]["frozen"])

    def test_gold_join_and_prediction_slices_marked(self):
        by_key = {entry["key"]: entry for entry in slice_schema.schema()["slices"]}
        self.assertEqual(by_key["target_script_class"]["phase_available"], "after_gold_join")
        self.assertEqual(by_key["target_script_class"]["categories"], ["latin", "accented_latin", "indic"])
        for key in ("cross_country_prediction", "false_id_type", "predicted_vs_gold_length"):
            self.assertEqual(by_key[key]["phase_available"], "prediction_time")
            self.assertEqual(by_key[key]["level"], "prediction")

    def test_canonical_bytes_are_deterministic_and_utf8(self):
        first = slice_schema.canonical_bytes()
        second = slice_schema.canonical_bytes()
        self.assertEqual(first, second)
        parsed = json.loads(first.decode("utf-8"))
        self.assertEqual(parsed["schema_version"], slice_schema.SCHEMA_VERSION)

    def test_validate_rejects_bad_documents(self):
        with self.assertRaises(ValueError):
            slice_schema.validate({"schema_version": "0", "slices": []})
        with self.assertRaises(ValueError):
            slice_schema.validate(
                {
                    "schema_version": slice_schema.SCHEMA_VERSION,
                    "slices": [
                        {
                            "key": "x", "description": "", "level": "bad",
                            "phase_available": "phase1", "value_type": "boolean",
                            "categories": [], "open_set": False,
                            "source_fields": ["a"], "parameters": {},
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
