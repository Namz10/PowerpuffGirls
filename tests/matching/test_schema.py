import unittest

from src.matching.features_raw import FEATURE_NAMES
from src.matching.features_v2 import (
    PHASE2_FEATURE_NAMES,
    idf_overlap,
    phase2_feature_row,
    postal_flags,
    schema_sha256,
)
from src.matching.invoke_blocker import command
from src.represent.canonical_record import CanonicalRecord


class _Tokens:
    def get_name_idf(self, token, country="global"):
        return 2.0 if token == "acme" else 10.0

    def get_address_idf(self, token, country="global"):
        return 3.0


def _record(**overrides):
    values = dict(
        entity_id="S1-1",
        source="source1",
        country="US",
        normalized_name="acme",
        romanized_name="acme",
        accent_folded_name="acme",
        normalized_address="1 main street",
        source_script="latin",
        postal_code="12345",
        is_empty_address=False,
        has_landmark_ref=False,
        is_cedex=False,
        name_tokens=["acme"],
        address_tokens=["main"],
    )
    values.update(overrides)
    return CanonicalRecord(**values)


class SchemaTests(unittest.TestCase):
    def test_schema_hash_is_stable_and_keeps_phase1_prefix(self):
        self.assertEqual(schema_sha256(), schema_sha256())
        self.assertEqual(len(schema_sha256()), 64)

    def test_postal_missing_and_conflict(self):
        self.assertEqual(postal_flags(None, "12345"), (0.0, 0.0, 1.0))
        self.assertEqual(postal_flags("12345", "99999"), (0.0, 1.0, 0.0))

    def test_phase2_row_width_and_script(self):
        left = _record()
        right = _record(entity_id="S2-1", source="source2", source_script="devanagari", postal_code="12345")
        row = phase2_feature_row(left, right, _Tokens())
        self.assertEqual(len(row), len(PHASE2_FEATURE_NAMES))
        self.assertEqual(row[PHASE2_FEATURE_NAMES.index("postal_equal")], 1.0)
        self.assertEqual(row[PHASE2_FEATURE_NAMES.index("same_script")], 0.0)
        self.assertGreater(idf_overlap(["acme"], ["acme"], "US", _Tokens().get_name_idf), 0)

    def test_phase1_names_are_the_raw_contract(self):
        self.assertEqual(FEATURE_NAMES[0], "name_jaccard")
        self.assertEqual(FEATURE_NAMES[-1], "src_is_s3")

    def test_blocker_invocation_is_the_existing_cli(self):
        argv = command(["generate", "--cap", "50"])
        self.assertEqual(argv[1:4], ["-m", "src.blocking.cli", "generate"])
        self.assertNotIn("--sweep", argv)


if __name__ == "__main__":
    unittest.main()
