"""
Orbit Wars agent — v3.2 "Forecast" (t14-tuned forward-sim differential planner).

Strategy summary (see competitions/orbit-wars/README.md for the full design):
  - Predict every planet's exact future position from `initial_planets` +
    `angular_velocity` (the engine rotates orbiting planets deterministically:
    angle = initial_angle + angular_velocity * step).
  - For each affordable target, solve a fixed-point INTERCEPT: the fleet flies a
    straight line at a size-dependent speed, the target moves on its orbit, so we
    iterate arrival-time T until it converges, then aim at the predicted arrival
    point — not the stale current position.
  - Use the engine's EXACT capture rule: a single attacker captures iff
    ships > garrison_at_arrival. Neutrals don't produce; enemy planets gain
    production * T while the fleet is in flight, so we lead that growth.
  - Avoid launches whose straight path would clip the sun or any other planet
    (the engine resolves the FIRST planet a fleet touches, so a bad angle wastes
    the whole fleet).
  - Keep a defensive reserve on planets that have inbound enemy fleets.
  - Greedy global allocation: each target is committed at most once (no overkill),
    ranked by production-per-ship discounted by travel time.

Robustness: the whole body is wrapped so any unexpected error yields an empty
move list (stay passive but ALIVE) rather than crashing — a crash forfeits.
"""

import math
import os as _os

# === config — single place that reads OW_* env overrides (OW-ARCH-001 config layer) ===
# Resolution per knob: env OW_* -> baked default (agent/config_baked.py) -> the inline literal
# kept here as a safety net. With nothing set this is byte-identical to the old inline
# os.environ.get(...) defaults (golden-verified). See core/config.py and config/README.md.
from . import config as _C  # noqa: E402

# === physics/geometry — single source is core.geometry (OW-ARCH-001 dedup) ===
# These names are kept as thin aliases so all call sites below are unchanged; the implementations
# (and the B11 planet-rotation phase fix) live ONLY in core/geometry.py now.
from . import geometry as _G  # noqa: E402

BOARD = _G.BOARD
CENTER = _G.CENTER
SUN_R = _G.SUN_R
ROT_LIMIT = _G.ROT_LIMIT
MAX_SPEED = _G.MAX_SPEED

fleet_speed = _G.fleet_speed
_seg_point_dist = _G.seg_point_dist
_swept_hit = _G.swept_hit
_resolve_combat = _G.resolve_combat
_planet_pos = _G.planet_pos


replay_planet = _G.replay_planet
project = _G.project


def signed_adv(owner_list, ships_list, me, H, gamma=0.97):
    """Discounted advantage of one planet's trajectory: +my ships, -opponent ships,
    0 for neutral, summed over k=1..H with a tempo discount."""
    s = 0.0
    g = 1.0
    for k in range(1, H + 1):
        g *= gamma
        o = owner_list[k]
        if o == me:
            s += g * ships_list[k]
        elif o != -1:
            s -= g * ships_list[k]
    return s


# === aliases ===
_project = project
_replay = replay_planet

# T2-R2 BAKED (2026-06-12, issue #87): t14 config confirmed on two independent
# 300-game blocks (snorlax 13000+: 17.7%, local 15000+: 19.0% vs baseline ~12%;
# pooled +6.7pt, z~3.3). Defaults below = t14: H26/FF5/FD20/CE3.2/CL1.3.
PROJ_H = _C.geti("OW_PROJ_H", 26)  # forward-sim horizon; 18 too short for slow opening fleets
# Multi-source coordination (the strong-tier lever): pool ships from several friendly
# planets onto one target, sized to capture AND hold (vs single-source minimal captures
# that get retaken). Staggered waves grind the defender; total = needed * HOLD_MULT.
MULTISRC = _C.geti("OW_MULTISRC", 0)  # default OFF: tried, no gain vs strong tier
HOLD_MULT = _C.getf("OW_HOLD_MULT", 1.6)
# Opening expander: the differential value-gate is too conservative early (we fire 2-3x
# in the first 25 turns while strong agents grab 5 planets). In the opening, grab every
# reachable neutral with positive production-gain over a long opening horizon, firing
# aggressively (no value-gate, no in-flight cap) to win the land-grab.
OPENING = _C.geti("OW_OPENING", 0)  # default OFF: fired more but win-rate dropped
OPENING_TURNS = _C.geti("OW_OPENING_TURNS", 25)
OPENING_H = _C.geti("OW_OPENING_H", 50)
# T8 — true co-arrival strikes (issue #87). Unlike MULTISRC (same-turn salvo: fleets
# from different distances arrive on DIFFERENT turns and are defeated in detail), this
# aligns ARRIVAL turns: pick an arrival turn K, fire the sources whose min ETA equals K
# now, and RESERVE nearer sources (they re-derive their own fire turn on a later replan,
# when the in-flight wave shows up in the do-nothing projection's arrival schedule and
# their min ETA matches its arrival turn). The engine sums same-turn arrivals by owner,
# so an aligned wave fights as one stack. Targets only planets no single source can take.
COARRIVAL = _C.geti("OW_COARRIVAL", 0)
COARR_MAX_SRC = _C.geti("OW_COARR_MAX_SRC", 4)  # wave fragmentation cap
COARR_HOLD = _C.getf("OW_COARR_HOLD", 1.0)  # extra force mult to hold
# T11 — ledger-constrained availability (issue #87, ChatGPT §9-2 dynamic defense
# reserve). avail = min(current rule, ledger slack), where slack = min projected
# garrison over the do-nothing trajectory's HELD turns (kuni05's safe_drain bound).
# CONSTRAINT-ONLY: never frees more ships than the static rule (v3a failed by using
# the same bound to free MORE); a planet projected to flip has nothing to protect
# (the defense module handles it) -> no cap.
LEDGER = _C.geti("OW_LEDGER", 0)
# K±tol merging (T8 v2): a share whose exact-size ETA lands at K+1..K+tol joins the
# wave anyway (fires now, valued at its true arrival turn) instead of aborting the
# whole wave; shares slower than K+tol are dropped, not wave-fatal. tol=0 ~= v1.
COARR_TOL = _C.geti("OW_COARR_TOL", 1)

try:
    from kaggle_environments.envs.orbit_wars.orbit_wars import Planet, Fleet
except Exception:  # pragma: no cover - fallback if import path changes
    from collections import namedtuple

    Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
    Fleet = namedtuple("Fleet", ["id", "owner", "x", "y", "angle", "from_planet_id", "ships"])

# Engine constants (mirrored from orbit_wars.py).
BOARD_SIZE = 100.0
CENTER = BOARD_SIZE / 2.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0  # configuration.shipSpeed default
EPISODE_STEPS = 500

# Tunables.
ENEMY_BUFFER = 2  # extra ships over the exact capture threshold for enemy planets
PATH_CLEARANCE = 1.0  # extra margin when testing whether a path clips a planet
DEFENSE_HORIZON = 18  # ticks ahead we consider an inbound enemy fleet a threat
TIME_DISCOUNT = 0.04  # how strongly to prefer near targets in the value score

# --- v2: hold what you take (fixes v1's capture-churn / leaky-expansion loss) ---
# v1 left captured planets at ~0 garrison and poured the empire into transit, so
# starter retook them and out-produced. v2 keeps a STANDING garrison on every planet
# and caps how much of the empire may be in flight at once.
# v2 defaults tuned via arena sweep vs the frozen v1 snapshot. The decisive lever is
# the in-flight cap (don't over-commit the empire into transit); a small frontier
# garrison complements it. Heavy garrison / a tight cap (<1.0) over-corrects and loses.
REAR_FLOOR = _C.getf("OW_REAR_FLOOR", 0)  # garrison kept on a safe (rear) planet
FRONTIER_FLOOR = _C.getf("OW_FRONTIER_FLOOR", 5)  # garrison kept on a planet near an enemy
FRONTIER_DIST = _C.getf("OW_FRONTIER_DIST", 20.0)  # enemy planet within this distance => frontier
GARRISON_PROD_MULT = _C.getf("OW_PROD_MULT", 0)  # extra standing garrison per unit production
INFLIGHT_CAP_FRAC = _C.getf("OW_INFLIGHT_CAP", 1.2)  # cap in-flight at this frac of on-planet ships
# Phase-scaled cap: looser early (win the land-grab) -> tighter late (hold and bank).
# Tuned via arena sweep vs the flat-1.2 v2 snapshot; mild scaling (2.0 -> 1.0) won,
# aggressive scaling (2.5-3.0 early / 0.6-0.8 late) lost. Linearly interpolated by step.
CAP_EARLY = _C.getf("OW_CAP_EARLY", 3.2)
CAP_LATE = _C.getf("OW_CAP_LATE", 1.3)
# === 4p-aware mode (KCT-OW-LIVE-002) ===========================================
# The ladder runs BOTH 2p and 4p episodes and BOTH update mu (~half are 4p,
# verified from the flyingfox 205-episode history); our value function was tuned
# 2p-only and is owner-BLIND across rivals. This mode triggers ONLY when >=3
# distinct rival owners are present, so 2p play is byte-identical (provable).
# In 4p mu is placement-vs-rating (avg_rank), and the flyingfox 4p analysis
# showed losers get ELIMINATED in the t35-110 gauntlet while winners expand
# fast on NEUTRALS and don't paint a target by early PvP. Three env-gated knobs:
FOURP_MODE = _C.geti("OW_4P_MODE", 0)  # master gate
FOURP_ATK_SCALE = _C.getf("OW_4P_ATK_SCALE", 0.5)  # opening PvP damping
FOURP_PEACE = _C.geti("OW_4P_PEACE_TURNS", 25)  # "no early aggressor" window
FOURP_RIVAL_W = _C.getf("OW_4P_RIVAL_W", 1.0)  # weight hurting the leader
FOURP_CAP_BUMP = _C.getf("OW_4P_CAP_BUMP", 0.0)  # survival reserve bump
# Consolidation: forward an idle rear planet's surplus to the friendly planet nearest the
# front (the getting-started tutorial's flaw #4). DEFAULT OFF — an arena sweep showed it
# never beats v2.1: harmful when aggressive (min=12 -> 30% vs v2.1), at best neutral when
# rare (min>=30 -> 40-40). Our aggression already uses rear ships efficiently; forwarding
# them wastes transit, starves the in-flight cap, and funnels the empire into fewer launch
# points. Code kept (env-gated) so the result stays reproducible via OW_CONSOLIDATE=1.
CONSOLIDATE = _C.geti("OW_CONSOLIDATE", 0)
CONSOLIDATE_MIN = _C.getf("OW_CONSOLIDATE_MIN", 12)  # min surplus to bother (tiny fleets crawl)
CONSOLIDATE_MARGIN = _C.getf("OW_CONSOLIDATE_MARGIN", 3.0)  # front-distance gain required


def _hypot(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


# Duplicates of core.geometry primitives -> aliases (single source = core.geometry).
_fleet_speed = _G.fleet_speed
_point_to_segment = _G.seg_point_dist


def _predict_pos(pid, future_step, init_by_id, ang_vel):
    """Predicted (x, y) of planet `pid` AS OBSERVED at absolute game `future_step` (None if unknown).
    Delegates to core.geometry.planet_pos — the single source (carries the B11 phase fix)."""
    ip = init_by_id.get(pid)
    if ip is None:
        return None
    return _G.planet_pos(ip[2], ip[3], ip[4], ang_vel, future_step)


_solve_intercept = _G.solve_intercept


def _path_blocked(mx, my, tx, ty, mine_id, tgt_id, planets, comet_ids):
    """True if the straight launch path clips the sun or any non-target planet.

    The engine consumes a fleet on the FIRST planet it touches, so this guards
    against wasting a fleet on an unintended body en route.
    """
    if _point_to_segment(CENTER, CENTER, mx, my, tx, ty) < SUN_RADIUS:
        return True
    for p in planets:
        if p.id == mine_id or p.id == tgt_id or p.id in comet_ids:
            continue
        if _point_to_segment(p.x, p.y, mx, my, tx, ty) < p.radius + PATH_CLEARANCE:
            return True
    return False


def _garrison_floor(planet, enemy_planets):
    """Standing garrison to keep on a planet even with no visible inbound fleet.

    Higher near enemies (frontier) so captured planets are held, not churned.
    """
    base = REAR_FLOOR
    for ep in enemy_planets:
        if _hypot(planet.x, planet.y, ep.x, ep.y) < FRONTIER_DIST:
            base = FRONTIER_FLOOR
            break
    return base + GARRISON_PROD_MULT * planet.production


def _front_dist(p, targets):
    """Distance from an owned planet to the nearest non-owned (enemy/neutral) planet."""
    if not targets:
        return float("inf")
    return min(_hypot(p.x, p.y, t.x, t.y) for t in targets)


def _incoming_threat(planet, fleets, player):
    """Approx enemy ships that will reach `planet` within DEFENSE_HORIZON ticks."""
    threat = 0
    for f in fleets:
        if f.owner == player:
            continue
        speed = _fleet_speed(f.ships)
        # Project planet offset onto the fleet heading.
        hx, hy = math.cos(f.angle), math.sin(f.angle)
        rx, ry = planet.x - f.x, planet.y - f.y
        proj = rx * hx + ry * hy
        if proj <= 0 or proj > speed * DEFENSE_HORIZON:
            continue
        perp = abs(rx * (-hy) + ry * hx)
        if perp < planet.radius + 2.0:
            threat += f.ships
    return threat


# --- FlightOracle execution gate (OW-P0-FLIGHT-ORACLE-001) -------------------
# Final emission passes through core.action_sanitizer, which drops provably-fatal launches
# (strict sun collision / out-of-bounds) via the deterministic FlightOracle. Import-guarded:
# active when core/ is importable (locally, in the arena, or in a tar.gz that bundles core/
# beside main.py); a transparent no-op otherwise, and ANY failure falls back to the raw moves
# so the gate can never break or starve the agent. Disable with OW_NO_SANITIZE=1; set
# OW_SANITIZE_LOG=<path> to append per-turn counters (off by default online).
_SANITIZE = _C.geti("OW_NO_SANITIZE", 0) == 0
# Opt-in wrong-first-hit / landing-target-mismatch gate. Default OFF to preserve current behavior
# (the v3.2 path-checks its own launches; with the B11 fix its first-hit ~always = intended target).
# Turn on via OW_BLOCK_WRONG_HIT=1 once intended-target intent is threaded through emission.
_BLOCK_WRONG_HIT = _C.geti("OW_BLOCK_WRONG_HIT", 0) == 1


def _emit_gate(obs, moves, targets=None):
    """Final emission gate (layer [7]) via core.action_emitter.ActionEmitter: always drops
    provably-fatal sun/oob; the wrong-first-hit gate is opt-in (OW_BLOCK_WRONG_HIT) and uses the
    intended `targets`. Any failure (core unavailable / single-file) returns the raw moves."""
    if not _SANITIZE or not moves:
        return moves
    try:
        from .action_emitter import ActionEmitter
        from .action_sanitizer import new_counters

        ctr = new_counters()
        emitter = ActionEmitter(block_wrong_first_hit=_BLOCK_WRONG_HIT, horizon=60)
        clean = emitter.emit(obs, moves, targets=targets, counters=ctr)
        _log = _C.getstr("OW_SANITIZE_LOG", "")
        if _log:
            import json as _json

            with open(_log, "a") as _f:
                _f.write(_json.dumps({"step": obs.get("step"), **ctr}) + "\n")
        return clean
    except Exception:
        return moves  # core/ unavailable (single-file submission) or any error -> raw moves


# --- Hybrid model re-ranker (OW-P2-HYBRID-001, prompt 06) --------------------
# A trained candidate scorer (agent/hybrid_model.py + hybrid_weights.json) RE-ORDERS the
# v3.2 candidate list before the greedy commit. It changes only WHICH equally-affordable
# candidates win the budget — never the sizing, the path/oracle safety, or the value sim.
# Strictly additive over the deterministic core: OFF by default (OW_HYBRID=0), and any
# failure (missing weights / core / inference error) falls back to the plain value order,
# so the agent is never worse than v3.2 by construction. Blend is RANK-based so the model's
# [0,1] score and the sim's arbitrary-scale value compose cleanly; OW_HYBRID_BETA=0 is
# byte-identical to v3.2 (model rank ignored). Only the top OW_HYBRID_TOPN candidates are
# scored (bounds runtime; the budget commits only a handful anyway).
# Read at CALL time (not module load): the arena pool clears OW_* per task and reuses workers,
# so a cached `main` module must re-read the env each turn or hybrid would silently misfire.
def _hybrid_cfg():
    return (
        _C.geti("OW_HYBRID", 0),
        _C.getf("OW_HYBRID_BETA", 0.5),
        _C.geti("OW_HYBRID_TOPN", 80),
    )


_HYBRID_SCORER = None
_HYBRID_TRIED = False


def _hybrid_scorer():
    global _HYBRID_SCORER, _HYBRID_TRIED
    if _HYBRID_TRIED:
        return _HYBRID_SCORER
    _HYBRID_TRIED = True
    try:
        import sys as _sys

        _here = _os.path.dirname(_os.path.abspath(__file__))  # core/
        _comp = _os.path.dirname(_here)
        # hybrid_model.py lives in agent/ (core/ sibling); add agent dir + comp root to path
        for _p in (_os.path.join(_comp, "agent"), _comp):
            if _p and _p not in _sys.path:
                _sys.path.insert(0, _p)
        from hybrid_model import load_default

        _HYBRID_SCORER = load_default()
    except Exception:
        _HYBRID_SCORER = None
    return _HYBRID_SCORER


def _hybrid_rerank(obs, candidates):
    """Return candidates re-ordered by a rank blend of (v3.2 value, model score).

    candidates: list of (value, src_id, tgt_id, angle, needed). Any failure -> the plain
    value-sorted order (identical to v3.2), so the re-ranker can never break the agent.
    """
    _, beta, topn = _hybrid_cfg()
    by_value = sorted(candidates, reverse=True, key=lambda c: c[0])
    sc = _hybrid_scorer()
    if sc is None or beta <= 0.0 or len(by_value) < 2:
        return by_value
    try:
        from .features import candidate_features, ship_bucket_of
        from .oracle import FlightOracle
        from .state import build_battlefield_state

        state = build_battlefield_state(obs, horizon=PROJ_H)
        orc = FlightOracle()
        top = by_value[:topn]
        rest = by_value[topn:]
        model = []
        for value, src_id, tgt_id, angle, needed in top:
            cf = candidate_features(state, {"source": src_id, "target": tgt_id, "ships": int(needed)}, obs, orc)
            model.append(sc.score_cf(cf, ship_bucket_of(needed)))
        # rank blend: lower combined rank = commit earlier
        order_v = sorted(range(len(top)), key=lambda i: -top[i][0])
        order_m = sorted(range(len(top)), key=lambda i: -model[i])
        rv = [0] * len(top)
        rm = [0] * len(top)
        for r, i in enumerate(order_v):
            rv[i] = r
        for r, i in enumerate(order_m):
            rm[i] = r
        blended = sorted(
            range(len(top)),
            key=lambda i: (1.0 - beta) * rv[i] + beta * rm[i],
        )
        return [top[i] for i in blended] + rest
    except Exception:
        return by_value


# --- RuleEngine guardrail / re-weight layer [6] (OW-ARCH-001) ----------------
# Wires core.rule_engine.RuleEngine into the candidate flow. PASS-THROUGH BY DEFAULT
# (OW_RULE_ENGINE=0): the candidate list is returned unchanged, so behavior is byte-identical
# to v3.2 (golden-verified). When enabled it builds the BattlefieldState + per-candidate feature
# dict (the same machinery the hybrid re-ranker uses), drops candidates the deterministic
# guardrails BLOCK (e.g. sun collision / wrong first-hit), and scales each candidate's value by
# the tactical weight before the greedy commit re-sorts. Read at CALL time (arena reuses workers
# and clears OW_*); any failure -> the candidates unchanged, so it can never break or starve the
# agent. EXPERIMENTAL / OFF by default — not yet shown to beat v3.2; the wiring is the deliverable.
def _rule_gate(obs, candidates):
    if not _C.geti("OW_RULE_ENGINE", 0) or not candidates:
        return candidates
    try:
        from .features import candidate_features
        from .oracle import FlightOracle
        from .rule_engine import RuleEngine
        from .state import build_battlefield_state

        state = build_battlefield_state(obs, horizon=PROJ_H)
        orc = FlightOracle()
        eng = RuleEngine(orc)
        out = []
        for value, src_id, tgt_id, angle, needed in candidates:
            cf = candidate_features(state, {"source": src_id, "target": tgt_id, "ships": int(needed)}, obs, orc)
            verdict = eng.evaluate(state, cf)
            if verdict.decision == "block":
                continue
            out.append((value * verdict.weight, src_id, tgt_id, angle, needed))
        return out
    except Exception:
        return candidates  # core/ unavailable or any error -> unchanged (byte-identical to v3.2)


def agent(obs):
    try:
        result = _agent(obs)
    except Exception:
        return []
    # _agent returns either bare moves or (moves, intended_targets). Preserve target intent through
    # to the emission gate so the (opt-in) wrong-first-hit sanitizer can use it; None => sun/oob only.
    if isinstance(result, tuple):
        moves, targets = result
    else:
        moves, targets = result, None
    return _emit_gate(obs, moves, targets)


def _agent(obs):
    player = obs.get("player", 0)
    raw_planets = obs.get("planets", []) or []
    raw_fleets = obs.get("fleets", []) or []
    ang_vel = obs.get("angular_velocity", 0.0) or 0.0
    init_planets = obs.get("initial_planets", []) or []
    comet_ids = set(obs.get("comet_planet_ids", []) or [])
    step = int(obs.get("step", 0) or 0)

    planets = [Planet(*p) for p in raw_planets]
    fleets = [Fleet(*f) for f in raw_fleets]
    init_by_id = {p[0]: p for p in init_planets}

    my_planets = [p for p in planets if p.owner == player]
    if not my_planets:
        return []

    enemy_planets = [p for p in planets if p.owner not in (-1, player) and p.id not in comet_ids]

    # 4p regime detection (no-op in 2p: triggers only with >= 3 distinct rivals).
    rival_owners = {p.owner for p in planets if p.owner not in (-1, player)}
    is_4p = bool(FOURP_MODE) and len(rival_owners) >= 3
    top_rival = None
    if is_4p:
        strength = dict.fromkeys(rival_owners, 0.0)
        for p in planets:
            if p.owner in strength:
                strength[p.owner] += p.ships
        top_rival = max(strength, key=strength.get) if strength else None

    # Reserve = standing garrison floor + any extra for currently-inbound enemy fleets.
    # The floor is the v2 fix: it lets freshly captured planets accumulate production
    # instead of being immediately re-emptied, which breaks v1's capture-churn loop.
    reserve = {}
    for mp in my_planets:
        floor = _garrison_floor(mp, enemy_planets)
        threat = _incoming_threat(mp, fleets, player)
        reserve[mp.id] = max(floor, threat)
        if is_4p:  # survival floor: clear the t35-110 4p elimination gauntlet
            reserve[mp.id] = max(reserve[mp.id], floor + FOURP_CAP_BUMP)

    # Global in-flight cap: don't pour the whole empire into simultaneous fleets.
    # Phase-scaled: interpolate from CAP_EARLY (step 0) to CAP_LATE (game end).
    cap_frac = CAP_EARLY + (CAP_LATE - CAP_EARLY) * min(1.0, step / EPISODE_STEPS)
    ships_on_planets = sum(mp.ships for mp in my_planets)
    ships_in_flight = sum(f.ships for f in fleets if f.owner == player)
    launch_budget = max(0.0, cap_frac * ships_on_planets - ships_in_flight)

    # Targets: anything we don't own and isn't a comet (comets handled later versions).
    targets = [p for p in planets if p.owner != player and p.id not in comet_ids]

    # --- Forecast: bit-exact do-nothing projection drives defender floors + value ---
    base_traj, base_arr = _project(raw_planets, raw_fleets, ang_vel, init_by_id, step, PROJ_H, comet_ids=comet_ids)
    prod_by_id = {p.id: p.production for p in planets}
    owner0_by_id = {p.id: p.owner for p in planets}
    ships0_by_id = {p.id: float(p.ships) for p in planets}

    def _term(o_list, s_list):
        # Terminal (k=H) signed advantage: +my ships, -opponent ships, 0 neutral.
        # Conservation-correct (ships in transit have landed by H), so launching is not
        # wrongly penalized; production accrued by H preserves tempo (earlier capture wins).
        o, s = o_list[PROJ_H], s_list[PROJ_H]
        if o == player:
            return s
        if o == -1:
            return 0.0
        if is_4p:
            # owner-aware in 4p: hurting the LEADER is worth more; force spent
            # against a small rival mostly hands tempo to a third party.
            return -s * (FOURP_RIVAL_W if o == top_rival else 1.0 / FOURP_RIVAL_W)
        return -s

    def _base_adv(pid):
        t = base_traj.get(pid)
        return _term(t["owner"], t["ships"]) if t else 0.0

    def _defense_needed(pid):
        """Reinforcement to keep an owned planet held: replay its do-nothing arrivals;
        at the first turn it flips to an enemy, return that enemy surplus (+1) — what we'd
        need to have added to survive. 0 if the planet holds on its own."""
        o_list, s_list = _replay(
            owner0_by_id[pid],
            ships0_by_id[pid],
            prod_by_id[pid],
            base_arr.get(pid, []),
            PROJ_H,
        )
        for k in range(1, PROJ_H + 1):
            if o_list[k] != player and o_list[k] != -1:
                return s_list[k] + 1.0
        return 0.0

    # Add our own planets the projection shows flipping to an enemy within H (reinforce).
    defense_need = {}
    for mp in my_planets:
        dn = _defense_needed(mp.id)
        if dn > 0:
            defense_need[mp.id] = dn
            targets.append(mp)

    def _ledger_slack(pid):
        """T11: max ships sheddable now while the do-nothing projection keeps the
        planet held (min garrison over held turns). Flipping planet -> inf (nothing
        to protect; defense module reinforces it instead)."""
        t = base_traj.get(pid)
        if t is None:
            return float("inf")
        slack = float("inf")
        for k in range(1, PROJ_H + 1):
            o = t["owner"][k]
            if o == player:
                slack = min(slack, t["ships"][k])
            elif o != -1:
                return float("inf")  # projected to flip -> doomed, no cap
        return slack

    ledger_cap = {mp.id: _ledger_slack(mp.id) for mp in my_planets} if LEDGER else {}

    def _avail(mp):
        a = mp.ships - reserve.get(mp.id, 0)
        if LEDGER:
            a = min(a, ledger_cap.get(mp.id, float("inf")))
        return a

    # --- Opening expander: aggressive land-grab for the first OPENING_TURNS turns ---
    if OPENING and step < OPENING_TURNS:
        op_avail = {mp.id: mp.ships - reserve.get(mp.id, 0) for mp in my_planets}
        op_cands = []
        for mp in my_planets:
            if op_avail[mp.id] <= 0:
                continue
            for tgt in targets:
                if tgt.id == mp.id or tgt.owner == player:
                    continue  # opening grabs neutral/enemy; defense handled post-opening
                ships_guess = max(1, tgt.ships + 1)
                sol = None
                needed = ships_guess
                eta = 1
                for _ in range(3):
                    sol = _solve_intercept(mp.x, mp.y, tgt.id, ships_guess, step, init_by_id, ang_vel)
                    if sol is None:
                        break
                    _, eta, _ = sol
                    bt = base_traj.get(tgt.id)
                    defn = bt["ships"][min(int(eta), PROJ_H)] if bt is not None else tgt.ships
                    needed = int(defn) + (1 if tgt.owner == -1 else 1 + ENEMY_BUFFER)
                    if needed == ships_guess:
                        break
                    ships_guess = needed
                if sol is None:
                    continue
                angle, eta, pos = sol
                if needed > op_avail[mp.id] or step + eta > EPISODE_STEPS - 2:
                    continue
                if _path_blocked(mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids):
                    continue
                gain = prod_by_id[tgt.id] * (OPENING_H - eta) - needed  # production won minus cost
                if gain <= 0:
                    continue
                op_cands.append((gain, mp.id, tgt.id, angle, needed))
        op_cands.sort(reverse=True, key=lambda c: c[0])
        rem = dict(op_avail)
        taken = set()
        op_moves = []
        op_targets = []
        for _g, src_id, tgt_id, angle, needed in op_cands:
            if tgt_id in taken or rem.get(src_id, 0) < needed:
                continue
            op_moves.append([src_id, angle, int(needed)])
            op_targets.append(tgt_id)  # preserve intended target for the emission sanitizer
            rem[src_id] -= needed
            taken.add(tgt_id)
        if op_moves:
            return op_moves, op_targets

    candidates = []
    for mp in my_planets:
        avail = _avail(mp)
        if avail <= 0:
            continue
        base_src_adv = _base_adv(mp.id)
        for tgt in targets:
            if tgt.id == mp.id:
                continue  # a planet can't reinforce itself
            is_defense = tgt.id in defense_need
            if is_defense:
                # Reinforce an owned planet projected to flip: size = the deficit.
                needed = max(1, int(math.ceil(defense_need[tgt.id])))
                sol = _solve_intercept(mp.x, mp.y, tgt.id, needed, step, init_by_id, ang_vel)
                if sol is None:
                    continue
                _, t_ticks, _ = sol
                eta_k = max(1, min(int(t_ticks), PROJ_H))
            else:
                # Offensive: required force = the SIM's projected defender at the arrival
                # turn (production + in-flight reinforcements baked in); iterate size->eta.
                ships_guess = max(1, tgt.ships + 1)
                sol = None
                needed = ships_guess
                eta_k = 1
                for _ in range(3):
                    sol = _solve_intercept(mp.x, mp.y, tgt.id, ships_guess, step, init_by_id, ang_vel)
                    if sol is None:
                        break
                    _, t_ticks, _ = sol
                    eta_k = max(1, min(int(t_ticks), PROJ_H))
                    bt = base_traj.get(tgt.id)
                    if bt is not None and bt["owner"][eta_k] == player:
                        needed = 1  # we'll already own it at arrival -> reinforce
                    else:
                        defender = bt["ships"][eta_k] if bt is not None else tgt.ships
                        buf = 1 if tgt.owner == -1 else 1 + ENEMY_BUFFER
                        needed = int(defender) + buf
                    if needed == ships_guess:
                        break
                    ships_guess = needed
            if sol is None:
                continue
            angle, t_ticks, pos = sol
            if needed > avail:
                continue
            if step + t_ticks > EPISODE_STEPS - 2:  # would arrive after game ends
                continue
            if t_ticks > PROJ_H:  # beyond the projection horizon -> can't score it
                continue
            if _path_blocked(mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids):
                continue
            # Value = simulated differential advantage: replay the two touched planets
            # with this launch (source debited now, target gets my arrival at eta) and
            # diff the signed (mine - opponent) advantage vs the do-nothing baseline.
            sw_o, sw_s = _replay(
                owner0_by_id[mp.id],
                ships0_by_id[mp.id] - needed,
                prod_by_id[mp.id],
                base_arr.get(mp.id, []),
                PROJ_H,
            )
            tw_arr = base_arr.get(tgt.id, []) + [(eta_k, player, float(needed))]
            tw_o, tw_s = _replay(
                owner0_by_id[tgt.id],
                ships0_by_id[tgt.id],
                prod_by_id[tgt.id],
                tw_arr,
                PROJ_H,
            )
            value = (_term(sw_o, sw_s) + _term(tw_o, tw_s)) - (base_src_adv + _base_adv(tgt.id))
            # 4p: don't be the early aggressor everyone gangs. Damp player-vs-
            # player attacks in the opening (neutral grabs untouched -> expansion
            # tempo, the actual 4p win driver, is preserved).
            if is_4p and step < FOURP_PEACE and tgt.owner not in (-1, player):
                value *= FOURP_ATK_SCALE
            if value <= 0:
                continue  # net-negative or pointless -> don't fire
            candidates.append((value, mp.id, tgt.id, angle, needed))

    # RuleEngine guardrail/re-weight layer [6] (OW-ARCH-001): pass-through by default
    # (OW_RULE_ENGINE=0) -> identical candidate list; enabled, it blocks/re-weights candidates.
    candidates = _rule_gate(obs, candidates)
    # Greedy commit order: v3.2 ranks by simulated value; the hybrid re-ranker (if enabled)
    # blends in the model's candidate score. OFF / on-failure -> identical value order.
    if _hybrid_cfg()[0]:
        candidates = _hybrid_rerank(obs, candidates)
    else:
        candidates.sort(reverse=True, key=lambda c: c[0])
    remaining = {mp.id: _avail(mp) for mp in my_planets}
    committed = set()
    moves = []
    move_targets = []  # intended target id parallel to each move (for the emission sanitizer)
    pos_by_id = {p.id: (p.x, p.y) for p in planets}

    def _flip_need(tgt, K):
        """Min extra friendly ships arriving exactly at turn K to OWN tgt at K, given
        the do-nothing arrival schedule (which already includes any of our in-flight
        waves — so a replan naturally tops up an in-progress strike). None if the
        projection already has us owning it at K."""
        arr = base_arr.get(tgt.id, [])
        bt = base_traj.get(tgt.id)
        if bt is None or bt["owner"][K] == player:
            return None
        # pre-combat garrison at K: replay with arrivals strictly before K
        o_pre, s_pre = _replay(
            owner0_by_id[tgt.id],
            ships0_by_id[tgt.id],
            prod_by_id[tgt.id],
            [a for a in arr if a[0] < K],
            K,
        )
        if o_pre[K] == player:
            return None
        g = s_pre[K]
        ours = sum(s for k, o, s in arr if k == K and o == player)
        by_o = {}
        for k, o, s in arr:
            if k == K and o != player:
                by_o[o] = by_o.get(o, 0.0) + s
        rival = max(by_o.values()) if by_o else 0.0
        buf = 1 + (ENEMY_BUFFER if o_pre[K] != -1 else 0)
        x = int(math.ceil(max(0.0, g + rival - ours))) + buf
        for _ in range(3):  # exact check (rank order / ties); bump if short
            o_chk, _s = _replay(
                owner0_by_id[tgt.id],
                ships0_by_id[tgt.id],
                prod_by_id[tgt.id],
                arr + [(K, player, float(x))],
                K,
            )
            if o_chk[K] == player:
                return x
            x += max(1, int(g * 0.1))
        return None

    # --- T8: co-arrival strikes on targets no single source can take ---
    # For each such target, enumerate arrival turns K from the sources' min ETAs.
    # Sources whose min ETA == K fire NOW; nearer sources are reserved and fire on a
    # later replan when the in-flight wave (visible in base_arr) counts down to their
    # own flight time — staggered launch, simultaneous arrival.
    if COARRIVAL:
        my_by_id = {mp.id: mp for mp in my_planets}
        covered = {c[2] for c in candidates}
        big = [t for t in targets if t.id not in covered and t.owner != player and t.id not in defense_need]
        big.sort(key=lambda t: -t.production)
        for tgt in big:
            if launch_budget < 1:
                break
            probes = {}  # source id -> min ETA at a representative size (path-clear)
            for mp in my_planets:
                avail = remaining.get(mp.id, 0)
                if avail < 1:
                    continue
                probe = max(1, min(int(avail), int(tgt.ships) + 1))
                sol = _solve_intercept(mp.x, mp.y, tgt.id, probe, step, init_by_id, ang_vel)
                if sol is None:
                    continue
                _a, t_ticks, pos = sol
                if _path_blocked(mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids):
                    continue
                probes[mp.id] = max(1, int(t_ticks))
            if len(probes) < 2:
                continue
            base_tgt_adv = _base_adv(tgt.id)
            for K in sorted(set(probes.values())):
                if K > PROJ_H or step + K > EPISODE_STEPS - 2:
                    continue
                need = _flip_need(tgt, K)
                if need is None:
                    continue
                need = int(math.ceil(need * COARR_HOLD))
                # fire-now members first (they define the wave), then largest garrison
                elig = sorted(
                    (m for m, eta in probes.items() if eta <= K),
                    key=lambda m: (0 if probes[m] == K else 1, -remaining.get(m, 0)),
                )[:COARR_MAX_SRC]
                if sum(remaining.get(m, 0) for m in elig) < need:
                    continue
                shares = []
                left = need
                for mid in elig:
                    if left <= 0:
                        break
                    give = int(min(remaining.get(mid, 0), left))
                    if give >= 1:
                        shares.append((mid, give))
                        left -= give
                if left > 0:
                    continue
                # exact ETA at each share's real size (speed is size-dependent).
                # K±tol merging: ETA in (K, K+tol] still fires now (valued at its
                # true arrival turn); ETA > K+tol drops the share, not the wave.
                fire_now, hold, kept, ok = [], [], 0, True
                for mid, give in shares:
                    mp = my_by_id[mid]
                    sol = _solve_intercept(mp.x, mp.y, tgt.id, give, step, init_by_id, ang_vel)
                    if sol is None:
                        ok = False
                        break
                    ang, t_ticks, pos = sol
                    t_ticks = max(1, int(t_ticks))
                    if t_ticks > K + COARR_TOL or t_ticks > PROJ_H:
                        continue  # too slow even with tolerance -> stays home
                    if t_ticks >= K:
                        if _path_blocked(mp.x, mp.y, pos[0], pos[1], mid, tgt.id, planets, comet_ids):
                            ok = False
                            break
                        fire_now.append((mid, ang, give, t_ticks))
                    else:
                        hold.append((mid, give))  # waits; hits K on a later replan
                    kept += give
                if not ok or not fire_now or kept < need:
                    continue
                if sum(g for _m, _a, g, _t in fire_now) > launch_budget:
                    continue
                # joint value gate: shares debited; fire-now lands at its true turn
                # (K..K+tol), held shares at K — the exact replay judges the spread.
                val = 0.0
                for mid, give in [(m, g) for m, _a, g, _t in fire_now] + hold:
                    sw_o, sw_s = _replay(
                        owner0_by_id[mid],
                        ships0_by_id[mid] - give,
                        prod_by_id[mid],
                        base_arr.get(mid, []),
                        PROJ_H,
                    )
                    val += _term(sw_o, sw_s) - _base_adv(mid)
                tw_arr = (
                    base_arr.get(tgt.id, [])
                    + [(t, player, float(g)) for _m, _a, g, t in fire_now]
                    + [(K, player, float(g)) for _m, g in hold]
                )
                tw_o, tw_s = _replay(
                    owner0_by_id[tgt.id],
                    ships0_by_id[tgt.id],
                    prod_by_id[tgt.id],
                    tw_arr,
                    PROJ_H,
                )
                val += _term(tw_o, tw_s) - base_tgt_adv
                if val <= 0:
                    continue
                for mid, ang, give, _t in fire_now:
                    moves.append([mid, ang, int(give)])
                    move_targets.append(tgt.id)
                    remaining[mid] -= give
                    launch_budget -= give
                for mid, give in hold:  # reserve so the greedy pass can't spend it
                    remaining[mid] -= give
                committed.add(tgt.id)
                break

    if not MULTISRC:
        # Single-source greedy (v3 behaviour; kept for A/B via OW_MULTISRC=0).
        for _value, src_id, tgt_id, angle, needed in candidates:
            if tgt_id in committed or needed > launch_budget:
                continue
            if remaining.get(src_id, 0) >= needed:
                moves.append([src_id, angle, int(needed)])
                move_targets.append(tgt_id)
                remaining[src_id] -= needed
                launch_budget -= needed
                committed.add(tgt_id)
    else:
        # Multi-source coordination: per target (best-value first), pool ships from the
        # nearest viable sources up to a hold force (capture + margin). Staggered waves
        # grind the defender; the engine sums same-turn arrivals. This is what the strong
        # tier does and our single-source minimal captures lacked.
        by_tgt = {}
        for value, src_id, tgt_id, angle, needed in candidates:
            by_tgt.setdefault(tgt_id, []).append((value, src_id, needed))
        # rank targets by their best single-source value
        order = sorted(by_tgt, key=lambda t: max(v for v, _, _ in by_tgt[t]), reverse=True)
        for tgt_id in order:
            entries = by_tgt[tgt_id]
            cap_needed = max(n for _, _, n in entries)  # single-source capture size
            hold_force = math.ceil(cap_needed * HOLD_MULT)
            tx, ty = pos_by_id[tgt_id]
            # nearest viable sources first (minimise travel, tightest co-arrival)
            srcs = sorted(
                {s for _, s, _ in entries},
                key=lambda s: _hypot(pos_by_id[s][0], pos_by_id[s][1], tx, ty),
            )
            accum = 0
            wave = []
            for src_id in srcs:
                if accum >= hold_force or launch_budget <= 0:
                    break
                give = int(min(remaining.get(src_id, 0), hold_force - accum, launch_budget))
                if give < 1:
                    continue
                sol = _solve_intercept(
                    pos_by_id[src_id][0],
                    pos_by_id[src_id][1],
                    tgt_id,
                    give,
                    step,
                    init_by_id,
                    ang_vel,
                )
                if sol is None:
                    continue
                ang, t_ticks, pos = sol
                if t_ticks > PROJ_H or step + t_ticks > EPISODE_STEPS - 2:
                    continue
                if _path_blocked(
                    pos_by_id[src_id][0],
                    pos_by_id[src_id][1],
                    pos[0],
                    pos[1],
                    src_id,
                    tgt_id,
                    planets,
                    comet_ids,
                ):
                    continue
                wave.append([src_id, ang, give])
                accum += give
                remaining[src_id] -= give
                launch_budget -= give
            # only keep the wave if it can at least capture (>= the single-source need)
            if accum >= cap_needed:
                moves.extend(wave)
                move_targets.extend([tgt_id] * len(wave))
                committed.add(tgt_id)
            else:
                for src_id, _ang, give in wave:  # refund partial commitment
                    remaining[src_id] += give
                    launch_budget += give

    # Consolidation pass: forward idle rear surplus toward the front.
    if CONSOLIDATE and targets:
        attacked = {m[0] for m in moves}
        fd = {p.id: _front_dist(p, targets) for p in my_planets}
        for src in my_planets:
            if src.id in attacked:  # only genuinely idle planets reposition
                continue
            surplus = remaining.get(src.id, 0)
            if surplus < CONSOLIDATE_MIN:
                continue
            # nearest friendly planet meaningfully closer to the front
            best, best_d = None, float("inf")
            for q in my_planets:
                if q.id == src.id or fd[q.id] >= fd[src.id] - CONSOLIDATE_MARGIN:
                    continue
                d = _hypot(src.x, src.y, q.x, q.y)
                if d < best_d:
                    best, best_d = q, d
            if best is None:
                continue
            sol = _solve_intercept(src.x, src.y, best.id, surplus, step, init_by_id, ang_vel)
            if sol is None:
                continue
            angle, _t, pos = sol
            if _path_blocked(src.x, src.y, pos[0], pos[1], src.id, best.id, planets, comet_ids):
                continue
            moves.append([src.id, angle, int(surplus)])
            move_targets.append(best.id)
            remaining[src.id] = 0
    return moves, move_targets


# --- Layered-policy facade (OW-ARCH-001) ------------------------------------
# Data-flow contract (the 8 layers; see ARCHITECTURE.md). `agent(obs)` above realizes it:
#
#   obs
#     -> load_config()                 core.config (env OW_* -> baked profile -> literal)   [cfg]
#     -> physics primitives            core.geometry (single source; B11 rotation fix)      [0]
#     -> BattlefieldState.from_obs     core.state.build_battlefield_state (default path: the [1]
#                                        v3.2 inline forward-sim; core.state used by features/ledger)
#     -> Arrival/Threat ledger         core.ledger (+ the inline do-nothing projection)      [2]
#     -> candidate generation          inline v3.2 intercept solve -> (value,src,tgt,ang,n)  [3]
#                                        (core.candidates.CandidateAction is the typed form)
#     -> candidate_features            core.features (own/enemy/neutral; 25-feat contract)   [4]
#     -> RuleEngine.evaluate           _rule_gate -> core.rule_engine (pass-through default) [6]
#     -> HybridModel.score (advisory)  _hybrid_rerank -> agent.hybrid_model (OFF by default) [5]
#     -> select (greedy budget commit) inline; emits (moves, intended_targets)
#     -> ActionEmitter.emit            _emit_gate -> core.action_emitter                     [7]
#     -> ActionSanitizer.sanitize      core.action_sanitizer (sun/OOB always; wrong-first-   [7]
#                                        hit opt-in via intended targets)
#     -> Kaggle action list [[src, angle, ships], ...]
#
# Layers [5]/[6] are advisory and OFF by default so the live agent is byte-identical to v3.2
# Forecast (golden-verified). `get_default_policy().act(obs)` is the single entrypoint main.py calls.
class DefaultPolicy:
    """Facade over the layered decision flow. Behavior == the v3.2 Forecast agent (preserved)."""

    def act(self, obs):
        return agent(obs)


_DEFAULT_POLICY = None


def get_default_policy():
    global _DEFAULT_POLICY
    if _DEFAULT_POLICY is None:
        _DEFAULT_POLICY = DefaultPolicy()
    return _DEFAULT_POLICY
