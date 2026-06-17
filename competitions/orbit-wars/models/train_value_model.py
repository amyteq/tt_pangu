"""Train the value model v0 — regress a candidate's future score delta (state-action value).

Distinct from the scorer (imitation classifier): here the target is the REALIZED future score
delta the dataset already computed (future_value_delta_h50, fallback h20), a continuous value
signal that does NOT require imitating the teacher's policy. This is the value head the hybrid
can use to break ties / prefer high-value launches, and it sidesteps the BC distribution-shift
trap (B7) because the label is outcome, not "what the strong player clicked". Same featurize()
vector, same episode-split discipline. Reports valid MSE + Pearson r.

  python train_value_model.py --data-root <dataset_root> --out-root models/artifacts/<run_id>_value [--horizon 50]
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


def main():
    ap = argparse.ArgumentParser(description="Train Orbit Wars value model v0 (regressor).")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--horizon", type=int, choices=(20, 50), default=50)
    ap.add_argument("--max-epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--valid-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    key = f"future_value_delta_h{args.horizon}"
    alt = "future_value_delta_h20" if args.horizon == 50 else "future_value_delta_h50"
    rows = [json.loads(line) for line in open(os.path.join(args.data_root, "candidates.jsonl")) if line.strip()]
    rows = [r for r in rows if r.get(key) is not None or r.get(alt) is not None]
    if len(rows) < 50:
        print(json.dumps({"blocker": f"too few labeled rows ({len(rows)}) for value target {key}"}))
        return
    X = np.array([featurize(r) for r in rows], dtype=np.float32)
    y = np.array(
        [float(r.get(key) if r.get(key) is not None else r.get(alt)) for r in rows],
        dtype=np.float32,
    )

    eps = sorted({r.get("episode_id") for r in rows})
    rng = np.random.default_rng(args.seed)
    rng.shuffle(eps)
    val_eps = set(eps[: max(1, int(len(eps) * args.valid_frac))])
    tr = np.array([r.get("episode_id") not in val_eps for r in rows])
    va = ~tr
    mean = X[tr].mean(0)
    std = X[tr].std(0) + 1e-6
    ym = float(y[tr].mean())
    ys = float(y[tr].std() + 1e-6)
    Xn = (X - mean) / std
    yn = (y - ym) / ys

    model = nn.Sequential(
        nn.Linear(N_FEATURES, 128),
        nn.ReLU(),
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Linear(64, 1),
    )
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    lossf = nn.MSELoss()
    Xt = torch.tensor(Xn[tr])
    yt = torch.tensor(yn[tr]).unsqueeze(1)
    Xv = torch.tensor(Xn[va])
    yv = torch.tensor(yn[va]).unsqueeze(1)
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
                    "train_mse": round(loss.item(), 4),
                    "valid_mse": round(vloss, 4),
                }
            )
    model.eval()
    with torch.no_grad():
        pv = model(Xv).numpy().ravel()
    yv_raw = y[va]
    pv_raw = pv * ys + ym
    if len(pv_raw) > 2 and np.std(pv_raw) > 0 and np.std(yv_raw) > 0:
        pearson = float(np.corrcoef(pv_raw, yv_raw)[0, 1])
    else:
        pearson = float("nan")
    metrics = {
        "n_rows": len(rows),
        "n_train": int(tr.sum()),
        "n_valid": int(va.sum()),
        "target": key,
        "valid_pearson_r": round(pearson, 4),
        "valid_mse_raw": round(float(np.mean((pv_raw - yv_raw) ** 2)), 3),
        "epochs": log,
    }
    os.makedirs(args.out_root, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(args.out_root, "model.pt"))
    meta = {
        "features": FEATURES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "y_mean": ym,
        "y_std": ys,
        "arch": [N_FEATURES, 128, 64, 1],
        "label": key,
        "task": "value_regression",
        "metrics": metrics,
        "data_root": args.data_root,
    }
    with open(os.path.join(args.out_root, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps({"out": args.out_root, **metrics}, indent=2))


if __name__ == "__main__":
    main()
