"""
Orbit Wars agent — v1 "Intercept Economist".

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
import sys as _sys

# Make sibling forecast_sim importable however this file is loaded (in place, or
# exec'd by kaggle_environments with no __file__).
try:
    _HERE = _os.path.dirname(_os.path.abspath(__file__))
except NameError:
    _HERE = _os.getcwd()
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
from forecast_sim import project as _project, replay_planet as _replay

# T2-R2 BAKED (2026-06-12, issue #87): t14 config confirmed on two independent
# 300-game blocks (snorlax 13000+: 17.7%, local 15000+: 19.0% vs baseline ~12%;
# pooled +6.7pt, z~3.3). Defaults below = t14: H26/FF5/FD20/CE3.2/CL1.3.
PROJ_H = int(_os.environ.get("OW_PROJ_H", 26))  # forward-sim horizon; 18 too short for slow opening fleets
# Multi-source coordination (the strong-tier lever): pool ships from several friendly
# planets onto one target, sized to capture AND hold (vs single-source minimal captures
# that get retaken). Staggered waves grind the defender; total = needed * HOLD_MULT.
MULTISRC = int(_os.environ.get("OW_MULTISRC", 0))  # default OFF: tried, no gain vs strong tier
HOLD_MULT = float(_os.environ.get("OW_HOLD_MULT", 1.6))
# Opening expander: the differential value-gate is too conservative early (we fire 2-3x
# in the first 25 turns while strong agents grab 5 planets). In the opening, grab every
# reachable neutral with positive production-gain over a long opening horizon, firing
# aggressively (no value-gate, no in-flight cap) to win the land-grab.
OPENING = int(_os.environ.get("OW_OPENING", 0))  # default OFF: fired more but win-rate dropped
OPENING_TURNS = int(_os.environ.get("OW_OPENING_TURNS", 25))
OPENING_H = int(_os.environ.get("OW_OPENING_H", 50))
# T8 — true co-arrival strikes (issue #87). Unlike MULTISRC (same-turn salvo: fleets
# from different distances arrive on DIFFERENT turns and are defeated in detail), this
# aligns ARRIVAL turns: pick an arrival turn K, fire the sources whose min ETA equals K
# now, and RESERVE nearer sources (they re-derive their own fire turn on a later replan,
# when the in-flight wave shows up in the do-nothing projection's arrival schedule and
# their min ETA matches its arrival turn). The engine sums same-turn arrivals by owner,
# so an aligned wave fights as one stack. Targets only planets no single source can take.
COARRIVAL = int(_os.environ.get("OW_COARRIVAL", 0))
COARR_MAX_SRC = int(_os.environ.get("OW_COARR_MAX_SRC", 4))  # wave fragmentation cap
COARR_HOLD = float(_os.environ.get("OW_COARR_HOLD", 1.0))  # extra force mult to hold
# T11 — ledger-constrained availability (issue #87, ChatGPT §9-2 dynamic defense
# reserve). avail = min(current rule, ledger slack), where slack = min projected
# garrison over the do-nothing trajectory's HELD turns (kuni05's safe_drain bound).
# CONSTRAINT-ONLY: never frees more ships than the static rule (v3a failed by using
# the same bound to free MORE); a planet projected to flip has nothing to protect
# (the defense module handles it) -> no cap.
LEDGER = int(_os.environ.get("OW_LEDGER", 0))
# K±tol merging (T8 v2): a share whose exact-size ETA lands at K+1..K+tol joins the
# wave anyway (fires now, valued at its true arrival turn) instead of aborting the
# whole wave; shares slower than K+tol are dropped, not wave-fatal. tol=0 ~= v1.
COARR_TOL = int(_os.environ.get("OW_COARR_TOL", 1))
# Replay-derived (issue #87 analysis #1): the top player attacks rarely but with
# ~4x the loser's fleet size — overwhelming force is insurance, not waste. Scale
# offensive sizing beyond the minimal capture threshold (1.0 = old behaviour).
OVERKILL = float(_os.environ.get("OW_OVERKILL", 1.0))
# T14 - short-hop supply chain (replay analysis #1: 56% of the top player's
# launches are short reinforce hops feeding the front; heavy strikes EMERGE from
# concentration - the OVERKILL sizing multiplier tested monotonically negative).
# Unlike the rejected CONSOLIDATE (long-haul, aggressive), hops are capped at
# SUPPLY_DIST and chain planet-to-planet toward the front, small and continuous.
SUPPLY = int(_os.environ.get("OW_SUPPLY", 0))
SUPPLY_DIST = float(_os.environ.get("OW_SUPPLY_DIST", 25.0))  # max hop length
SUPPLY_MIN = float(_os.environ.get("OW_SUPPLY_MIN", 5))  # min surplus to stream
SUPPLY_MARGIN = float(_os.environ.get("OW_SUPPLY_MARGIN", 3.0))  # front-gain needed
# T13 - decisive-battle posture switching (replay analysis #1: the top player
# wins ONE big exchange ~t100-125 then snowballs; the loser bleeds out in small
# attacks). Module state persists within an episode (agents are loaded once and
# called per step), so we can react to the opponent's army being IN TRANSIT:
#   BRACE  - large enemy mass in flight -> hold offensive budget, raise reserves
#            (their wave must beat fortified garrisons; ours stays home);
#   PUNISH - the wave has landed (their sources are drained, their field army is
#            spent on our garrisons) -> temporarily loosen the budget and let the
#            value gate find the weakened planets.
POSTURE = int(_os.environ.get("OW_POSTURE", 0))
POSTURE_BRACE = float(_os.environ.get("OW_POSTURE_BRACE", 0.35))  # in-flight frac
POSTURE_BUDGET = float(_os.environ.get("OW_POSTURE_BUDGET", 0.3))  # brace budget x
POSTURE_RESERVE = float(_os.environ.get("OW_POSTURE_RESERVE", 1.5))  # brace floors x
PUNISH_TURNS = int(_os.environ.get("OW_PUNISH_TURNS", 6))
PUNISH_BUDGET = float(_os.environ.get("OW_PUNISH_BUDGET", 1.6))  # punish budget x

_T13 = {"ep_step": -1, "braced": False, "punish": 0}

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
REAR_FLOOR = float(_os.environ.get("OW_REAR_FLOOR", 0))  # garrison kept on a safe (rear) planet
FRONTIER_FLOOR = float(_os.environ.get("OW_FRONTIER_FLOOR", 5))  # garrison kept on a planet near an enemy
FRONTIER_DIST = float(_os.environ.get("OW_FRONTIER_DIST", 20.0))  # enemy planet within this distance => frontier
GARRISON_PROD_MULT = float(_os.environ.get("OW_PROD_MULT", 0))  # extra standing garrison per unit production
INFLIGHT_CAP_FRAC = float(_os.environ.get("OW_INFLIGHT_CAP", 1.2))  # cap in-flight at this frac of on-planet ships
# Phase-scaled cap: looser early (win the land-grab) -> tighter late (hold and bank).
# Tuned via arena sweep vs the flat-1.2 v2 snapshot; mild scaling (2.0 -> 1.0) won,
# aggressive scaling (2.5-3.0 early / 0.6-0.8 late) lost. Linearly interpolated by step.
CAP_EARLY = float(_os.environ.get("OW_CAP_EARLY", 3.2))
CAP_LATE = float(_os.environ.get("OW_CAP_LATE", 1.3))
# Consolidation: forward an idle rear planet's surplus to the friendly planet nearest the
# front (the getting-started tutorial's flaw #4). DEFAULT OFF — an arena sweep showed it
# never beats v2.1: harmful when aggressive (min=12 -> 30% vs v2.1), at best neutral when
# rare (min>=30 -> 40-40). Our aggression already uses rear ships efficiently; forwarding
# them wastes transit, starves the in-flight cap, and funnels the empire into fewer launch
# points. Code kept (env-gated) so the result stays reproducible via OW_CONSOLIDATE=1.
CONSOLIDATE = int(_os.environ.get("OW_CONSOLIDATE", 0))
CONSOLIDATE_MIN = float(_os.environ.get("OW_CONSOLIDATE_MIN", 12))  # min surplus to bother (tiny fleets crawl)
CONSOLIDATE_MARGIN = float(_os.environ.get("OW_CONSOLIDATE_MARGIN", 3.0))  # front-distance gain required


def _hypot(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def _fleet_speed(ships):
    if ships <= 1:
        return 1.0
    s = 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000.0)) ** 1.5
    return min(s, MAX_SPEED)


def _point_to_segment(px, py, ax, ay, bx, by):
    """Min distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    l2 = (ax - bx) ** 2 + (ay - by) ** 2
    if l2 == 0.0:
        return _hypot(px, py, ax, ay)
    t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2
    t = max(0.0, min(1.0, t))
    return _hypot(px, py, ax + t * (bx - ax), ay + t * (by - ay))


def _predict_pos(pid, future_step, init_by_id, ang_vel):
    """Exact predicted (x, y) of a planet at an absolute game step.

    Static planets never move (return initial == current position). Orbiting
    planets rotate at constant angular velocity about the center.
    """
    ip = init_by_id.get(pid)
    if ip is None:
        return None
    ix, iy, r_planet = ip[2], ip[3], ip[4]
    dx, dy = ix - CENTER, iy - CENTER
    orb = math.hypot(dx, dy)
    if orb + r_planet < ROTATION_RADIUS_LIMIT:
        a = math.atan2(dy, dx) + ang_vel * future_step
        return (CENTER + orb * math.cos(a), CENTER + orb * math.sin(a))
    return (ix, iy)


def _solve_intercept(mx, my, tgt_pid, ships, step, init_by_id, ang_vel):
    """Fixed-point intercept: returns (angle, T_ticks, (tx, ty)) or None."""
    speed = _fleet_speed(ships)
    cur = _predict_pos(tgt_pid, step, init_by_id, ang_vel)
    if cur is None:
        return None
    t = max(1.0, _hypot(mx, my, cur[0], cur[1]) / speed)
    pos = cur
    for _ in range(12):
        pos = _predict_pos(tgt_pid, step + t, init_by_id, ang_vel)
        d = _hypot(mx, my, pos[0], pos[1])
        nt = max(1.0, d / speed)
        if abs(nt - t) < 0.2:
            t = nt
            break
        t = nt
    t_ceil = max(1, int(math.ceil(t)))
    pos = _predict_pos(tgt_pid, step + t_ceil, init_by_id, ang_vel)
    angle = math.atan2(pos[1] - my, pos[0] - mx)
    return angle, t_ceil, pos


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


def agent(obs):
    try:
        return _agent(obs)
    except Exception:
        return []


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

    # Reserve = standing garrison floor + any extra for currently-inbound enemy fleets.
    # The floor is the v2 fix: it lets freshly captured planets accumulate production
    # instead of being immediately re-emptied, which breaks v1's capture-churn loop.
    reserve = {}
    for mp in my_planets:
        floor = _garrison_floor(mp, enemy_planets)
        threat = _incoming_threat(mp, fleets, player)
        reserve[mp.id] = max(floor, threat)

    # Global in-flight cap: don't pour the whole empire into simultaneous fleets.
    # Phase-scaled: interpolate from CAP_EARLY (step 0) to CAP_LATE (game end).
    cap_frac = CAP_EARLY + (CAP_LATE - CAP_EARLY) * min(1.0, step / EPISODE_STEPS)
    ships_on_planets = sum(mp.ships for mp in my_planets)
    ships_in_flight = sum(f.ships for f in fleets if f.owner == player)
    launch_budget = max(0.0, cap_frac * ships_on_planets - ships_in_flight)

    # T13 posture: react to the opponent's army being in transit (see knobs).
    if POSTURE:
        if step <= _T13["ep_step"]:  # new episode -> reset persistent state
            _T13["braced"] = False
            _T13["punish"] = 0
        _T13["ep_step"] = step
        enemy_onplanet = sum(p.ships for p in planets if p.owner not in (-1, player))
        enemy_inflight = sum(f.ships for f in fleets if f.owner != player)
        mass_frac = enemy_inflight / max(1.0, enemy_inflight + enemy_onplanet)
        if mass_frac > POSTURE_BRACE:
            launch_budget *= POSTURE_BUDGET
            for pid in reserve:
                reserve[pid] *= POSTURE_RESERVE
            _T13["braced"] = True
        else:
            if _T13["braced"] and mass_frac < POSTURE_BRACE * 0.5:
                _T13["punish"] = PUNISH_TURNS  # their wave just landed
            _T13["braced"] = False
            if _T13["punish"] > 0:
                launch_budget *= PUNISH_BUDGET
                _T13["punish"] -= 1

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
        return s if o == player else (-s if o != -1 else 0.0)

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
        for _g, src_id, tgt_id, angle, needed in op_cands:
            if tgt_id in taken or rem.get(src_id, 0) < needed:
                continue
            op_moves.append([src_id, angle, int(needed)])
            rem[src_id] -= needed
            taken.add(tgt_id)
        if op_moves:
            return op_moves

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
                        needed = int(math.ceil((defender + buf) * OVERKILL))
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
            if value <= 0:
                continue  # net-negative or pointless -> don't fire
            candidates.append((value, mp.id, tgt.id, angle, needed))

    candidates.sort(reverse=True, key=lambda c: c[0])
    remaining = {mp.id: _avail(mp) for mp in my_planets}
    committed = set()
    moves = []
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
            remaining[src.id] = 0
    # T14 - short-hop supply chain: idle rear surplus streams one hop toward the
    # front each turn (nearest friendly planet meaningfully closer to the front,
    # within SUPPLY_DIST). Front planets accumulate mass; big strikes follow.
    if SUPPLY and targets:
        attacked = {m[0] for m in moves}
        fd = {p.id: _front_dist(p, targets) for p in my_planets}
        for src in my_planets:
            if src.id in attacked:
                continue
            surplus = remaining.get(src.id, 0)
            if surplus < SUPPLY_MIN:
                continue
            best, best_d = None, None
            for q in my_planets:
                if q.id == src.id:
                    continue
                d = _hypot(src.x, src.y, q.x, q.y)
                if d > SUPPLY_DIST or fd[q.id] >= fd[src.id] - SUPPLY_MARGIN:
                    continue
                if best is None or d < best_d:
                    best, best_d = q, d
            if best is None:
                continue
            sol = _solve_intercept(src.x, src.y, best.id, surplus, step, init_by_id, ang_vel)
            if sol is None:
                continue
            ang, _t, pos = sol
            if _path_blocked(src.x, src.y, pos[0], pos[1], src.id, best.id, planets, comet_ids):
                continue
            moves.append([src.id, ang, int(surplus)])
            remaining[src.id] = 0

    return moves
