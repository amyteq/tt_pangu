"""Train the candidate-scorer v0 (MLP 24->128->64->score) on a candidates.jsonl dataset.

Imitation target = teacher_selected (did a real ladder player launch this candidate). The model
RANKS legal candidates; it never emits angles (FlightOracle + RuleEngine stay final authority).
Splits by episode_id (no step leakage), standardizes features, trains bounded epochs (CPU is fine
— the MLP is tiny; GPU buys nothing). Reports valid AUC + recall@k vs the teacher, with 2p/4p and
winner/loser splits. `--winners-only` restricts imitation to the WINNING seat of each game (a
stronger "imitate successful play" signal, aligned with the strong-tier goal). Saves model.pt +
meta.json to --out-root.

Memory-lean: streams the file, featurizes on the fly into a float32 array, and keeps only light
per-row fields (episode/step/player/winner/2p4p) — it never holds the full row dicts (the real
corpus is ~2.5M rows).

  python train_candidate_scorer.py --data-root <dataset_artifact_root> --out-root models/artifacts/<run_id> [--max-epochs 60] [--winners-only]
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
from _featurize import FEATURES, N_FEATURES, featurize  # noqa: E402


def _player_count_by_ep(data_root):
    out = {}
    ip = os.path.join(data_root, "episodes.jsonl")
    if os.path.exists(ip):
        for line in open(ip):
            if line.strip():
                e = json.loads(line)
                out[e.get("episode_id")] = e.get("player_count")
    return out


def _stream(data_root, winners_only):
    """Yield (feature_vec, label, episode_id, step, player_id, seat_is_winner) per row."""
    p = os.path.join(data_root, "candidates.jsonl")
    for line in open(p):
        if not line.strip():
            continue
        r = json.loads(line)
        win = int(bool(r.get("seat_is_winner")))
        if winners_only and not win:
            continue
        yield (
            featurize(r),
            1.0 if r.get("teacher_selected") else 0.0,
            r.get("episode_id"),
            r.get("step"),
            r.get("player_id"),
            win,
        )


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


def _recall_at_k(groups, scores, y, mask, ks=(1, 3, 5)):
    """groups: per-row (episode, step, player) tuples. mask: rows to include (e.g. valid set)."""
    g = {}
    for i in np.nonzero(mask)[0]:
        g.setdefault(groups[i], []).append(i)
    out = {k: [] for k in ks}
    for idxs in g.values():
        sel = [i for i in idxs if y[i] == 1]
        if not sel:
            continue
        ordered = sorted(idxs, key=lambda i: -scores[i])
        for k in ks:
            out[k].append(len(set(ordered[:k]) & set(sel)) / len(sel))
    return {str(k): (round(float(np.mean(v)), 4) if v else None) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description="Train Orbit Wars candidate-scorer v0 (MLP).")
    ap.add_argument(
        "--data-root",
        required=True,
        help="dataset artifact dir (candidates.jsonl[, episodes.jsonl])",
    )
    ap.add_argument("--out-root", required=True, help="output run dir (model.pt + meta.json)")
    ap.add_argument("--max-epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--valid-frac", type=float, default=0.2)
    ap.add_argument(
        "--winners-only",
        action="store_true",
        help="imitate only the winning seat of each game",
    )
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    pcount = _player_count_by_ep(args.data_root)

    feats, ys, eps_col, win_col, groups = [], [], [], [], []
    for vec, lab, eid, step, pid, win in _stream(args.data_root, args.winners_only):
        feats.append(vec)
        ys.append(lab)
        eps_col.append(eid)
        win_col.append(win)
        groups.append((eid, step, pid))
    if len(feats) < 50:
        print(json.dumps({"blocker": f"dataset too small ({len(feats)} candidates) — build a larger corpus"}))
        return
    X = np.asarray(feats, dtype=np.float32)
    y = np.asarray(ys, dtype=np.float32)
    win_col = np.asarray(win_col)
    pc_col = np.asarray([pcount.get(e, 0) for e in eps_col])

    eps = sorted(set(eps_col))
    rng = np.random.default_rng(args.seed)
    rng.shuffle(eps)
    val_eps = set(eps[: max(1, int(len(eps) * args.valid_frac))])
    va = np.asarray([e in val_eps for e in eps_col])
    tr = ~va

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
        if ep % 10 == 0 or ep == args.max_epochs - 1:
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

    metrics = {
        "n_candidates": int(len(y)),
        "n_train": int(tr.sum()),
        "n_valid": int(va.sum()),
        "winners_only": bool(args.winners_only),
        "positive_rate": round(float(y.mean()), 5),
        "valid_auc": round(float(_auc(sv[va], y[va])), 4),
        "valid_recall_at_k": _recall_at_k(groups, sv, y, va),
        "epochs": log,
    }
    for pc in (2, 4):
        m = (pc_col == pc) & va
        if m.sum() > 5 and y[m].sum() > 0 and (y[m] == 0).sum() > 0:
            metrics[f"valid_auc_{pc}p"] = round(float(_auc(sv[m], y[m])), 4)
    for name, wv in (("winner", 1), ("loser", 0)):
        m = (win_col == wv) & va
        if m.sum() > 5 and y[m].sum() > 0 and (y[m] == 0).sum() > 0:
            metrics[f"valid_auc_{name}_seat"] = round(float(_auc(sv[m], y[m])), 4)

    os.makedirs(args.out_root, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(args.out_root, "model.pt"))
    meta = {
        "features": FEATURES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "arch": [N_FEATURES, 128, 64, 1],
        "label": "teacher_selected (imitation)",
        "winners_only": bool(args.winners_only),
        "metrics": metrics,
        "data_root": args.data_root,
    }
    with open(os.path.join(args.out_root, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps({"out": args.out_root, **metrics}, indent=2))


if __name__ == "__main__":
    main()
