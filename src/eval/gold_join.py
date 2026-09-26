"""Gold-join Unicode script classes for frozen loop Source 1 ids."""

import json
from pathlib import Path

from src.eval.config import REPO_ROOT, SEED, train_dir
from src.eval.difficulty_pack import script_class
from src.eval.fingerprint import sha256_file

ENTITY_HEADER = "source1_entity_id\tgold_list_length\tscript_class\tindic_targets\taccented_latin_targets"
TARGET_HEADER = "source1_entity_id\ttarget_entity_id\tscript_class"


def entity_script(target_classes: list[str]) -> str:
    """indic beats accented Latin, which beats Latin. other never wins."""
    if any(item == "indic" for item in target_classes):
        return "indic"
    if any(item == "accented_latin" for item in target_classes):
        return "accented_latin"
    if any(item == "latin" for item in target_classes):
        return "latin"
    if target_classes:
        raise ValueError("gold targets have no latin, accented_latin, or indic name")
    return ""


def _rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        header = handle.readline()
        if "\t" not in header:
            raise ValueError(f"{path.name} is not tab-separated")
        for line in handle:
            if line.strip():
                yield line.rstrip("\n").split("\t")


def build(loop_ids_path: Path, train: Path, out_dir: Path) -> dict:
    loop_ids = loop_ids_path.read_text(encoding="utf-8").splitlines()
    if len(loop_ids) != len(set(loop_ids)):
        raise ValueError("loop ids are not unique")
    wanted = set(loop_ids)
    gold: dict[str, list[str]] = {}
    needed: set[str] = set()
    for parts in _rows(train / "train_ground_truth.tsv"):
        if parts[0] not in wanted:
            continue
        raw = parts[1].strip() if len(parts) > 1 else ""
        matched = raw.split(",") if raw else []
        gold[parts[0]] = matched
        needed.update(matched)
    if set(gold) != wanted:
        raise ValueError("gold rows do not cover the loop ids")

    names: dict[str, str] = {}
    for filename in ("train_source2.tsv", "train_source3.tsv"):
        for parts in _rows(train / filename):
            if parts[0] in needed and parts[0] not in names:
                if len(parts) < 2:
                    raise ValueError(f"missing target name for {parts[0]}")
                names[parts[0]] = parts[1]
    missing = needed - set(names)
    if missing:
        sample = sorted(missing)[:5]
        raise ValueError(f"missing target name for {sample}")

    entity_lines = [ENTITY_HEADER]
    target_lines = [TARGET_HEADER]
    counts = {"": 0, "latin": 0, "accented_latin": 0, "indic": 0}
    for source_id in loop_ids:
        matched = gold[source_id]
        classes = []
        indic_n = accented_n = 0
        for target_id in matched:
            kind = script_class(names[target_id])
            classes.append(kind)
            if kind == "indic":
                indic_n += 1
            elif kind == "accented_latin":
                accented_n += 1
            target_lines.append(f"{source_id}\t{target_id}\t{kind}")
        label = entity_script(classes)
        counts[label] = counts.get(label, 0) + 1
        entity_lines.append(f"{source_id}\t{len(matched)}\t{label}\t{indic_n}\t{accented_n}")

    out_dir.mkdir(parents=True, exist_ok=True)
    entity_path = out_dir / "loop_script_join.tsv"
    target_path = out_dir / "loop_script_targets.tsv"
    entity_path.write_text("\n".join(entity_lines) + "\n", encoding="utf-8", newline="\n")
    target_path.write_text("\n".join(target_lines) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "seed": SEED,
        "loop_rows": len(loop_ids),
        "target_rows": len(target_lines) - 1,
        "script_counts": counts,
        "inputs": {
            "loop_ids": {"path": "src/eval/splits/loop_ids.txt", "sha256": sha256_file(loop_ids_path)},
            "train_ground_truth": {
                "path": "../student_resource/dataset/train/train_ground_truth.tsv",
                "sha256": sha256_file(train / "train_ground_truth.tsv"),
            },
            "train_source2": {
                "path": "../student_resource/dataset/train/train_source2.tsv",
                "sha256": sha256_file(train / "train_source2.tsv"),
            },
            "train_source3": {
                "path": "../student_resource/dataset/train/train_source3.tsv",
                "sha256": sha256_file(train / "train_source3.tsv"),
            },
        },
        "artifacts": {
            "loop_script_join": {
                "path": "artifacts/eval/phase2/loop_script_join.tsv",
                "sha256": sha256_file(entity_path),
            },
            "loop_script_targets": {
                "path": "artifacts/eval/phase2/loop_script_targets.tsv",
                "sha256": sha256_file(target_path),
            },
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main() -> None:
    out = REPO_ROOT / "artifacts" / "eval" / "phase2"
    manifest = build(REPO_ROOT / "src" / "eval" / "splits" / "loop_ids.txt", train_dir(), out)
    print(json.dumps({"loop_rows": manifest["loop_rows"], "script_counts": manifest["script_counts"]}))


if __name__ == "__main__":
    main()
