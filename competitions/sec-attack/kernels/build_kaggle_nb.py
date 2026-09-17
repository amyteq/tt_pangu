"""
Build a Kaggle submission notebook for sec-attack from attack_kaggle.py.

Emits (into --out-dir, default = this dir):
  - <slug>.ipynb         (3 code cells: sys.path setup -> write attack.py -> run JED inference server)
  - kernel-metadata.json (notebook kernel, T4 GPU, internet off, competition data attached)

The attack source is base64-embedded so docstrings/quotes can't break the notebook literal. Cells
1/3 mirror the official getting-started notebook. CONFIG lines in attack_kaggle.py are rewritten
per-variant (MAX_CANDIDATES / FANOUT_PER_FAMILY / FAMILIES) so one source drives all variants.

Examples:
  python build_kaggle_nb.py --user harrysun2006 --slug sec-attack-jed   --families deputy,direct,filewash --max 40 --fanout 16
  python build_kaggle_nb.py --user firefly2006  --slug sec-attack-jed-x --families direct,filewash        --max 60 --fanout 28
Push:
  kaggle kernels push -p <out-dir>
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPETITION = "ai-agent-security-multi-step-tool-attacks"

SETUP_CELL = (
    "import sys, glob\n"
    "from pathlib import Path\n"
    "sys.argv = [sys.argv[0]]  # avoid argparse conflicts in Kaggle notebooks\n"
    "for candidate in glob.glob('/kaggle/input/**/kaggle_evaluation', recursive=True):\n"
    "    root = str(Path(candidate).parent)\n"
    "    if root not in sys.path:\n"
    "        sys.path.insert(0, root)\n"
    "    print('Dataset root:', root)\n"
    "    break\n"
    "print('Setup complete')\n"
)
SERVER_CELL = (
    "import os, csv\n"
    "# During 'Save & Run All' (commit) the real gateway is absent, so serve() writes no\n"
    "# submission.csv. Write a schema-valid stub to satisfy the code-submission precondition;\n"
    "# the scored competition rerun replaces it with real per-model/guardrail scores.\n"
    "if not os.getenv('KAGGLE_IS_COMPETITION_RERUN'):\n"
    "    with open('submission.csv', 'w', newline='') as _f:\n"
    "        _w = csv.writer(_f)\n"
    "        _w.writerow(['Id', 'Score'])\n"
    "        for _rid in ('gpt_oss_public', 'gpt_oss_private', 'gemma_public', 'gemma_private'):\n"
    "            _w.writerow([_rid, 0])\n"
    "    print('wrote submission.csv stub')\n"
    "import kaggle_evaluation.jed_attack_134815.jed_attack_inference_server as srv\n"
    "srv.JEDAttackInferenceServer().serve()\n"
)


def _apply_config(src: str, max_c: int, fanout: int, families: tuple[str, ...]) -> str:
    src = re.sub(r"^MAX_CANDIDATES = .*$", f"MAX_CANDIDATES = {max_c}", src, flags=re.M)
    src = re.sub(r"^FANOUT_PER_FAMILY = .*$", f"FANOUT_PER_FAMILY = {fanout}", src, flags=re.M)
    fam = "(" + ", ".join(f'"{f}"' for f in families) + ("," if len(families) == 1 else "") + ")"
    src = re.sub(r"^FAMILIES = .*$", f"FAMILIES = {fam}", src, flags=re.M)
    return src


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def _write_attack_cell(b64: str) -> str:
    return (
        "import base64\n"
        f'attack_code = base64.b64decode("{b64}").decode("utf-8")\n'
        "with open('/kaggle/working/attack.py', 'w') as f:\n"
        "    f.write(attack_code)\n"
        "print('attack.py written:', len(attack_code), 'bytes')\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--families", default="deputy,direct,filewash")
    ap.add_argument("--max", type=int, default=40, dest="max_c")
    ap.add_argument("--fanout", type=int, default=16)
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()

    out = Path(a.out_dir) if a.out_dir else HERE
    out.mkdir(parents=True, exist_ok=True)
    families = tuple(f.strip() for f in a.families.split(",") if f.strip())

    src = _apply_config((HERE / "attack_kaggle.py").read_text(encoding="utf-8"), a.max_c, a.fanout, families)
    compile(src, "attack.py", "exec")  # fail fast on a bad substitution
    b64 = base64.b64encode(src.encode("utf-8")).decode("ascii")

    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# sec-attack — {a.slug}\n",
                    f"families={families} max={a.max_c} fanout={a.fanout}. Verifies templates "
                    "against the real in-kernel agent, keeps firing families, fans out across sinks.",
                ],
            },
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
    (out / f"{a.slug}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
    meta = {
        "id": f"{a.user}/{a.slug}",
        "title": a.slug,
        "code_file": f"{a.slug}.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        # The competition requires T4 (P100 is rejected); match the official getting-started kernel.
        "machine_shape": "NvidiaTeslaT4",
        "docker_image": (
            "gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c"
        ),
        "dataset_sources": [],
        "competition_sources": [COMPETITION],
        "kernel_sources": [],
        "model_sources": [],
    }
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"built {a.user}/{a.slug}: families={families} max={a.max_c} fanout={a.fanout} -> {out}")


if __name__ == "__main__":
    main()
