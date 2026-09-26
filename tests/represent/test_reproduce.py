"""Unit test for canonical artifact reproduction and byte-stability."""

import json
import unittest
from src.eval.fingerprint import sha256_file
from src.represent.config import resource_dir


class ReproductionContractTests(unittest.TestCase):
    def test_manifest_fingerprints_match_disk_artifacts(self):
        res_d = resource_dir()
        manifest_path = res_d / "manifest.json"
        self.assertTrue(manifest_path.exists(), "Manifest file must exist")

        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        for resource_name, info in manifest["resources"].items():
            artifact_file = res_d / f"{resource_name}.json"
            self.assertTrue(artifact_file.exists(), f"Resource {artifact_file} must exist")
            actual_sha256 = sha256_file(artifact_file)
            self.assertEqual(
                actual_sha256,
                info["sha256"],
                f"SHA-256 fingerprint mismatch for {resource_name}",
            )


if __name__ == "__main__":
    unittest.main()
