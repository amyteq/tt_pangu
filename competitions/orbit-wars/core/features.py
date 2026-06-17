"""Candidate-launch feature extraction (for the RuleEngine now, a model scorer later).

A `candidate` is a proposed launch: {"source": pid, "target": pid, "ships": int}.
`candidate_features` returns a flat, deterministic dict combining battlefield-state
fields for the source and target with the FlightOracle's path verdict.
"""

from __future__ import annotations

from .oracle import FlightOracle

# ---------------------------------------------------------------------------
# Model feature contract — the SINGLE source of truth shared by the offline
# trainer (models/_featurize.py) and the online scorer (agent/hybrid_model.py).
# Order is load-bearing: it must match the weights' input order exactly.
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
    "ships",
    "ship_bucket",
    "remaining_steps",
    "phase",
    "src_ships",
    "src_defense_slack",
    "src_is_hub",
    "src_is_safe_bank",
    "tgt_owner_is_own",
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
_PHASE = {"opening": 0.0, "midgame": 1.0, "endgame": 2.0}
SHIP_BUCKETS = [(0, 20), (20, 50), (50, 120), (120, 10**9)]


def ship_bucket_of(n) -> int:
    n = int(n or 0)
    for i, (lo, hi) in enumerate(SHIP_BUCKETS):
        if lo <= n < hi:
            return i
    return len(SHIP_BUCKETS) - 1


def _ff(d, k, default=0.0):
    v = d.get(k, default)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def feature_vector(cf: dict, ship_bucket=None) -> list[float]:
    """Map a candidate_features() dict -> the fixed FEATURE_NAMES float vector (pure Python).

    ship_bucket is passed through from the dataset row when available; otherwise it is derived
    from the candidate ship count with the same bucketing the dataset builder uses.
    """
    cf = cf or {}
    if ship_bucket is None:
        ship_bucket = ship_bucket_of(_ff(cf, "ships"))
    tgt_owner = cf.get("tgt_owner")
    my_id = cf.get("my_id")
    # distinguish OWN / ENEMY / NEUTRAL — never encode "owner != -1" as enemy (that mislabels our
    # own planets, e.g. reinforcement targets). own requires knowing my_id (carried in cf).
    is_own = 1.0 if (tgt_owner is not None and my_id is not None and tgt_owner == my_id) else 0.0
    is_neutral = 1.0 if (tgt_owner == -1) else 0.0
    is_enemy = 1.0 if (tgt_owner not in (None, -1) and not is_own) else 0.0
    return [
        _ff(cf, "ships"),
        float(ship_bucket),
        _ff(cf, "remaining_steps"),
        _PHASE.get(cf.get("phase"), 0.0),
        _ff(cf, "src_ships"),
        _ff(cf, "src_defense_slack"),
        _ff(cf, "src_is_hub"),
        _ff(cf, "src_is_safe_bank"),
        is_own,
        is_enemy,
        is_neutral,
        _ff(cf, "tgt_strategic_value"),
        _ff(cf, "tgt_roi"),
        _ff(cf, "tgt_holdability"),
        _ff(cf, "tgt_pressure"),
        _ff(cf, "tgt_frontier"),
        _ff(cf, "tgt_centrality"),
        _ff(cf, "tgt_is_comet"),
        _ff(cf, "tgt_reinforcement_need"),
        _ff(cf, "tgt_threat_window"),
        _ff(cf, "path_valid"),
        _ff(cf, "path_eta"),
        _ff(cf, "path_min_sun_distance"),
        _ff(cf, "path_near_sun"),
        1.0 if cf.get("path_first_hit_type") == "target" else 0.0,
    ]


def candidate_features(state, candidate, obs, oracle: FlightOracle | None = None) -> dict:
    oracle = oracle or FlightOracle()
    src = state.planets.get(candidate["source"])
    tgt = state.planets.get(candidate["target"])
    ships = int(candidate.get("ships", 1))
    me = state.glob.my_id
    feat = {
        "source_id": candidate["source"],
        "target_id": candidate["target"],
        "ships": ships,
        "my_id": me,  # so feature_vector can classify target ownership as own/enemy/neutral
        "phase": state.glob.phase,
        "remaining_steps": state.glob.remaining_steps,
    }
    if src is not None:
        feat.update(
            {
                "src_owner_is_me": int(src.owner == me),
                "src_ships": src.ships,
                "src_defense_slack": src.defense_slack,
                "src_is_hub": int(src.is_hub_candidate),
                "src_is_safe_bank": int(src.is_safe_bank),
            }
        )
    if tgt is not None:
        feat.update(
            {
                "tgt_owner": tgt.owner,
                "tgt_strategic_value": tgt.strategic_value_1_100,
                "tgt_roi": tgt.roi_value,
                "tgt_holdability": tgt.holdability,
                "tgt_pressure": tgt.pressure_score,
                "tgt_frontier": tgt.frontier_score,
                "tgt_centrality": tgt.centrality,
                "tgt_is_comet": int(tgt.is_comet),
                "tgt_reinforcement_need": tgt.reinforcement_need,
                "tgt_threat_window": tgt.threat_window if tgt.threat_window is not None else -1,
            }
        )
    # FlightOracle path verdict for this exact launch
    res = oracle.validate_target(obs, candidate["source"], candidate["target"], ships)
    feat.update(
        {
            "path_valid": int(res.valid),
            "path_first_hit_type": res.first_hit_type,
            "path_first_hit_id": res.first_hit_id if res.first_hit_id is not None else -1,
            "path_eta": res.eta if res.eta is not None else -1,
            "path_min_sun_distance": res.min_sun_distance if res.min_sun_distance is not None else -1.0,
            "path_near_sun": int(res.near_sun),
        }
    )
    return feat
