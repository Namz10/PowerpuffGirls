"""Deterministic fit / loop / report assignment.

Unit of assignment is the Source 1 id. Links are never split.
"""

import random

from src.eval.config import BUCKETS, LOOP_SIZE, REPORT_PERCENT, SEED

BUCKET_ORDER = {name: index for index, name in enumerate(BUCKETS)}


def bucket_name(list_length: int) -> str:
    if list_length <= 0:
        return "0"
    if list_length == 1:
        return "1"
    if list_length <= 3:
        return "2-3"
    if list_length <= 5:
        return "4-5"
    return "6+"


def stratum_key(country: str, list_length: int) -> tuple[str, str]:
    return (country, bucket_name(list_length))


def allocate(stratum_sizes: dict[tuple[str, str], int]) -> dict[tuple[str, str], dict[str, int]]:
    """Floor 10% of each stratum to report. Largest-remainder 25_000 to loop."""
    if not stratum_sizes:
        raise ValueError("no strata")
    total = sum(stratum_sizes.values())
    keys = sorted(stratum_sizes, key=lambda key: (key[0], BUCKET_ORDER[key[1]]))
    report = {key: (stratum_sizes[key] * REPORT_PERCENT) // 100 for key in keys}
    base = {key: (LOOP_SIZE * stratum_sizes[key]) // total for key in keys}
    remainder = {key: (LOOP_SIZE * stratum_sizes[key]) % total for key in keys}
    leftover = LOOP_SIZE - sum(base.values())
    winners = sorted(keys, key=lambda key: (-remainder[key], key[0], BUCKET_ORDER[key[1]]))
    loop = dict(base)
    for key in winners[:leftover]:
        loop[key] += 1
    allocation = {}
    for key in keys:
        size = stratum_sizes[key]
        report_n = report[key]
        loop_n = loop[key]
        if report_n + loop_n > size:
            raise ValueError(f"stratum {key} cannot hold report={report_n} loop={loop_n} size={size}")
        allocation[key] = {
            "size": size,
            "report": report_n,
            "loop": loop_n,
            "fit": size - report_n - loop_n,
        }
    if sum(item["loop"] for item in allocation.values()) != LOOP_SIZE:
        raise ValueError("loop allocation does not sum to 25000")
    return allocation


def assign(
    stratum_ids: dict[tuple[str, str], list[str]],
    allocation: dict[tuple[str, str], dict[str, int]],
    seed: int = SEED,
) -> dict[str, list[str]]:
    """Shuffle within each stratum using one Random(seed), then publish sorted ids."""
    rng = random.Random(seed)
    assigned = {"fit": [], "loop": [], "report": []}
    for key in sorted(allocation, key=lambda item: (item[0], BUCKET_ORDER[item[1]])):
        ids = stratum_ids[key]
        if len(ids) != allocation[key]["size"]:
            raise ValueError(f"stratum {key} size mismatch")
        shuffled = sorted(ids)
        rng.shuffle(shuffled)
        report_n = allocation[key]["report"]
        loop_n = allocation[key]["loop"]
        assigned["report"].extend(shuffled[:report_n])
        assigned["loop"].extend(shuffled[report_n : report_n + loop_n])
        assigned["fit"].extend(shuffled[report_n + loop_n :])
    for name in assigned:
        assigned[name] = sorted(assigned[name])
    return assigned
