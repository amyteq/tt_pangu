"""Export a trained model.pt (+ meta.json) to a single .npz the ladder agent loads with numpy only.

The ladder agent stays stdlib+numpy (no torch import on Kaggle). This dumps the MLP weights,
the standardization mean/std, and the FEATURES contract into one .npz; forward() here is the
reference pure-numpy scorer the runtime mirrors.

  python export_npz.py --run-root models/artifacts/<run_id> [--out models/artifacts/<run_id>/scorer.npz]
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
from _featurize import FEATURES  # noqa: E402


def forward(npz, x):
    """Pure-numpy MLP forward (x: [n, N_FEATURES] raw features). Returns sigmoid scores."""
    x = (np.asarray(x, dtype=np.float64) - npz["mean"]) / npz["std"]
    for i in range(len([k for k in npz.files if k.startswith("W")])):
        x = x @ npz[f"W{i}"].T + npz[f"b{i}"]
        if f"W{i + 1}" in npz.files:
            x = np.maximum(x, 0.0)  # ReLU on hidden layers only
    return 1.0 / (1.0 + np.exp(-np.clip(x.ravel(), -60.0, 60.0)))


def main():
    ap = argparse.ArgumentParser(description="Export Orbit Wars scorer to numpy .npz.")
    ap.add_argument(
        "--run-root", required=True, help="run dir with model.pt + meta.json"
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import torch

    meta = json.load(open(os.path.join(args.run_root, "meta.json")))
    sd = torch.load(os.path.join(args.run_root, "model.pt"), map_location="cpu")
    arrs = {
        "mean": np.array(meta["mean"], np.float64),
        "std": np.array(meta["std"], np.float64),
    }
    li = 0
    for key in sd:  # nn.Sequential -> "0.weight","0.bias","2.weight",...
        if key.endswith(".weight"):
            arrs[f"W{li}"] = sd[key].cpu().numpy().astype(np.float64)
        elif key.endswith(".bias"):
            arrs[f"b{li}"] = sd[key].cpu().numpy().astype(np.float64)
            li += 1
    out = args.out or os.path.join(args.run_root, "scorer.npz")
    np.savez(out, features=np.array(FEATURES), **arrs)

    # self-check: exported numpy forward must reproduce torch within tolerance
    npz = np.load(out, allow_pickle=True)
    rng = np.random.default_rng(0)
    xs = rng.standard_normal((8, len(FEATURES)))
    with torch.no_grad():
        model_keys = [k for k in sd if k.endswith(".weight")]
        h = torch.tensor((xs - arrs["mean"]) / arrs["std"], dtype=torch.float32)
        for i, k in enumerate(model_keys):
            bk = k.replace("weight", "bias")
            h = h @ sd[k].T.float() + sd[bk].float()
            if i < len(model_keys) - 1:
                h = torch.relu(h)
        ref = torch.sigmoid(h).numpy().ravel()
    got = forward(npz, xs)
    max_err = float(np.max(np.abs(ref - got)))
    print(
        json.dumps(
            {
                "npz": out,
                "n_features": len(FEATURES),
                "selfcheck_max_err": round(max_err, 8),
                "ok": max_err < 1e-5,
            }
        )
    )


if __name__ == "__main__":
    main()
