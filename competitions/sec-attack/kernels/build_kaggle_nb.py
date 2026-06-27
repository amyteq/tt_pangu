"""
Build the Kaggle submission notebook for sec-attack from attack_kaggle.py.

Produces, next to this file:
  - sec-attack-jed.ipynb   (3 cells: sys.path setup → write attack.py → run JED inference server)
  - kernel-metadata.json   (notebook kernel, T4 GPU, internet off, competition data attached)

The attack source is base64-embedded so arbitrary Python (docstrings/quotes) can't break the
notebook string literal. Cell 1 + cell 3 mirror the official getting-started notebook
(martynaplomecka/getting-started-notebook); cell 2 writes our attack to /kaggle/working/attack.py.

Usage:  python build_kaggle_nb.py
Push:   kaggle kernels push -p competitions/sec-attack/kernels
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KAGGLE_USER = "harrysun2006"
KERNEL_SLUG = "sec-attack-jed"
COMPETITION = "ai-agent-security-multi-step-tool-attacks"

SETUP_CELL = (
    "import sys, glob\n"
    "from pathlib import Path\n"
    "sys.argv = [sys.argv[0]]  # avoid argparse conflicts in Kaggle notebooks\n"
    "# competition data root holds kaggle_evaluation/ and aicomp_sdk/\n"
    "for candidate in glob.glob('/kaggle/input/**/kaggle_evaluation', recursive=True):\n"
    "    root = str(Path(candidate).parent)\n"
    "    if root not in sys.path:\n"
    "        sys.path.insert(0, root)\n"
    "    print('Dataset root:', root)\n"
    "    break\n"
    "print('Setup complete')\n"
)

SERVER_CELL = (
    "# 'Save & Run All' only verifies the notebook runs; real scoring happens on the\n"
    "# competition rerun via this inference server.\n"
    "import kaggle_evaluation.jed_attack_134815.jed_attack_inference_server as srv\n"
    "srv.JEDAttackInferenceServer().serve()\n"
)


def _write_attack_cell(b64: str) -> str:
    return (
        "import base64\n"
        "# attack source (attack_kaggle.py) base64-embedded to avoid escaping issues\n"
        f'attack_code = base64.b64decode("{b64}").decode("utf-8")\n'
        "with open('/kaggle/working/attack.py', 'w') as f:\n"
        "    f.write(attack_code)\n"
        "print('attack.py written:', len(attack_code), 'bytes')\n"
    )


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def main() -> None:
    attack_src = (HERE / "attack_kaggle.py").read_text(encoding="utf-8")
    b64 = base64.b64encode(attack_src.encode("utf-8")).decode("ascii")

    nb = {
        "cells": [
            {"cell_type": "markdown", "metadata": {},
             "source": ["# sec-attack — JED red-team submission\n",
                        "Verifies attack templates against the real in-kernel agent, then fans out "
                        "firing families across distinct benign sinks. See competitions/sec-attack/."]},
            _code_cell(SETUP_CELL),
            _code_cell(_write_attack_cell(b64)),
            _code_cell(SERVER_CELL),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (HERE / f"{KERNEL_SLUG}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")

    meta = {
        "id": f"{KAGGLE_USER}/{KERNEL_SLUG}",
        "title": KERNEL_SLUG,
        "code_file": f"{KERNEL_SLUG}.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [],
        "competition_sources": [COMPETITION],
        "kernel_sources": [],
        "model_sources": [],
    }
    (HERE / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {KERNEL_SLUG}.ipynb ({len(b64)} b64 chars) + kernel-metadata.json")


if __name__ == "__main__":
    main()
