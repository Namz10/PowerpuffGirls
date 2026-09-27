import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.blocking.index import sha256_file
from src.blocking.phase2 import build_phase2_index
from src.blocking.phase3 import generate_locked_report
from src.matching.decision_config import config_sha256, skeleton_config


HEADER = ["entity_id", "business_name", "business_address", "country"]


def write_tsv(path: Path, rows: list[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


class Phase3BlockingTest(unittest.TestCase):
    def test_locked_report_requires_matching_locked_config_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source1, source2, source3 = root / "s1.tsv", root / "s2.tsv", root / "s3.tsv"
            write_tsv(source1, [("S1-1", "Acme", "1 Main", "US")])
            write_tsv(source2, [("S2-1", "Acme", "1 Main", "US")])
            write_tsv(source3, [("S3-1", "Other", "2 Main", "US")])
            index = root / "index.sqlite"
            build_phase2_index((source2, source3), index)
            resources = root / "resources"
            resources.mkdir()
            boilerplate = resources / "boilerplate_tokens.json"
            boilerplate.write_text("{}\n", encoding="utf-8")
            loop_report = root / "loop_report.json"
            loop_report.write_text(json.dumps({"provenance_sha256": "p"}), encoding="utf-8")
            config = {
                "cap": 50, "source_floor": 2, "rescue_quota": 10, "exact_pool": 250,
                "token_posting_limit": 250, "ngram_posting_limit": 400, "max_tokens_per_field": 4,
            }
            config_hash = __import__("hashlib").sha256(
                json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            freeze = {
                "schema_version": "phase2-blocker-freeze-v1", "status": "frozen",
                "selection_split": "loop", "config": config, "config_sha256": config_hash,
                "index_sha256": sha256_file(index), "boilerplate_sha256": sha256_file(boilerplate),
                "normalizer_version": "2.0.0",
                "loop": {"entities": 25_000, "report_path": str(loop_report), "candidate_file_sha256": "c", "misses_sha256": "m"},
                "fit_400k": {"entities": 400_000, "candidate_file_sha256": "fit-hash"},
            }
            freeze_path = root / "freeze.json"
            freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
            ids = root / "report_ids.txt"
            ids.write_text("S1-1\n", encoding="utf-8")
            decision = skeleton_config()
            skeleton_path = root / "skeleton.json"
            skeleton_path.write_text(json.dumps(decision), encoding="utf-8")
            with self.assertRaises(ValueError):
                generate_locked_report(
                    freeze_path=freeze_path, decision_config_path=skeleton_path, index_path=index,
                    source1_path=source1, report_ids_path=ids, resources_path=resources,
                    output_path=root / "c.tsv", provenance_path=root / "p.tsv", report_path=root / "r.json",
                    manifest_path=root / "m.json",
                )
            decision.update({"status": "locked", "fit_400k_candidate_sha256": "fit-hash", "fit_400k_entity_count": 400_000})
            decision["sha256"] = config_sha256(decision)
            decision_path = root / "decision.json"
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            with patch("src.eval.config.split_dir", return_value=root):
                manifest = generate_locked_report(
                    freeze_path=freeze_path, decision_config_path=decision_path, index_path=index,
                    source1_path=source1, report_ids_path=ids, resources_path=resources,
                    output_path=root / "c.tsv", provenance_path=root / "p.tsv", report_path=root / "r.json",
                    manifest_path=root / "m.json",
                )
            self.assertEqual(manifest["status"], "locked")
            self.assertEqual(manifest["entities"], 1)
            self.assertEqual(manifest["decision_config_sha256"], decision["sha256"])
            self.assertTrue((root / "m.json").is_file())


if __name__ == "__main__":
    unittest.main()
