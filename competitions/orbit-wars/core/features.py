"""Candidate-launch feature extraction (for the RuleEngine now, a model scorer later).

A `candidate` is a proposed launch: {"source": pid, "target": pid, "ships": int}.
`candidate_features` returns a flat, deterministic dict combining battlefield-state
fields for the source and target with the FlightOracle's path verdict.
"""

from __future__ import annotations

from .oracle import FlightOracle


def candidate_features(
    state, candidate, obs, oracle: FlightOracle | None = None
) -> dict:
    oracle = oracle or FlightOracle()
    src = state.planets.get(candidate["source"])
    tgt = state.planets.get(candidate["target"])
    ships = int(candidate.get("ships", 1))
    me = state.glob.my_id
    feat = {
        "source_id": candidate["source"],
        "target_id": candidate["target"],
        "ships": ships,
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
                "tgt_threat_window": tgt.threat_window
                if tgt.threat_window is not None
                else -1,
            }
        )
    # FlightOracle path verdict for this exact launch
    res = oracle.validate_target(obs, candidate["source"], candidate["target"], ships)
    feat.update(
        {
            "path_valid": int(res.valid),
            "path_first_hit_type": res.first_hit_type,
            "path_first_hit_id": res.first_hit_id
            if res.first_hit_id is not None
            else -1,
            "path_eta": res.eta if res.eta is not None else -1,
            "path_min_sun_distance": res.min_sun_distance
            if res.min_sun_distance is not None
            else -1.0,
            "path_near_sun": int(res.near_sun),
        }
    )
    return feat
