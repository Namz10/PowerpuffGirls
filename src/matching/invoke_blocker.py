"""Run ``python -m src.blocking.cli`` unchanged.

On Windows, prepend the resource shim via ``PYTHONPATH`` so the import succeeds.
The blocker package itself is not edited.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def command(argv: list[str]) -> list[str]:
    return [sys.executable, "-m", "src.blocking.cli", *argv]


def environment() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform == "win32":
        shim = str(Path(__file__).resolve().parent / "_win_stdlib_shim")
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = shim if not current else shim + os.pathsep + current
    return env


def run(argv: list[str]) -> int:
    completed = subprocess.run(command(argv), cwd=REPO_ROOT, env=environment(), check=False)
    return completed.returncode


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
