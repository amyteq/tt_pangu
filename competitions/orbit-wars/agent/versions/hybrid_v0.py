"""hybrid_v0 — the v3.2 Forecast agent with the model candidate re-ranker enabled (OW-P2-HYBRID-001).

This is just main.py (v3.2) with OW_HYBRID on: the trained scorer (agent/hybrid_weights.json) blends
into the greedy commit order; sizing, path-safety, the value sim, and the FlightOracle emission gate
are unchanged. If the weights / core fail to load, main.py falls back to the plain v3.2 order, so
hybrid_v0 is never worse than v3.2 by construction.

Used as a named opponent in the arena A/B (hybrid_v0 vs main/v3.2). Tune the blend with
OW_HYBRID_BETA (default 0.5); OW_HYBRID_BETA=0 is byte-identical to v3.2.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_DIR = os.path.dirname(_HERE)  # competitions/orbit-wars/agent
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

os.environ.setdefault("OW_HYBRID", "1")
os.environ.setdefault("OW_HYBRID_BETA", "0.5")

from main import agent  # noqa: E402,F401  (kaggle_environments calls `agent(obs)`)
