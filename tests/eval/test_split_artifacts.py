"""Freeze contract over the committed split artifacts.

These tests read only the checked-in files under src/eval/splits/. They do not
load the training data, so they are fast and encode the "freeze + fingerprint +
reproducibility" contract: the published id files must stay internally
consistent with manifest.json (fingerprints, disjointness, coverage, the 25,000
loop, per-stratum floor-10% report), or a later edit that silently redraws the
split will fail here instead of passing unnoticed.
"""

import json
import unittest

from src.eval.config import LOOP_SIZE, REPORT_PERCENT, split_dir
from src.eval.fingerprint import sha256_file

SPLITS = split_dir()
MANIFEST = json.loads((SPLITS / "manifest.json").read_text(encoding="utf-8"))


def _ids(name: str) -> list[str]:
    return (SPLITS / f"{name}_ids.txt").read_text(encoding="utf-8").splitlines()


class CommittedArtifactTests(unittest.TestCase):
    def test_fingerprints_match_committed_bytes(self):
        for name in ("fit", "loop", "report"):
            digest = sha256_file(SPLITS / f"{name}_ids.txt")
            self.assertEqual(digest, MANIFEST["artifacts"][name]["sha256"], name)

    def test_counts_match_manifest_and_loop_is_25000(self):
        for name in ("fit", "loop", "report"):
            self.assertEqual(len(_ids(name)), MANIFEST["artifacts"][name]["count"], name)
            self.assertEqual(len(_ids(name)), MANIFEST["counts"][name], name)
        self.assertEqual(MANIFEST["counts"]["loop"], LOOP_SIZE)

    def test_disjoint_complete_sorted_and_all_source1(self):
        seen: set[str] = set()
        union = 0
        for name in ("fit", "loop", "report"):
            ids = _ids(name)
            self.assertEqual(ids, sorted(ids), f"{name} not sorted")
            self.assertTrue(all(i.startswith("S1-") for i in ids), f"{name} has non-S1 id")
            self.assertEqual(len(ids), len(set(ids)), f"{name} has an internal duplicate")
            self.assertTrue(seen.isdisjoint(ids), f"{name} overlaps another split")
            seen.update(ids)
            union += len(ids)
        self.assertEqual(union, len(seen), "splits overlap")
        self.assertEqual(len(seen), MANIFEST["counts"]["source1"])

    def test_manifest_strata_obey_floor10_and_loop_budget(self):
        loop_total = 0
        for row in MANIFEST["strata"]:
            self.assertEqual(row["report"], (row["size"] * REPORT_PERCENT) // 100)
            self.assertEqual(row["fit"] + row["loop"] + row["report"], row["size"])
            loop_total += row["loop"]
        self.assertEqual(loop_total, LOOP_SIZE)
        self.assertEqual(
            sum(row["size"] for row in MANIFEST["strata"]),
            MANIFEST["counts"]["source1"],
        )

    def test_seed_recorded(self):
        self.assertEqual(MANIFEST["seed"], 42)


if __name__ == "__main__":
    unittest.main()
