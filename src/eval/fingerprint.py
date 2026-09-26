"""SHA-256 fingerprints of exact file bytes.

This is the eval fingerprint. Other owners should call it rather than
hashing artifacts a second way.
"""

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
