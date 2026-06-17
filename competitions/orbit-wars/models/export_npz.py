"""Export a trained model.pt (+ meta.json) to runtime artifacts.

Two outputs from one run:
  * scorer.npz  — numpy weights for fast OFFLINE eval (models/evaluate_offline.py). forward() here
    is the reference numpy scorer.
  * scorer.json — pure-Python-loadable weights (features, mean/std, per-layer W/b) for the ONLINE
    ladder agent, which stays stdlib-only (no numpy/torch import on Kaggle). agent/hybrid_model.py
    loads this with the json module and runs a pure-Python forward.

Both are self-checked against torch (max_err < 1e-5).

  python export_npz.py --run-root models/artifacts/<run_id>
"""

from __future__ import annotations

import argparse
import json
import math
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
    ap.add_argument("--run-root", required=True, help="run dir with model.pt + meta.json")
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

    # pure-Python-loadable JSON (stdlib-only online runtime). Layers ordered input->output.
    n_layers = len([k for k in arrs if k.startswith("W")])
    layers = [{"W": arrs[f"W{i}"].tolist(), "b": arrs[f"b{i}"].tolist()} for i in range(n_layers)]
    jdoc = {
        "features": list(FEATURES),
        "mean": arrs["mean"].tolist(),
        "std": arrs["std"].tolist(),
        "layers": layers,
        "activation": "relu",
        "output": "sigmoid",
    }
    json_out = os.path.join(args.run_root, "scorer.json")
    with open(json_out, "w") as f:
        json.dump(jdoc, f)

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

    # pure-Python forward (mirrors agent/hybrid_model.py) on the standardized rows
    def _pyfwd(row):
        h = list(row)
        for li2, lyr in enumerate(jdoc["layers"]):
            out_v = []
            for wj, bj in zip(lyr["W"], lyr["b"]):
                acc = bj + sum(wj[k] * h[k] for k in range(len(wj)))
                out_v.append(acc)
            if li2 < len(jdoc["layers"]) - 1:
                out_v = [v if v > 0 else 0.0 for v in out_v]
            h = out_v
        z = max(-60.0, min(60.0, h[0]))
        return 1.0 / (1.0 + math.exp(-z))

    std_rows = ((xs - arrs["mean"]) / arrs["std"]).tolist()
    py = np.array([_pyfwd(r) for r in std_rows])
    py_err = float(np.max(np.abs(ref - py)))
    print(
        json.dumps(
            {
                "npz": out,
                "json": json_out,
                "n_features": len(FEATURES),
                "npz_selfcheck_max_err": round(max_err, 8),
                "json_selfcheck_max_err": round(py_err, 8),
                "ok": max_err < 1e-5 and py_err < 1e-5,
            }
        )
    )


if __name__ == "__main__":
    main()
