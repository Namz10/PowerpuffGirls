import tempfile
import unittest
from pathlib import Path

from src.eval import difficulty_pack as dp


class HelperTests(unittest.TestCase):
    def test_tokenize_and_jaccard(self):
        self.assertEqual(dp.tokenize("A&B  Corp."), ["a", "b", "corp"])
        self.assertEqual(dp.jaccard(frozenset("ab"), frozenset("ab")), 1.0)
        self.assertEqual(dp.jaccard(frozenset("a"), frozenset("b")), 0.0)
        self.assertEqual(dp.jaccard(frozenset(), frozenset()), 0.0)

    def test_overlap_bucket_edges(self):
        self.assertEqual(dp.overlap_bucket(0.0), "none")
        self.assertEqual(dp.overlap_bucket(0.2), "low")
        self.assertEqual(dp.overlap_bucket(0.5), "mid")
        self.assertEqual(dp.overlap_bucket(0.9), "high")

    def test_script_class(self):
        self.assertEqual(dp.script_class("Acme Foods"), "latin")
        self.assertEqual(dp.script_class("Límited Nétwork"), "accented_latin")
        self.assertEqual(dp.script_class("शक्ति"), "indic")          # Devanagari
        self.assertEqual(dp.script_class("குளோபல்"), "indic")        # Tamil

    def test_legal_variant(self):
        self.assertTrue(dp.is_legal_variant("Acme Corp", "Acme Corporation"))
        self.assertTrue(dp.is_legal_variant("Acme Foods Pvt Ltd", "Foods Acme Private Limited"))
        self.assertFalse(dp.is_legal_variant("Acme Corp", "Beta Corp"))
        self.assertFalse(dp.is_legal_variant("Acme Corp", "Acme Corp"))


def _write(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "".join(r + "\n" for r in rows), encoding="utf-8", newline="\n")


class SyntheticBuildTests(unittest.TestCase):
    def _dataset(self, root: Path) -> tuple[Path, Path]:
        train = root / "train"
        train.mkdir()
        s1, s2, s3 = [], [], []
        gold = []
        fit_ids = []
        # easy_latin + legal_suffix + low_overlap + accented + indic + empty-addr + multi
        # Build several non-singletons.
        def add_s1(i, name, addr, country):
            eid = f"S1-{i:05d}"
            s1.append(f"{eid}\t{name}\t{addr}\t{country}")
            fit_ids.append(eid)
            return eid

        # easy latin: near-identical name+addr
        e1 = add_s1(1, "Acme Foods", "12 Main Road", "US")
        s2.append("S2-00001\tAcme Foods\t12 Main Road\tUS")
        gold.append(f"{e1}\tS2-00001")
        # legal suffix
        e2 = add_s1(2, "Beta Corp", "9 Oak Street", "US")
        s2.append("S2-00002\tBeta Corporation\t9 Oak Street\tUS")
        gold.append(f"{e2}\tS2-00002")
        # low overlap gold pair
        e3 = add_s1(3, "Zeta Traders", "88 Lake Ave", "India")
        s3.append("S3-00003\tOm Enterprises\tNear SBI ATM\tIndia")
        gold.append(f"{e3}\tS3-00003")
        # accented latin target
        e4 = add_s1(4, "Prime Solar", "5 Sun Lane", "India")
        s2.append("S2-00004\tPrime Sólar\t5 Sun Lane\tIndia")
        gold.append(f"{e4}\tS2-00004")
        # indic target
        e5 = add_s1(5, "Shakti Urban", "7 Hill Rd", "India")
        s2.append("S2-00005\tशक्ति अर्बन\t7 Hill Rd\tIndia")
        gold.append(f"{e5}\tS2-00005")
        # empty-address match
        e6 = add_s1(6, "Delta Works", "3 River Rd", "US")
        s3.append("S3-00006\tDelta Works\t\tUS")
        gold.append(f"{e6}\tS3-00006")
        # multi-id length 4
        e7 = add_s1(7, "Multi Chain", "1 First St", "US")
        for k in range(4):
            s2.append(f"S2-0007{k}\tMulti Chain {k}\t1 First St\tUS")
        gold.append(f"{e7}\tS2-00070,S2-00071,S2-00072,S2-00073")
        # non-match lookalike distractor for a non-singleton with a gold elsewhere
        e8 = add_s1(8, "Union Textiles", "4 Cotton St", "US")
        s2.append("S2-00008\tUnion Textiles\t4 Cotton St\tUS")  # gold
        gold.append(f"{e8}\tS2-00008")
        s3.append("S3-09999\tUnion Textiles\t4 Cotton St\tUS")  # gold for nobody -> distractor
        # stolen neighbourhood: e9 shares name with a target owned by e10
        e9 = add_s1(9, "Peak Systems", "2 Ridge Rd", "US")
        s2.append("S2-00009\tPeak Systems\t2 Ridge Rd\tUS")
        gold.append(f"{e9}\tS2-00009")
        e10 = add_s1(10, "Peak Systems", "99 Faraway Rd", "US")
        s2.append("S2-00010\tPeak Systems\t99 Faraway Rd\tUS")  # owned by e10
        gold.append(f"{e10}\tS2-00010")
        # singleton with lookalike
        e11 = add_s1(11, "Lonely Cafe", "6 Bean St", "US")
        s3.append("S3-00011\tLonely Cafe\t6 Bean St\tUS")  # gold for nobody
        gold.append(f"{e11}\t")
        # singleton isolated
        e12 = add_s1(12, "Zzxqv Uniqueburg", "0 Nowhere", "US")
        gold.append(f"{e12}\t")

        _write(train / "train_source1.tsv", "entity_id\tbusiness_name\tbusiness_address\tcountry", s1)
        _write(train / "train_source2.tsv", "entity_id\tbusiness_name\tbusiness_address\tcountry", s2)
        _write(train / "train_source3.tsv", "entity_id\tbusiness_name\tbusiness_address\tcountry", s3)
        _write(train / "train_ground_truth.tsv", "source1_entity_id\tmatched_entity_ids", gold)
        fit_path = root / "fit_ids.txt"
        fit_path.write_text("".join(sorted(f"{i}\n" for i in fit_ids)), encoding="utf-8", newline="\n")
        return train, fit_path

    def test_build_produces_valid_deterministic_pack(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            train, fit_path = self._dataset(root)
            out1 = root / "pack1"
            out2 = root / "pack2"
            kw = dict(train=train, fit_ids_path=fit_path, per_kind=1, nonsingleton_probes=100, singleton_probes=100)
            m1 = dp.build(out_dir=out1, **kw)
            m2 = dp.build(out_dir=out2, **kw)
            text1 = (out1 / "pack.tsv").read_text(encoding="utf-8")
            text2 = (out2 / "pack.tsv").read_text(encoding="utf-8")
            self.assertEqual(text1, text2)  # deterministic
            self.assertEqual(m1["artifacts"]["pack"]["sha256"], m2["artifacts"]["pack"]["sha256"])

            lines = text1.splitlines()
            self.assertEqual(lines[0], "source1_entity_id\trelated_entity_ids\tkind\toverlap_bucket\treason")
            body = lines[1:]
            s1_ids = [ln.split("\t")[0] for ln in body]
            self.assertEqual(len(s1_ids), len(set(s1_ids)))  # no duplicate Source 1 id
            for ln in body:
                cols = ln.split("\t")
                self.assertEqual(len(cols), 5)
                self.assertTrue(cols[0].startswith("S1-"))
                self.assertIn(cols[2], dp.KINDS)
                for rid in (cols[1].split(",") if cols[1] else []):
                    self.assertTrue(rid.startswith(("S2-", "S3-")))
            # rows sorted by (kind order, id)
            keyed = [(dp.KINDS.index(ln.split("\t")[2]), ln.split("\t")[0]) for ln in body]
            self.assertEqual(keyed, sorted(keyed))

    def test_pack_ids_are_from_fit_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            train, fit_path = self._dataset(root)
            out = root / "pack"
            dp.build(train=train, fit_ids_path=fit_path, out_dir=out, per_kind=1,
                     nonsingleton_probes=100, singleton_probes=100)
            fit = set(fit_path.read_text(encoding="utf-8").splitlines())
            body = (out / "pack.tsv").read_text(encoding="utf-8").splitlines()[1:]
            for ln in body:
                self.assertIn(ln.split("\t")[0], fit)


if __name__ == "__main__":
    unittest.main()
