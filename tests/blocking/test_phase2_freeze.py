import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.blocking.phase2_freeze import (
    build_fit_sample,
    build_freeze_manifest,
    validate_loop_report,
)


def write_tsv(path: Path, header: list[str], rows: list[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


class Phase2FreezeTest(unittest.TestCase):
    def test_fit_sample_is_deterministic_hashed_and_fit_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source1 = root / "source1.tsv"
            truth = root / "truth.tsv"
            fit = root / "fit.txt"
            loop = root / "loop.txt"
            report = root / "report.txt"
            rows = [
                ("S1-1", "A", "", "India"),
                ("S1-2", "B", "", "India"),
                ("S1-3", "C", "", "US"),
                ("S1-4", "D", "", "US"),
            ]
            write_tsv(
                source1,
                ["entity_id", "business_name", "business_address", "country"],
                rows,
            )
            write_tsv(
                truth,
                ["source1_entity_id", "matched_entity_ids"],
                [(row[0], "") for row in rows],
            )
            fit.write_text("S1-1\nS1-2\nS1-3\nS1-4\n", encoding="utf-8")
            loop.write_text("S1-loop\n", encoding="utf-8")
            report.write_text("S1-report\n", encoding="utf-8")
            output1, output2 = root / "sample1.txt", root / "sample2.txt"
            manifest1, manifest2 = root / "sample1.json", root / "sample2.json"
            first = build_fit_sample(
                output1, manifest1, source1, truth, fit, loop, report, total=2, seed=7
            )
            second = build_fit_sample(
                output2, manifest2, source1, truth, fit, loop, report, total=2, seed=7
            )
            self.assertEqual(output1.read_text(), output2.read_text())
            self.assertEqual(first["output"]["sha256"], second["output"]["sha256"])
            self.assertEqual(first["count"], 2)
            self.assertEqual(sum(first["stratum_counts"].values()), 2)

    def test_loop_guardrails_are_mandatory(self):
        report = {
            "selection_split": "loop",
            "entities": 25_000,
            "promotion_check": {
                "selected_point_on_pareto_frontier": True,
                "bootstrap_lower_bound_above_zero": True,
                "eligible": True,
            },
        }
        validate_loop_report(report)
        report["promotion_check"]["eligible"] = False
        with self.assertRaises(ValueError):
            validate_loop_report(report)

    def test_freeze_binds_matching_config_index_and_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop_path = root / "loop.json"
            sample_path = root / "sample.json"
            fit_path = root / "fit.json"
            output = root / "frozen.json"
            loop = {
                "selection_split": "loop",
                "entities": 25_000,
                "promotion_check": {
                    "selected_point_on_pareto_frontier": True,
                    "bootstrap_lower_bound_above_zero": True,
                    "eligible": True,
                },
                "config": {"cap": 50, "source_floor": 2, "rescue_quota": 10},
                "config_sha256": "config",
                "normalizer_version": "2.0.0",
                "index_sha256": "index",
                "boilerplate_sha256": "tokens",
                "candidate_file_sha256": "loop-candidates",
                "misses_sha256": "misses",
            }
            sample = {"count": 400_000, "output": {"sha256": "ids"}}
            fit = {
                "entities": 400_000,
                "truth_sha256": None,
                "config_sha256": "config",
                "requested_ids_sha256": "ids",
                "normalizer_version": "2.0.0",
                "index_sha256": "index",
                "boilerplate_sha256": "tokens",
                "candidate_file": "fit.tsv",
                "candidate_file_sha256": "fit-candidates",
                "provenance_sha256": "provenance",
                "elapsed_seconds": 1.0,
                "peak_rss_kib": 100,
            }
            for path, value in ((loop_path, loop), (sample_path, sample), (fit_path, fit)):
                path.write_text(json.dumps(value), encoding="utf-8")
            frozen = build_freeze_manifest(loop_path, sample_path, fit_path, output)
            self.assertEqual(frozen["status"], "frozen")
            self.assertEqual(frozen["fit_400k"]["entities"], 400_000)
            fit["config_sha256"] = "different"
            fit_path.write_text(json.dumps(fit), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_freeze_manifest(loop_path, sample_path, fit_path, output)


if __name__ == "__main__":
    unittest.main()
