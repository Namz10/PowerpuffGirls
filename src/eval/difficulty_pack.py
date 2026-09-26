"""Difficulty pack — Person 1 Phase 1.

A frozen, reading-only TSV of about 330 `fit`-only Source 1 entities, 11 documented
kinds x 30. Source of truth for the kinds and columns:
- build_plan_person1.md "Difficulty pack" table (lines 223-243);
- consolidated plan section 3 ("Difficulty pack: ... Counts of 30: ...").

Columns (exactly as documented): source1_entity_id, related_entity_ids, kind,
overlap_bucket, reason.

The pack is drawn from `fit` only (never `loop`/`report`), never resampled, and is
for reading, not for choosing a threshold. Near-miss and singleton-lookalike kinds
use a cheap same-country token-overlap miner that is explicitly NOT Person 3's
blocker and is not exported as one. This module computes no recall, oracle, width,
or bootstrap number; it only selects example entities.
"""

import json
from pathlib import Path

from src.eval.config import (
    PACK_DIR_RELATIVE,
    PACK_PER_KIND,
    REPO_ROOT,
    SEED,
    SPLIT_DIR_RELATIVE,
    TRAIN_DIR_RELATIVE,
    pack_dir,
    train_dir,
)
from src.eval.fingerprint import sha256_file

# Fixed kind order. Filling is greedy in this order; each Source 1 id is used once.
KINDS = [
    "easy_latin",
    "legal_suffix",
    "low_overlap",
    "accented_latin",
    "indic_other_side",
    "empty_address_match",
    "multi_id",
    "unmatched_distractor_near_miss",
    "stolen_neighborhood_near_miss",
    "singleton_lookalike",
    "singleton_isolated",
]

LEGAL_TOKENS = frozenset(
    {
        "corp", "corporation", "pvt", "private", "ltd", "limited", "inc",
        "incorporated", "llc", "co", "company", "plc", "gmbh", "sarl", "sa",
        "sas", "bv", "and", "the",
    }
)

# Indic Unicode blocks used only to classify a target name's script for the pack.
_INDIC_RANGES = (
    (0x0900, 0x097F),  # Devanagari
    (0x0980, 0x09FF),  # Bengali
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
)

# Miner bounds (cheap, deterministic; not a blocker).
DF_CAP = 200          # a probe token rarer than this is usable for overlap search
POST_CAP = 50         # postings kept per usable token
NEAR_MISS_MIN = 0.5   # Jaccard for a "high overlap" near miss / lookalike
ISOLATED_MAX = 0.10   # best neighbour below this counts as "nothing nearby"
LOW_OVERLAP_MAX = 0.10
EASY_NAME_MIN = 0.70
EASY_ADDR_MIN = 0.30

DEFAULT_NONSINGLETON_PROBES = 40_000
DEFAULT_SINGLETON_PROBES = 12_000


def tokenize(text: str) -> list[str]:
    tokens, current = [], []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def token_set(text: str) -> frozenset[str]:
    return frozenset(tokenize(text))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def overlap_bucket(value: float) -> str:
    if value <= 0.0:
        return "none"
    if value < 0.30:
        return "low"
    if value < 0.70:
        return "mid"
    return "high"


def script_class(name: str) -> str:
    has_indic = has_non_ascii_letter = has_ascii_letter = False
    for char in name:
        code = ord(char)
        if any(lo <= code <= hi for lo, hi in _INDIC_RANGES):
            has_indic = True
        elif code > 0x7F and char.isalpha():
            has_non_ascii_letter = True
        elif char.isalpha():
            has_ascii_letter = True
    if has_indic:
        return "indic"
    if has_non_ascii_letter:
        return "accented_latin"
    if has_ascii_letter:
        return "latin"
    return "other"


def is_legal_variant(a_name: str, b_name: str) -> bool:
    """Names differ only by legal-suffix / punctuation / word order."""
    core_a = token_set(a_name) - LEGAL_TOKENS
    core_b = token_set(b_name) - LEGAL_TOKENS
    if not core_a or core_a != core_b:
        return False
    return a_name.strip().casefold() != b_name.strip().casefold()


def _rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        handle.readline()  # header
        for line in handle:
            if not line.strip():
                continue
            yield line.rstrip("\n").split("\t")


def _read_ids(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _load_gold(gold_path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    gold: dict[str, list[str]] = {}
    owner: dict[str, str] = {}
    for parts in _rows(gold_path):
        s1 = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        matched = rest.split(",") if rest else []
        gold[s1] = matched
        for target in matched:
            owner[target] = s1
    return gold, owner


def _select(eligible_by_kind: dict[str, list[tuple]], per_kind: int) -> list[dict]:
    """Greedy, deterministic assignment. Each Source 1 id is used at most once."""
    used: set[str] = set()
    rows: list[dict] = []
    for kind in KINDS:
        picked = 0
        for s1, related, bucket, reason in eligible_by_kind.get(kind, []):
            if s1 in used:
                continue
            used.add(s1)
            rows.append(
                {
                    "source1_entity_id": s1,
                    "related_entity_ids": ",".join(related),
                    "kind": kind,
                    "overlap_bucket": bucket,
                    "reason": reason,
                }
            )
            picked += 1
            if picked >= per_kind:
                break
    rows.sort(key=lambda row: (KINDS.index(row["kind"]), row["source1_entity_id"]))
    return rows


def build(
    train: Path | None = None,
    fit_ids_path: Path | None = None,
    out_dir: Path | None = None,
    per_kind: int = PACK_PER_KIND,
    nonsingleton_probes: int = DEFAULT_NONSINGLETON_PROBES,
    singleton_probes: int = DEFAULT_SINGLETON_PROBES,
) -> dict:
    train = train or train_dir()
    fit_ids_path = fit_ids_path or (REPO_ROOT / SPLIT_DIR_RELATIVE / "fit_ids.txt")
    out_dir = out_dir or pack_dir()
    source1 = train / "train_source1.tsv"
    source2 = train / "train_source2.tsv"
    source3 = train / "train_source3.tsv"
    gold_path = train / "train_ground_truth.tsv"

    fit_ids = set(_read_ids(fit_ids_path))
    gold, owner = _load_gold(gold_path)

    fit_sorted = sorted(fit_ids)
    nonsingleton = [s1 for s1 in fit_sorted if len(gold.get(s1, [])) >= 1][:nonsingleton_probes]
    singleton = [s1 for s1 in fit_sorted if len(gold.get(s1, [])) == 0][:singleton_probes]
    probe_ids = set(nonsingleton) | set(singleton)

    # Source 1 text for the probes.
    s1_text: dict[str, tuple[str, str, str]] = {}
    for parts in _rows(source1):
        if parts[0] in probe_ids:
            s1_text[parts[0]] = (parts[1], parts[2], parts[3])

    needed_targets = set()
    for s1 in nonsingleton:
        needed_targets.update(gold.get(s1, []))

    probe_tokens: set[str] = set()
    for s1 in probe_ids:
        name = s1_text.get(s1, ("", "", ""))[0]
        probe_tokens.update(token_set(name))

    # One combined pass over Source 2 and Source 3.
    target_text: dict[str, tuple[str, str, str]] = {}
    df: dict[str, int] = {}
    postings: dict[str, list[tuple[str, str, frozenset]]] = {}
    for source_file in (source2, source3):
        for parts in _rows(source_file):
            if len(parts) < 4:
                continue
            tid, tname, taddr, tcountry = parts[0], parts[1], parts[2], parts[3]
            if tid in needed_targets:
                target_text[tid] = (tname, taddr, tcountry)
            shared = token_set(tname) & probe_tokens
            if not shared:
                continue
            tokens = token_set(tname)
            for tok in shared:
                df[tok] = df.get(tok, 0) + 1
                bucket = postings.setdefault(tok, [])
                if len(bucket) < POST_CAP:
                    bucket.append((tid, tcountry, tokens))

    usable_tokens = {tok for tok, count in df.items() if count <= DF_CAP}

    def neighbours(s1: str):
        name, _, country = s1_text.get(s1, ("", "", ""))
        s1_tokens = token_set(name)
        seen: dict[str, float] = {}
        payload: dict[str, tuple[str, frozenset]] = {}
        for tok in s1_tokens & usable_tokens:
            for tid, tcountry, ttokens in postings.get(tok, []):
                if tcountry != country:
                    continue
                if tid not in seen:
                    seen[tid] = jaccard(s1_tokens, ttokens)
                    payload[tid] = (tcountry, ttokens)
        return sorted(seen.items(), key=lambda item: (-item[1], item[0])), payload

    eligible: dict[str, list[tuple]] = {kind: [] for kind in KINDS}

    for s1 in nonsingleton:
        name = s1_text.get(s1, ("", "", ""))[0]
        addr = s1_text.get(s1, ("", "", ""))[1]
        s1_name_tokens = token_set(name)
        s1_addr_tokens = token_set(addr)
        matched = gold.get(s1, [])
        matched_set = set(matched)
        # gold-derived kinds
        for tid in matched:
            text = target_text.get(tid)
            if not text:
                continue
            tname, taddr, _ = text
            tname_tokens = token_set(tname)
            score = jaccard(s1_name_tokens, tname_tokens)
            scls = script_class(tname)
            if scls == "latin" and score >= EASY_NAME_MIN and taddr.strip() and jaccard(
                s1_addr_tokens, token_set(taddr)
            ) >= EASY_ADDR_MIN:
                eligible["easy_latin"].append((s1, [tid], overlap_bucket(score), f"latin near-exact j={score:.2f}"))
            if is_legal_variant(name, tname):
                eligible["legal_suffix"].append((s1, [tid], overlap_bucket(score), "legal-suffix/word-order variant"))
            if score <= LOW_OVERLAP_MAX:
                eligible["low_overlap"].append((s1, [tid], overlap_bucket(score), f"gold pair low overlap j={score:.2f}"))
            if scls == "accented_latin":
                eligible["accented_latin"].append((s1, [tid], "na", "accented-latin target name"))
            if scls == "indic":
                eligible["indic_other_side"].append((s1, [tid], "na", "indic target name vs latin source1"))
            if not taddr.strip():
                eligible["empty_address_match"].append((s1, [tid], "na", "gold target has empty address"))
        if len(matched) in (4, 5):
            eligible["multi_id"].append((s1, matched, "na", f"full gold list length {len(matched)}"))
        # near-miss kinds
        ranked, _ = neighbours(s1)
        for tid, score in ranked:
            if tid in matched_set or score < NEAR_MISS_MIN:
                continue
            who = owner.get(tid)
            if who is None:
                eligible["unmatched_distractor_near_miss"].append(
                    (s1, [tid], overlap_bucket(score), f"non-match lookalike j={score:.2f}")
                )
                break
        for tid, score in ranked:
            if tid in matched_set or score < NEAR_MISS_MIN:
                continue
            who = owner.get(tid)
            if who is not None and who != s1:
                eligible["stolen_neighborhood_near_miss"].append(
                    (s1, [tid], overlap_bucket(score), f"owned by {who} j={score:.2f}")
                )
                break

    for s1 in singleton:
        ranked, _ = neighbours(s1)
        best = ranked[0][1] if ranked else 0.0
        if ranked and best >= NEAR_MISS_MIN:
            tid = ranked[0][0]
            eligible["singleton_lookalike"].append((s1, [tid], overlap_bucket(best), f"singleton with lookalike j={best:.2f}"))
        elif best <= ISOLATED_MAX:
            eligible["singleton_isolated"].append((s1, [], "none", "singleton, no close neighbour"))

    rows = _select(eligible, per_kind)

    out_dir.mkdir(parents=True, exist_ok=True)
    pack_path = out_dir / "pack.tsv"
    with pack_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("source1_entity_id\trelated_entity_ids\tkind\toverlap_bucket\treason\n")
        for row in rows:
            handle.write(
                f"{row['source1_entity_id']}\t{row['related_entity_ids']}\t{row['kind']}\t{row['overlap_bucket']}\t{row['reason']}\n"
            )

    counts = {kind: sum(1 for row in rows if row["kind"] == kind) for kind in KINDS}
    manifest = {
        "seed": SEED,
        "selection": "deterministic sort by (kind order, source1_entity_id); no RNG required",
        "per_kind_target": per_kind,
        "total_rows": len(rows),
        "counts": counts,
        "shortfall": {kind: per_kind - counts[kind] for kind in KINDS if counts[kind] < per_kind},
        "probe_pools": {"nonsingleton": len(nonsingleton), "singleton": len(singleton)},
        "miner": {
            "df_cap": DF_CAP,
            "post_cap": POST_CAP,
            "near_miss_min": NEAR_MISS_MIN,
            "isolated_max": ISOLATED_MAX,
            "low_overlap_max": LOW_OVERLAP_MAX,
        },
        "columns": ["source1_entity_id", "related_entity_ids", "kind", "overlap_bucket", "reason"],
        "inputs": {},
        "artifacts": {},
    }
    for label, path in (
        ("train_source1", source1),
        ("train_source2", source2),
        ("train_source3", source3),
        ("train_ground_truth", gold_path),
        ("fit_ids", fit_ids_path),
    ):
        try:
            rel = path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = TRAIN_DIR_RELATIVE.joinpath(path.name).as_posix()
        manifest["inputs"][label] = {"path": rel, "sha256": sha256_file(path)}
    manifest["artifacts"]["pack"] = {
        "path": (PACK_DIR_RELATIVE / "pack.tsv").as_posix(),
        "rows": len(rows),
        "sha256": sha256_file(pack_path),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    manifest = build()
    print(f"WROTE difficulty pack rows={manifest['total_rows']}")
    for kind in KINDS:
        print(f"  {kind}: {manifest['counts'][kind]}")
    if manifest["shortfall"]:
        print(f"SHORTFALL: {manifest['shortfall']}")


if __name__ == "__main__":
    main()
