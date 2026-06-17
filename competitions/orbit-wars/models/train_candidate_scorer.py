"""Train the candidate-scorer v0 (MLP 128->64->score) on a candidates.jsonl dataset.

Imitation target = teacher_selected (did a strong player launch this candidate). The model
RANKS legal candidates; it never emits angles (FlightOracle + RuleEngine stay final authority).
Splits by episode_id (no step leakage), standardizes features, trains bounded epochs (CPU ok for
the small/local first cycle; RTX-4090/snorlax for the full 20G corpus), reports valid AUC +
recall@k vs the teacher, with a 2p/4p split. Saves model.pt + meta.json to --out-root.

  python train_candidate_scorer.py --data-root <dataset_artifact_root> --out-root models/artifacts/<run_id> [--max-epochs 40]
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
from _featurize import FEATURES, N_FEATURES, featurize, label, group_key  # noqa: E402


def _load(data_root):
    p = os.path.join(data_root, "candidates.jsonl")
    rows = [json.loads(line) for line in open(p) if line.strip()]
    return rows


def _player_count_by_ep(data_root):
    """episode_id -> player_count, from the episode index (for the 2p/4p split metric)."""
    out = {}
    ip = os.path.join(data_root, "episodes.jsonl")
    if os.path.exists(ip):
        for line in open(ip):
            if line.strip():
                e = json.loads(line)
                out[e.get("episode_id")] = e.get("player_count")
    return out


def _auc(scores, labels):
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order), float)
    ranks[order] = np.arange(1, len(order) + 1)
    r_pos = ranks[: len(pos)].sum()
    return (r_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def _recall_at_k(rows, scores, ks=(1, 3, 5)):
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(group_key(r), []).append(i)
    out = {k: [] for k in ks}
    for _g, idxs in groups.items():
        sel = [i for i in idxs if rows[i].get("teacher_selected")]
        if not sel:
            continue
        ordered = sorted(idxs, key=lambda i: -scores[i])
        for k in ks:
            topk = set(ordered[:k])
            out[k].append(len(topk & set(sel)) / len(sel))
    return {k: (float(np.mean(v)) if v else float("nan")) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(
        description="Train Orbit Wars candidate-scorer v0 (MLP)."
    )
    ap.add_argument(
        "--data-root",
        required=True,
        help="dataset artifact dir (candidates.jsonl[, episodes.jsonl])",
    )
    ap.add_argument(
        "--out-root", required=True, help="output run dir (model.pt + meta.json)"
    )
    ap.add_argument("--max-epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--valid-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    rows = _load(args.data_root)
    if len(rows) < 50:
        print(
            json.dumps(
                {
                    "blocker": f"dataset too small ({len(rows)} candidates) — build a larger corpus"
                }
            )
        )
        return
    pcount = _player_count_by_ep(args.data_root)
    X = np.array([featurize(r) for r in rows], dtype=np.float32)
    y = np.array([label(r) for r in rows], dtype=np.float32)
    eps = sorted({r.get("episode_id") for r in rows})
    rng = np.random.default_rng(args.seed)
    rng.shuffle(eps)
    n_val = max(1, int(len(eps) * args.valid_frac))
    val_eps = set(eps[:n_val])
    tr = np.array([r.get("episode_id") not in val_eps for r in rows])
    va = ~tr
    mean = X[tr].mean(0)
    std = X[tr].std(0) + 1e-6
    Xn = (X - mean) / std

    model = nn.Sequential(
        nn.Linear(N_FEATURES, 128),
        nn.ReLU(),
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Linear(64, 1),
    )
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_w = torch.tensor([max(1.0, (y[tr] == 0).sum() / max(1.0, (y[tr] == 1).sum()))])
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    Xt = torch.tensor(Xn[tr])
    yt = torch.tensor(y[tr]).unsqueeze(1)
    Xv = torch.tensor(Xn[va])
    yv = torch.tensor(y[va]).unsqueeze(1)
    log = []
    for ep in range(args.max_epochs):
        model.train()
        opt.zero_grad()
        loss = lossf(model(Xt), yt)
        loss.backward()
        opt.step()
        if ep % 5 == 0 or ep == args.max_epochs - 1:
            model.eval()
            with torch.no_grad():
                vloss = lossf(model(Xv), yv).item()
            log.append(
                {
                    "epoch": ep,
                    "train_loss": round(loss.item(), 4),
                    "valid_loss": round(vloss, 4),
                }
            )
    model.eval()
    with torch.no_grad():
        sv = torch.sigmoid(model(torch.tensor(Xn))).numpy().ravel()
    va_rows = [rows[i] for i in range(len(rows)) if va[i]]
    va_scores = sv[va]
    metrics = {
        "n_candidates": len(rows),
        "n_train": int(tr.sum()),
        "n_valid": int(va.sum()),
        "positive_rate": round(float(y.mean()), 4),
        "valid_auc": round(float(_auc(va_scores, y[va])), 4),
        "valid_recall_at_k": {
            str(k): round(v, 4) for k, v in _recall_at_k(va_rows, va_scores).items()
        },
        "epochs": log,
    }
    # 2p/4p split AUC
    for pc in (2, 4):
        mask = np.array([pcount.get(r.get("episode_id")) == pc for r in rows]) & va
        if mask.sum() > 5 and y[mask].sum() > 0 and (y[mask] == 0).sum() > 0:
            metrics[f"valid_auc_{pc}p"] = round(float(_auc(sv[mask], y[mask])), 4)

    os.makedirs(args.out_root, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(args.out_root, "model.pt"))
    meta = {
        "features": FEATURES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "arch": [N_FEATURES, 128, 64, 1],
        "label": "teacher_selected (imitation)",
        "metrics": metrics,
        "data_root": args.data_root,
    }
    with open(os.path.join(args.out_root, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps({"out": args.out_root, **metrics}, indent=2))


if __name__ == "__main__":
    main()
