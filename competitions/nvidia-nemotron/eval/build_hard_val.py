"""Build eval/hard_val_ids.json — a category-stratified hard-validation set (T12).

Selection criteria (no GPU): a deterministic per-category solver (../lib/nemo_solver.py) is
run over the local train.csv; rows the solver CANNOT fit (its answer != ground truth) are the
"hard to fit" rows — the closest cheap proxy to the hidden new-rule benchmark. We also add a
few answer-format edge rows (leading-zero binary). Per category we keep up to N hard ids plus
a couple of solver-SOLVED "anchor" rows (should always pass — regression guards).

Run where the competition train.csv is available:
    python build_hard_val.py [path/to/train.csv]
Default path: ~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv
The emitted hard_val_ids.json is committed and reusable without train.csv.
"""

import csv
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "lib"))
from nemo_solver import SOLVERS, classify, verify  # noqa: E402

N_HARD = 20  # hard (solver-unfit) ids per category
N_ANCHOR = 3  # solver-solved regression anchors per category


def answer_type(a: str) -> str:
    a = str(a).strip()
    if re.fullmatch(r"[01]{8}", a):
        return "binary8"
    try:
        float(a)
        return "numeric"
    except ValueError:
        return "string/symbol"


def main():
    tc = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")
    )
    rows = list(csv.DictReader(open(tc, encoding="utf-8")))
    rng = random.Random(13)
    hard, anchors, cov = {}, {}, {}
    for r in rows:
        c = classify(r["prompt"])
        if c not in SOLVERS:
            continue
        cov.setdefault(c, [0, 0])
        cov[c][1] += 1
        try:
            out = SOLVERS[c](r["prompt"])
        except Exception:
            out = None
        ok = bool(out) and verify(out[0], r["answer"])
        cov[c][0] += int(ok)
        (anchors if ok else hard).setdefault(c, []).append(r)

    out = {
        "_meta": {
            "purpose": "category-stratified hard-validation set for local eval (T12)",
            "selection": "solver-unfit rows per category (proxy for hidden new-rule difficulty) + format edges",
            "metric": "official extract+verify (eval/official_metric.py); numeric 1e-2 or exact string",
            "coverage_solved_total": {c: cov[c] for c in sorted(cov)},
            "note": "per-row hidden-LB contribution is unknown; rebuild with same criteria if train.csv changes",
        },
        "hard": {},
        "anchors": {},
    }
    for c in sorted(cov):
        h = rng.sample(hard.get(c, []), min(N_HARD, len(hard.get(c, []))))
        a = rng.sample(anchors.get(c, []), min(N_ANCHOR, len(anchors.get(c, []))))
        out["hard"][c] = [{"id": r["id"], "answer_type": answer_type(r["answer"])} for r in h]
        out["anchors"][c] = [{"id": r["id"]} for r in a]
    # format-edge: leading-zero binary answers
    lz = [r for r in rows if re.fullmatch(r"0[01]{7}", str(r["answer"]).strip())]
    out["format_edges"] = {"leading_zero_binary": [r["id"] for r in rng.sample(lz, min(8, len(lz)))]}
    n = sum(len(v) for v in out["hard"].values())
    with open(os.path.join(HERE, "hard_val_ids.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote hard_val_ids.json: {n} hard ids across {len(out['hard'])} categories")
    for c, (s, t) in out["_meta"]["coverage_solved_total"].items():
        print(f"  {c:9s} solved {s}/{t}  hard kept {len(out['hard'][c])}")


if __name__ == "__main__":
    main()
