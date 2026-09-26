"""Person 2 Phase 3: Canonical artifact reproduction and byte-level verification."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

from src.eval.fingerprint import sha256_file
from src.represent.build_canonical_artifacts import build_representation_artifacts
from src.represent.config import NORMALIZER_VERSION, dataset_dir, resource_dir, REPO_ROOT


def verify_and_reproduce_canonical_artifacts() -> Dict[str, Any]:
    """Reproduce canonical token resources and verify byte-for-byte against manifest.json."""
    start_time = time.time()
    res_d = resource_dir()
    manifest_path = res_d / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}. Build artifacts first.")

    with manifest_path.open("r", encoding="utf-8") as f:
        frozen_manifest = json.load(f)

    # 1. Capture original fingerprints
    expected_hashes = {
        name: data["sha256"] for name, data in frozen_manifest["resources"].items()
    }

    # 2. Re-run artifact generation
    print("Executing deterministic rebuild of canonical token resources...")
    build_representation_artifacts()

    # 3. Compute and compare new fingerprints
    verification_results = {}
    all_matched = True

    for resource_name, expected_hash in expected_hashes.items():
        file_path = res_d / f"{resource_name}.json"
        actual_hash = sha256_file(file_path)
        matched = (actual_hash == expected_hash)
        if not matched:
            all_matched = False
        verification_results[resource_name] = {
            "path": str(file_path.relative_to(REPO_ROOT)),
            "expected_sha256": expected_hash,
            "actual_sha256": actual_hash,
            "byte_identical": matched,
            "size_bytes": file_path.stat().st_size,
        }

    elapsed = round(time.time() - start_time, 2)

    proof = {
        "proof_type": "canonical_representation_reproduction",
        "phase": 3,
        "owner": "Shriya (Person 2)",
        "status": "PASSED" if all_matched else "FAILED",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "normalizer_version": NORMALIZER_VERSION,
        "reproduction_runtime_seconds": elapsed,
        "verified_resources": verification_results,
        "supported_scripts": frozen_manifest.get("supported_indic_scripts", []),
        "supported_french_entities": frozen_manifest.get("supported_french_entities", []),
    }

    proof_path = res_d / "reproduction_proof.json"
    with proof_path.open("w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2)

    print(f"Reproduction proof generated: {proof_path}")
    print(f"Reproduction status: {proof['status']} (Runtime: {elapsed}s)")
    return proof


if __name__ == "__main__":
    verify_and_reproduce_canonical_artifacts()
