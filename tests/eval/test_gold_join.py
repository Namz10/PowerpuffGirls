import tempfile
import unittest
from pathlib import Path

from src.eval.gold_join import build, entity_script


class EntityScriptTests(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(entity_script(["latin", "indic"]), "indic")
        self.assertEqual(entity_script(["latin", "accented_latin"]), "accented_latin")
        self.assertEqual(entity_script(["other", "latin"]), "latin")
        self.assertEqual(entity_script([]), "")

    def test_other_alone_fails(self):
        with self.assertRaises(ValueError):
            entity_script(["other"])


class BuildTests(unittest.TestCase):
    def test_missing_name_fails_and_join_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "loop_ids.txt").write_text("S1-1\nS1-2\n", encoding="utf-8")
            train = root / "train"
            train.mkdir()
            (train / "train_ground_truth.tsv").write_text(
                "source1_entity_id\tmatched_entity_ids\nS1-1\tS2-1\nS1-2\t\n",
                encoding="utf-8",
            )
            (train / "train_source2.tsv").write_text(
                "entity_id\tbusiness_name\tbusiness_address\tcountry\nS2-1\tCafé\t1\tUS\n",
                encoding="utf-8",
            )
            (train / "train_source3.tsv").write_text(
                "entity_id\tbusiness_name\tbusiness_address\tcountry\n",
                encoding="utf-8",
            )
            out = root / "out"
            first = build(root / "loop_ids.txt", train, out)
            second = build(root / "loop_ids.txt", train, out)
            self.assertEqual(first["artifacts"]["loop_script_join"]["sha256"], second["artifacts"]["loop_script_join"]["sha256"])
            body = (out / "loop_script_join.tsv").read_text(encoding="utf-8").splitlines()[1:]
            self.assertEqual(body[0].split("\t")[2], "accented_latin")
            self.assertEqual(body[1].split("\t")[2], "")
            (train / "train_source2.tsv").write_text(
                "entity_id\tbusiness_name\tbusiness_address\tcountry\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                build(root / "loop_ids.txt", train, out)


if __name__ == "__main__":
    unittest.main()
