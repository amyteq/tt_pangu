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

    # Defensive reserve per owned planet (don't empty a planet under attack).
    reserve = {}
    for mp in my_planets:
        reserve[mp.id] = _incoming_threat(mp, fleets, player)

    # Targets: anything we don't own and isn't a comet (comets handled later versions).
    targets = [p for p in planets if p.owner != player and p.id not in comet_ids]

    candidates = []
    for mp in my_planets:
        avail = mp.ships - reserve.get(mp.id, 0)
        if avail <= 0:
            continue
        for tgt in targets:
            # Estimate required force, iterating because ships affect travel time.
            ships_guess = max(1, tgt.ships + 1)
            sol = None
            needed = ships_guess
            for _ in range(3):
                sol = _solve_intercept(mp.x, mp.y, tgt.id, ships_guess, step, init_by_id, ang_vel)
                if sol is None:
                    break
                _, t_ticks, _ = sol
                if tgt.owner == -1:  # neutral: static garrison
                    needed = tgt.ships + 1
                else:  # enemy: grows by production while in flight
                    needed = tgt.ships + tgt.production * t_ticks + 1 + ENEMY_BUFFER
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
            if _path_blocked(mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids):
                continue
            value = tgt.production / (needed * (1.0 + TIME_DISCOUNT * t_ticks))
            candidates.append((value, mp.id, tgt.id, angle, needed))

    candidates.sort(reverse=True, key=lambda c: c[0])

    remaining = {mp.id: mp.ships - reserve.get(mp.id, 0) for mp in my_planets}
    committed = set()
    moves = []
    for _value, src_id, tgt_id, angle, needed in candidates:
        if tgt_id in committed:
            continue
        if remaining.get(src_id, 0) >= needed:
            moves.append([src_id, angle, int(needed)])
            remaining[src_id] -= needed
            committed.add(tgt_id)
    return moves
