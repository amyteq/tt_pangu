"""
Orbit Wars agent — v3 "Forecast" (forward-sim differential planner).

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

# === inlined forward simulator (forecast_sim.py; bit-exact vs engine) ===
BOARD = 100.0
CENTER = 50.0
SUN_R = 10.0
ROT_LIMIT = 50.0
MAX_SPEED = 6.0


def fleet_speed(ships):
    if ships <= 1:
        return 1.0
    return min(MAX_SPEED, 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000.0)) ** 1.5)


def _seg_point_dist(px, py, ax, ay, bx, by):
    l2 = (ax - bx) ** 2 + (ay - by) ** 2
    if l2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))


def _swept_hit(A, B, P0, P1, r):
    """True iff a fleet moving A->B and a body moving P0->P1 come within r (engine's
    swept_pair_hit: relative motion is linear over the tick)."""
    d0x, d0y = A[0] - P0[0], A[1] - P0[1]
    dvx = (B[0] - A[0]) - (P1[0] - P0[0])
    dvy = (B[1] - A[1]) - (P1[1] - P0[1])
    a = dvx * dvx + dvy * dvy
    b = 2.0 * (d0x * dvx + d0y * dvy)
    c = d0x * d0x + d0y * d0y - r * r
    if a < 1e-12:
        return c <= 0.0
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return False
    sq = math.sqrt(disc)
    return (-b + sq) / (2.0 * a) >= 0.0 and (-b - sq) / (2.0 * a) <= 1.0


def _resolve_combat(garrison_owner, garrison_ships, arrivals):
    """Engine combat at one planet. `arrivals` = list of (owner, ships).
    Returns (new_owner, new_ships). Mirrors orbit_wars.interpreter step 5."""
    by_owner = {}
    for o, s in arrivals:
        by_owner[o] = by_owner.get(o, 0.0) + s
    if not by_owner:
        return garrison_owner, garrison_ships
    ranked = sorted(by_owner.items(), key=lambda kv: kv[1], reverse=True)
    top_owner, top_ships = ranked[0]
    if len(ranked) > 1:
        second = ranked[1][1]
        surv = 0.0 if top_ships == second else (top_ships - second)
        surv_owner = top_owner if surv > 0 else -1
    else:
        surv_owner, surv = top_owner, top_ships
    if surv <= 0:
        return garrison_owner, garrison_ships
    if garrison_owner == surv_owner:
        return garrison_owner, garrison_ships + surv
    ships = garrison_ships - surv
    if ships < 0:
        return surv_owner, abs(ships)
    return garrison_owner, ships


def _planet_pos(ix, iy, radius, ang_vel, step):
    """Engine rotation: orbiting (orbital_r + radius < 50) rotate; else static."""
    dx, dy = ix - CENTER, iy - CENTER
    orb = math.hypot(dx, dy)
    if orb + radius < ROT_LIMIT:
        a = math.atan2(dy, dx) + ang_vel * step
        return CENTER + orb * math.cos(a), CENTER + orb * math.sin(a)
    return ix, iy


def replay_planet(owner0, ships0, prod, arrivals, H):
    """Single-planet trajectory given its per-turn arrival schedule.

    `arrivals` = list of (k, owner, ships). Mirrors project()'s per-turn order for one
    planet: production (if owned) then combat. Returns (owner_list[H+1], ships_list[H+1]).
    Used to score a candidate by recomputing only the planets a launch touches.
    """
    by_k = {}
    for k, o, s in arrivals:
        by_k.setdefault(k, []).append((o, s))
    owner, ships = owner0, float(ships0)
    o_out, s_out = [owner], [ships]
    for k in range(1, H + 1):
        if owner != -1:
            ships += prod
        if k in by_k:
            owner, ships = _resolve_combat(owner, ships, by_k[k])
        o_out.append(owner)
        s_out.append(ships)
    return o_out, s_out


def project(planets, fleets, ang_vel, init_by_id, step0, H, comet_ids=()):
    """Do-nothing projection. Returns (traj, arrivals).

    traj: pid -> {'owner':[H+1], 'ships':[H+1]}.
    arrivals: pid -> list of (k, owner, ships) — fleets that hit it at turn k (the
    combat schedule), so a candidate can be scored by recomputing only touched planets.

    planets/fleets are tuples (id,owner,x,y,radius,ships,prod) / (id,owner,x,y,angle,from,ships).
    Comets are dropped (their path-based motion isn't modeled here).
    """
    comet_ids = set(comet_ids)
    pl = {
        p[0]: {
            "owner": p[1],
            "x": p[2],
            "y": p[3],
            "r": p[4],
            "ships": float(p[5]),
            "prod": p[6],
        }
        for p in planets
        if p[0] not in comet_ids
    }
    init = {pid: (init_by_id[pid][2], init_by_id[pid][3]) for pid in pl if pid in init_by_id}
    fl = [{"owner": f[1], "x": f[2], "y": f[3], "ang": f[4], "ships": float(f[6])} for f in fleets if f[6] > 0]
    traj = {pid: {"owner": [pl[pid]["owner"]], "ships": [pl[pid]["ships"]]} for pid in pl}
    arrivals = {pid: [] for pid in pl}

    for k in range(1, H + 1):
        step = step0 + k
        # 1. production
        for pid, p in pl.items():
            if p["owner"] != -1:
                p["ships"] += p["prod"]
        # planet positions this tick (old=step-1, new=step)
        old_pos, new_pos = {}, {}
        for pid, p in pl.items():
            ix, iy = init.get(pid, (p["x"], p["y"]))
            old_pos[pid] = _planet_pos(ix, iy, p["r"], ang_vel, step - 1)
            new_pos[pid] = _planet_pos(ix, iy, p["r"], ang_vel, step)
        # 2. fleet movement + swept collision; queue combats
        combat = {pid: [] for pid in pl}
        alive_fl = []
        for f in fl:
            spd = fleet_speed(f["ships"])
            A = (f["x"], f["y"])
            B = (f["x"] + math.cos(f["ang"]) * spd, f["y"] + math.sin(f["ang"]) * spd)
            hit = None
            for pid, p in pl.items():
                if _swept_hit(A, B, old_pos[pid], new_pos[pid], p["r"]):
                    hit = pid
                    break
            if hit is not None:
                combat[hit].append((f["owner"], f["ships"]))
                continue
            if not (0 <= B[0] <= BOARD and 0 <= B[1] <= BOARD):
                continue  # out of bounds -> gone
            if _seg_point_dist(CENTER, CENTER, A[0], A[1], B[0], B[1]) < SUN_R:
                continue  # hit sun -> gone
            f["x"], f["y"] = B
            alive_fl.append(f)
        fl = alive_fl
        # 3. rotation (apply new positions)
        for pid, p in pl.items():
            p["x"], p["y"] = new_pos[pid]
        # 4. combat
        for pid, arr in combat.items():
            if arr:
                pl[pid]["owner"], pl[pid]["ships"] = _resolve_combat(pl[pid]["owner"], pl[pid]["ships"], arr)
                for o, s in arr:
                    arrivals[pid].append((k, o, s))
        # record
        for pid, p in pl.items():
            traj[pid]["owner"].append(p["owner"])
            traj[pid]["ships"].append(p["ships"])
    return traj, arrivals


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


# === aliases used by the planner ===
_project = project
_replay = replay_planet
_adv = signed_adv

PROJ_H = 18  # forward-simulation horizon (matches kuni05's 2p horizon)

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
FRONTIER_FLOOR = float(_os.environ.get("OW_FRONTIER_FLOOR", 10))  # garrison kept on a planet near an enemy
FRONTIER_DIST = float(_os.environ.get("OW_FRONTIER_DIST", 28.0))  # enemy planet within this distance => frontier
GARRISON_PROD_MULT = float(_os.environ.get("OW_PROD_MULT", 0))  # extra standing garrison per unit production
INFLIGHT_CAP_FRAC = float(_os.environ.get("OW_INFLIGHT_CAP", 1.2))  # cap in-flight at this frac of on-planet ships
# Phase-scaled cap: looser early (win the land-grab) -> tighter late (hold and bank).
# Tuned via arena sweep vs the flat-1.2 v2 snapshot; mild scaling (2.0 -> 1.0) won,
# aggressive scaling (2.5-3.0 early / 0.6-0.8 late) lost. Linearly interpolated by step.
CAP_EARLY = float(_os.environ.get("OW_CAP_EARLY", 2.0))
CAP_LATE = float(_os.environ.get("OW_CAP_LATE", 1.0))
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

    candidates = []
    for mp in my_planets:
        avail = mp.ships - reserve.get(mp.id, 0)
        if avail <= 0:
            continue
        base_src_adv = _base_adv(mp.id)
        for tgt in targets:
            # Required force = the SIM's projected defender at the arrival turn (production
            # growth + in-flight reinforcements baked in), iterating because size->eta.
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
            if value <= 0:
                continue  # net-negative or pointless -> don't fire
            candidates.append((value, mp.id, tgt.id, angle, needed))

    candidates.sort(reverse=True, key=lambda c: c[0])

    remaining = {mp.id: mp.ships - reserve.get(mp.id, 0) for mp in my_planets}
    committed = set()
    moves = []
    for _value, src_id, tgt_id, angle, needed in candidates:
        if tgt_id in committed:
            continue
        if needed > launch_budget:  # respect the empire-wide in-flight cap
            continue
        if remaining.get(src_id, 0) >= needed:
            moves.append([src_id, angle, int(needed)])
            remaining[src_id] -= needed
            launch_budget -= needed
            committed.add(tgt_id)

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
    return moves
