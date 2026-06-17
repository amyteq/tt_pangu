"""Offline evaluation of an exported scorer.npz against a candidates.jsonl dataset.

Pure numpy (no torch) — this is the same forward path the ladder runtime uses, so the numbers
here are what the deployed scorer would produce. Reports AUC + recall@k vs the teacher, split by
2p/4p. IMPORTANT: high offline recall does NOT imply arena strength — the T12 BC student hit
recall@k 0.387 yet scored 0% in the arena (distribution shift). Treat these as imitation-fidelity
diagnostics only; arena A/B (VALIDATION.md gate #3) is the real test.

  python evaluate_offline.py --npz models/artifacts/<run_id>/scorer.npz --data-root <dataset_root>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from _featurize import featurize, group_key  # noqa: E402
from export_npz import forward  # noqa: E402


def _auc(scores, labels):
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order), float)
    ranks[order] = np.arange(1, len(order) + 1)
    return (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def _recall_at_k(rows, scores, ks=(1, 3, 5)):
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(group_key(r), []).append(i)
    out = {k: [] for k in ks}
    for idxs in groups.values():
        sel = [i for i in idxs if rows[i].get("teacher_selected")]
        if not sel:
            continue
        ordered = sorted(idxs, key=lambda i: -scores[i])
        for k in ks:
            out[k].append(len(set(ordered[:k]) & set(sel)) / len(sel))
    return {str(k): (round(float(np.mean(v)), 4) if v else None) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description="Offline eval of an Orbit Wars scorer.npz.")
    ap.add_argument("--npz", required=True)
    ap.add_argument("--data-root", required=True)
    args = ap.parse_args()

    npz = np.load(args.npz, allow_pickle=True)
    rows = [json.loads(line) for line in open(os.path.join(args.data_root, "candidates.jsonl")) if line.strip()]
    X = np.array([featurize(r) for r in rows], dtype=np.float64)
    y = np.array([1.0 if r.get("teacher_selected") else 0.0 for r in rows])
    scores = forward(npz, X)

    pcount = {}
    ip = os.path.join(args.data_root, "episodes.jsonl")
    if os.path.exists(ip):
        for line in open(ip):
            if line.strip():
                e = json.loads(line)
                pcount[e.get("episode_id")] = e.get("player_count")

    report = {
        "n_candidates": len(rows),
        "positive_rate": round(float(y.mean()), 4),
        "auc": round(float(_auc(scores, y)), 4),
        "recall_at_k": _recall_at_k(rows, scores),
        "caveat": "offline imitation fidelity only — NOT arena strength (T12 BC: recall 0.387 / arena 0%).",
    }
    for pc in (2, 4):
        m = np.array([pcount.get(r.get("episode_id")) == pc for r in rows])
        if m.sum() > 5 and y[m].sum() > 0 and (y[m] == 0).sum() > 0:
            report[f"auc_{pc}p"] = round(float(_auc(scores[m], y[m])), 4)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
