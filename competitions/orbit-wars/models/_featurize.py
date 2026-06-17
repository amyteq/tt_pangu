"""Shared candidate -> fixed numeric feature vector for the scorer (train/eval/export share it).

Reads a `candidates.jsonl` row (from datasets/build_candidate_dataset.py): the nested
`candidate_features_json` (core.features.candidate_features) + a few row fields. Categorical
fields are mapped to small ordinals so the exported npz model can run in pure numpy.
"""

from __future__ import annotations

_PHASE = {"opening": 0.0, "midgame": 1.0, "endgame": 2.0}

# ordered, fixed feature names = the model's input contract (exported alongside the npz weights)
FEATURES = [
    "ships",
    "ship_bucket",
    "remaining_steps",
    "phase",
    "src_ships",
    "src_defense_slack",
    "src_is_hub",
    "src_is_safe_bank",
    "tgt_owner_is_enemy",
    "tgt_owner_is_neutral",
    "tgt_strategic_value",
    "tgt_roi",
    "tgt_holdability",
    "tgt_pressure",
    "tgt_frontier",
    "tgt_centrality",
    "tgt_is_comet",
    "tgt_reinforcement_need",
    "tgt_threat_window",
    "path_valid",
    "path_eta",
    "path_min_sun_distance",
    "path_near_sun",
    "path_first_hit_is_target",
]
N_FEATURES = len(FEATURES)


def _f(d, k, default=0.0):
    v = d.get(k, default)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def featurize(row) -> list[float]:
    cf = row.get("candidate_features_json") or {}
    tgt_owner = cf.get("tgt_owner")
    return [
        _f(cf, "ships", _f(row, "ships")),
        _f(row, "ship_bucket"),
        _f(cf, "remaining_steps"),
        _PHASE.get(cf.get("phase"), 0.0),
        _f(cf, "src_ships"),
        _f(cf, "src_defense_slack"),
        _f(cf, "src_is_hub"),
        _f(cf, "src_is_safe_bank"),
        1.0 if (tgt_owner not in (None, -1)) else 0.0,
        1.0 if (tgt_owner == -1) else 0.0,
        _f(cf, "tgt_strategic_value"),
        _f(cf, "tgt_roi"),
        _f(cf, "tgt_holdability"),
        _f(cf, "tgt_pressure"),
        _f(cf, "tgt_frontier"),
        _f(cf, "tgt_centrality"),
        _f(cf, "tgt_is_comet"),
        _f(cf, "tgt_reinforcement_need"),
        _f(cf, "tgt_threat_window"),
        _f(cf, "path_valid"),
        _f(cf, "path_eta"),
        _f(cf, "path_min_sun_distance"),
        _f(cf, "path_near_sun"),
        1.0 if cf.get("path_first_hit_type") == "target" else 0.0,
    ]


def label(row) -> float:
    """Imitation label: did the teacher (real player) launch this candidate that step."""
    return 1.0 if row.get("teacher_selected") else 0.0


def group_key(row):
    """Ranking group = one decision point (episode, step, player)."""
    return (row.get("episode_id"), row.get("step"), row.get("player_id"))
