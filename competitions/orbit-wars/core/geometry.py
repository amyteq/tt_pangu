"""Engine-verified geometry/physics primitives (stdlib only).

Copied verbatim from the engine-verified reference `agent/utils.py` (0 error vs the
real engine over 3,672 planet-step states; mirrors the orbit_wars interpreter). This
is the single home for collision/position math — `core/` modules and the FlightOracle
build on these; do NOT re-derive geometry elsewhere.

Engine turn order: (1) owned planets +production; (2) fleets move `speed` along a fixed
angle, consumed by the FIRST swept body, dying on sun / out-of-bounds; (3) orbiting
planets rotate; (4) combat per planet over same-tick arrivals.
"""

import math

BOARD = 100.0  # square board (0,0)..(100,100)
CENTER = 50.0  # sun at exact center
SUN_R = 10.0  # a fleet path within this disc dies
ROT_LIMIT = 50.0  # planets with orbital_radius + radius < 50 rotate
MAX_SPEED = 6.0  # speed cap (reached near fleet size 1000)
EPISODE_STEPS = 500


def fleet_speed(ships):
    """speed = 1 + 5*(ln n/ln 1000)^1.5, capped at 6 (bigger fleets fly FASTER)."""
    if ships <= 1:
        return 1.0
    return min(MAX_SPEED, 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000.0)) ** 1.5)


def planet_pos(init_x, init_y, radius, ang_vel, step):
    """Exact planet position as OBSERVED at absolute game `step` (orbiting iff orbit_r+radius<50).

    Engine phase (orbit_wars.py interpreter): the observation at step t shows orbiting planets at
    rotate(init_angle, ang_vel*(t-1)) — verified vs replay 80276901 and the engine source
    (`game_step = spawn_step - 1 + k`). The earlier `ang_vel*step` was one tick AHEAD (it returned
    obs(step+1)), which mis-aimed intercepts by ~orbit_r*ang_vel and made FlightOracle phantom-hit
    planets (masking real sun/OOB danger → fleets flew into the sun). The (step-1) below is that fix.
    """
    dx, dy = init_x - CENTER, init_y - CENTER
    orb = math.hypot(dx, dy)
    if orb + radius < ROT_LIMIT:
        # obs(0)==obs(1)==init, then obs(t)=rotate(init, ang_vel*(t-1)) — verified on replay 80276901
        a = math.atan2(dy, dx) + ang_vel * max(0, step - 1)
        return CENTER + orb * math.cos(a), CENTER + orb * math.sin(a)
    return init_x, init_y


def orbital_radius(init_x, init_y):
    return math.hypot(init_x - CENTER, init_y - CENTER)


def is_orbiting(init_x, init_y, radius):
    return orbital_radius(init_x, init_y) + radius < ROT_LIMIT


def seg_point_dist(px, py, ax, ay, bx, by):
    """Min distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    l2 = (ax - bx) ** 2 + (ay - by) ** 2
    if l2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))


def swept_hit(A, B, P0, P1, r):
    """True iff a fleet moving A->B and a body moving P0->P1 come within r (engine's
    own swept-pair test — relative motion linear within the tick)."""
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


def resolve_combat(garrison_owner, garrison_ships, arrivals):
    """Engine combat at one planet for one turn. arrivals=[(owner,ships)].
    Same-owner stacks; largest-minus-second survives (tie annihilates); survivor vs
    garrison. Returns (new_owner, new_ships)."""
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


def solve_intercept(mx, my, tgt_pid, ships, step, init_by_id, ang_vel):
    """Aim at where the target WILL be: fixed-point on flight time T.
    Returns (angle, T_ticks, (tx,ty)) or None. init_by_id: {pid: initial_planet_row}."""
    speed = fleet_speed(ships)
    ip = init_by_id.get(tgt_pid)
    if ip is None:
        return None

    def _pos(t):
        return planet_pos(ip[2], ip[3], ip[4], ang_vel, t)

    pos = _pos(step)
    t = max(1.0, math.hypot(mx - pos[0], my - pos[1]) / speed)
    for _ in range(12):
        pos = _pos(step + t)
        nt = max(1.0, math.hypot(mx - pos[0], my - pos[1]) / speed)
        if abs(nt - t) < 0.2:
            t = nt
            break
        t = nt
    t_ceil = max(1, int(math.ceil(t)))
    pos = _pos(step + t_ceil)
    angle = math.atan2(pos[1] - my, pos[0] - mx)
    return angle, t_ceil, pos


def replay_planet(owner0, ships0, prod, arrivals, H):
    """Single-planet trajectory: arrivals=[(k,owner,ships)]. Returns (owner[H+1], ships[H+1])."""
    by_k = {}
    for k, o, s in arrivals:
        by_k.setdefault(k, []).append((o, s))
    owner, ships = owner0, float(ships0)
    o_out, s_out = [owner], [ships]
    for k in range(1, H + 1):
        if owner != -1:
            ships += prod
        if k in by_k:
            owner, ships = resolve_combat(owner, ships, by_k[k])
        o_out.append(owner)
        s_out.append(ships)
    return o_out, s_out


def project(planets, fleets, ang_vel, init_by_id, step0, H, comet_ids=()):
    """Bit-exact do-nothing projection of the whole board H turns ahead.
    Returns (traj{pid:{owner[H+1],ships[H+1]}}, arrivals{pid:[(k,owner,ships)]}).
    planets/fleets are raw obs rows (id,owner,x,y,radius,ships,prod)/(id,owner,x,y,angle,from,ships).
    Comets excluded (path motion unmodelled)."""
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
        for pid, p in pl.items():
            if p["owner"] != -1:
                p["ships"] += p["prod"]
        old_pos, new_pos = {}, {}
        for pid, p in pl.items():
            ix, iy = init.get(pid, (p["x"], p["y"]))
            old_pos[pid] = planet_pos(ix, iy, p["r"], ang_vel, step - 1)
            new_pos[pid] = planet_pos(ix, iy, p["r"], ang_vel, step)
        combat = {pid: [] for pid in pl}
        alive_fl = []
        for f in fl:
            spd = fleet_speed(f["ships"])
            A = (f["x"], f["y"])
            B = (f["x"] + math.cos(f["ang"]) * spd, f["y"] + math.sin(f["ang"]) * spd)
            hit = None
            for pid, p in pl.items():
                if swept_hit(A, B, old_pos[pid], new_pos[pid], p["r"]):
                    hit = pid
                    break
            if hit is not None:
                combat[hit].append((f["owner"], f["ships"]))
                continue
            if not (0 <= B[0] <= BOARD and 0 <= B[1] <= BOARD):
                continue
            if seg_point_dist(CENTER, CENTER, A[0], A[1], B[0], B[1]) < SUN_R:
                continue
            f["x"], f["y"] = B
            alive_fl.append(f)
        fl = alive_fl
        for pid, p in pl.items():
            p["x"], p["y"] = new_pos[pid]
        for pid, arr in combat.items():
            if arr:
                pl[pid]["owner"], pl[pid]["ships"] = resolve_combat(pl[pid]["owner"], pl[pid]["ships"], arr)
                for o, s in arr:
                    arrivals[pid].append((k, o, s))
        for pid, p in pl.items():
            traj[pid]["owner"].append(p["owner"])
            traj[pid]["ships"].append(p["ships"])
    return traj, arrivals
