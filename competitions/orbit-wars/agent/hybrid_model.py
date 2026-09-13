"""Online candidate scorer for the hybrid agent — pure Python, stdlib + core only (no numpy/torch).

Loads the exported weights (agent/hybrid_weights.json: features + standardization mean/std +
per-layer W/b) and runs a pure-Python MLP forward, so the ladder agent stays import-light
(VALIDATION.md #6). The scorer only RANKS legal candidates — FlightOracle + RuleEngine +
ActionSanitizer remain the final authority (it never emits an angle or a ship count).

Fail-safe by construction: `load_default()` returns None if the weights are missing/malformed or
core is unavailable, and the caller (agent/main.py) then runs rules-only. Feature extraction reuses
`core.features.feature_vector` — the SAME contract the model was trained on (single source of truth).
"""

from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):  # agent/ and comp root (for `core`)
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)


def _default_weights_path():
    return os.path.join(_HERE, "hybrid_weights.json")


class Scorer:
    """Pure-Python MLP scorer over candidate feature dicts."""

    def __init__(self, doc):
        self.features = doc["features"]
        self.mean = doc["mean"]
        self.std = doc["std"]
        self.layers = doc["layers"]  # [{"W": [[...]], "b": [...]}, ...] input->output
        # import here so a missing core only disables the scorer, never the agent
        from core.features import feature_vector  # noqa: PLC0415

        self._feature_vector = feature_vector

    def _forward(self, vec):
        h = [(vec[k] - self.mean[k]) / self.std[k] for k in range(len(vec))]
        n = len(self.layers)
        for li, lyr in enumerate(self.layers):
            W, b = lyr["W"], lyr["b"]
            out = []
            for j in range(len(W)):
                wj = W[j]
                acc = b[j]
                for k in range(len(wj)):
                    acc += wj[k] * h[k]
                out.append(acc)
            if li < n - 1:  # ReLU on hidden layers only
                out = [v if v > 0.0 else 0.0 for v in out]
            h = out
        z = h[0]
        if z < -60.0:
            z = -60.0
        elif z > 60.0:
            z = 60.0
        return 1.0 / (1.0 + math.exp(-z))

    def score_cf(self, cf, ship_bucket=None):
        """Score a candidate_features() dict -> probability in [0, 1]."""
        return self._forward(self._feature_vector(cf, ship_bucket))


def load_default(path=None):
    """Return a Scorer, or None if weights/core are unavailable OR the weights' feature contract no
    longer matches core.features.FEATURE_NAMES (caller falls back to rules-only)."""
    try:
        p = path or _default_weights_path()
        with open(p) as f:
            doc = json.load(f)
        if not doc.get("layers") or not doc.get("features"):
            return None
        # Compatibility guard: the exported weights must match the CURRENT feature contract exactly,
        # else they would silently mis-score (or index-error). On mismatch, disable -> rules-only.
        from core.features import FEATURE_NAMES  # noqa: PLC0415

        if list(doc["features"]) != list(FEATURE_NAMES) or len(doc.get("mean", [])) != len(FEATURE_NAMES):
            return None
        in_dim = len(doc["layers"][0]["W"][0]) if doc["layers"][0].get("W") else 0
        if in_dim != len(FEATURE_NAMES):
            return None
        return Scorer(doc)
    except Exception:
        return None
