"""Lightweight ECA-style RuleEngine — guardrails + tactical re-weighting, NOT a strategy.

Predicates read the BattlefieldState + FlightOracle verdict for a candidate; actions
either BLOCK a candidate (hard safety) or adjust its weight (tactical). The two
load-bearing guardrails wire the deterministic FlightOracle gate:
  TARGET_FIRST_HIT_VALID and SUN_SAFE -> block on failure.
Model scoring slots in later as another weight signal; this just builds the substrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .oracle import FlightOracle


@dataclass
class RuleVerdict:
    decision: str  # "allow" | "block"
    weight: float  # multiplicative weight on the candidate's base score (1.0 = neutral)
    reasons: list = field(default_factory=list)


# ---- predicates: (state, feat) -> bool -------------------------------------
def TARGET_FIRST_HIT_VALID(state, feat):
    return bool(feat.get("path_valid"))


def SUN_SAFE(state, feat):
    return feat.get("path_first_hit_type") != "sun"


def SOURCE_HAS_DEFENSE_SLACK(state, feat):
    return feat.get("src_defense_slack", 0.0) >= feat.get("ships", 0)


def TARGET_ROI_POSITIVE(state, feat):
    return feat.get("tgt_roi", 0.0) > 0.0


def TARGET_HOLDABLE(state, feat):
    return feat.get("tgt_holdability", 0.0) >= 0.5


def MY_CORE_UNDER_THREAT(state, feat=None):
    me = state.glob.my_id
    return any(
        p.owner == me and p.threat_window is not None and p.strategic_value_1_100 >= 50 for p in state.planets.values()
    )


def I_AM_4P_LEADER(state, feat=None):
    return state.glob.player_count >= 4 and state.glob.leader_id == state.glob.my_id


def I_AM_4P_UNDERDOG(state, feat=None):
    me = state.glob.my_id
    return state.glob.player_count >= 4 and state.players.get(me) is not None and state.players[me].rank_by_score >= 3


def ENEMY_FIELD_ARMY_COMMITTED(state, feat=None):
    me = state.glob.my_id
    for pl, ps in state.players.items():
        if pl != me and pl != -1:
            tot = ps.ships_on_planets + ps.ships_in_flight
            if tot > 0 and ps.ships_in_flight / tot >= 0.45:
                return True
    return False


def ENDGAME_SCORE_POSITIVE(state, feat):
    return state.glob.phase == "endgame" and feat.get("tgt_roi", 0.0) > 0.0


def COMET_PAYBACK_POSITIVE(state, feat):
    # blocker: comet expiry/path not modelled (schema doc) -> conservative False
    return False


class RuleEngine:
    def __init__(self, oracle: FlightOracle | None = None):
        self.oracle = oracle or FlightOracle()

    def evaluate(self, state, feat) -> RuleVerdict:
        reasons = []
        # --- hard safety guardrails (deterministic FlightOracle gate) ---
        if not SUN_SAFE(state, feat):
            return RuleVerdict("block", 0.0, ["SUN_SAFE failed: strict_sun_collision"])
        if not TARGET_FIRST_HIT_VALID(state, feat):
            return RuleVerdict(
                "block",
                0.0,
                [
                    f"TARGET_FIRST_HIT_VALID failed: {feat.get('path_first_hit_type')} "
                    f"{feat.get('path_first_hit_id')} before target"
                ],
            )
        # --- tactical re-weighting ---
        w = 1.0
        if feat.get("path_near_sun"):
            w *= 0.9
            reasons.append("near_sun_warning -> -10%")
        if not SOURCE_HAS_DEFENSE_SLACK(state, feat):
            w *= 0.6
            reasons.append("source lacks defense slack -> -40%")
        if not TARGET_HOLDABLE(state, feat):
            w *= 0.8
            reasons.append("target not holdable -> -20%")
        if TARGET_ROI_POSITIVE(state, feat):
            w *= 1.1
            reasons.append("positive ROI -> +10%")
        if MY_CORE_UNDER_THREAT(state) and not (feat.get("tgt_owner") == state.glob.my_id):
            w *= 0.7
            reasons.append("core under threat, non-defensive launch -> -30%")
        if I_AM_4P_LEADER(state):
            w *= 0.9
            reasons.append("4p leader: damp over-extension -> -10%")
        elif I_AM_4P_UNDERDOG(state):
            w *= 1.05
            reasons.append("4p underdog: press expansion -> +5%")
        return RuleVerdict("allow", round(w, 3), reasons)
