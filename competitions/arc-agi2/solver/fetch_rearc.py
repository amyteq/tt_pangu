"""Fetch the RE-ARC generator repo (gitignored; never committed).

Clones github.com/michaelhodel/re-arc (MIT) into competitions/arc-agi2/data/re-arc. The repo
ships 400 generator + 400 verifier functions and the arc-dsl they use.

    python competitions/arc-agi2/solver/fetch_rearc.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPO_URL = "https://github.com/michaelhodel/re-arc.git"


def main():
    dest = DATA_DIR / "re-arc"
    if (dest / "generators.py").exists():
        print(f"[skip] {dest} already present")
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[clone] {REPO_URL} -> {dest}")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(dest)], check=True)
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
