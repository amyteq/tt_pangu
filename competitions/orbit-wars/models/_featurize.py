"""Shared candidate -> fixed numeric feature vector for the scorer (train/eval/export share it).

Thin wrapper over `core.features.feature_vector` — the SINGLE source of truth for the feature
contract, so the offline trainer here and the online scorer (agent/hybrid_model.py) can never
drift. Reads a `candidates.jsonl` row (from datasets/build_candidate_dataset.py): the nested
`candidate_features_json` (core.features.candidate_features output) + the row's `ship_bucket`.
"""

from __future__ import annotations

import os
import sys

_COMP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _COMP not in sys.path:
    sys.path.insert(0, _COMP)
from core.features import FEATURE_NAMES, feature_vector  # noqa: E402

FEATURES = FEATURE_NAMES
N_FEATURES = len(FEATURES)


def featurize(row) -> list[float]:
    cf = row.get("candidate_features_json") or {}
    return feature_vector(cf, row.get("ship_bucket"))


def label(row) -> float:
    """Imitation label: did the teacher (real player) launch this candidate that step."""
    return 1.0 if row.get("teacher_selected") else 0.0


def group_key(row):
    """Ranking group = one decision point (episode, step, player)."""
    return (row.get("episode_id"), row.get("step"), row.get("player_id"))
