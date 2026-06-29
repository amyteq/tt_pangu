"""Fetch the public ARC-AGI-2 data (gitignored; never committed).

Clones github.com/arcprize/ARC-AGI-2 into competitions/arc-agi2/data/ARC-AGI-2
(1,000 training + 120 evaluation tasks). Optionally also downloads the Kaggle
competition files (challenges/solutions + sample_submission) if the kaggle CLI is set up.

    python competitions/arc-agi2/eval/fetch_data.py          # GitHub data only
    python competitions/arc-agi2/eval/fetch_data.py --kaggle  # + Kaggle competition files
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPO_URL = "https://github.com/arcprize/ARC-AGI-2.git"
KAGGLE_SLUG = "arc-prize-2026-arc-agi-2"


def fetch_github() -> None:
    dest = DATA_DIR / "ARC-AGI-2"
    if (dest / "data" / "evaluation").is_dir():
        print(f"[skip] {dest} already present")
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[clone] {REPO_URL} -> {dest}")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(dest)], check=True)


def fetch_kaggle() -> None:
    print(f"[kaggle] downloading competition files for {KAGGLE_SLUG}")
    subprocess.run(
        ["kaggle", "competitions", "download", "-c", KAGGLE_SLUG, "-p", str(DATA_DIR)],
        check=True,
    )
    # unzip if a bundle was produced
    for z in DATA_DIR.glob("*.zip"):
        subprocess.run(["unzip", "-o", str(z), "-d", str(DATA_DIR)], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kaggle", action="store_true", help="also download Kaggle competition files")
    args = ap.parse_args(argv)
    fetch_github()
    if args.kaggle:
        fetch_kaggle()
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
