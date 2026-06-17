"""Forecast planner — forward simulator (Track 1, our own clean-room build).

A do-nothing projection of the board over a horizon H, using the EXACT engine rules
from kaggle_environments orbit_wars (production -> fleet movement+swept collision ->
rotation -> combat). Produces per-planet (owner, ships) trajectories used to:
  - size launches via safe_drain (max sheddable while a source stays held),
  - gate captures via per-arrival-turn defender floors,
  - score candidates by simulated differential net-ship delta.

Pure Python, stdlib only (keeps the eventual submission single-file). No torch.
"""

import math

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
        p[0]: {"owner": p[1], "x": p[2], "y": p[3], "r": p[4], "ships": float(p[5]), "prod": p[6]}
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


# --------------------------------------------------------------------------- #
# self-test: combat rule + a do-nothing projection sanity check
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # combat unit checks (engine rule: top1-top2 survives; tie annihilates;
    # surplus vs garrison flips if it exceeds it).
    assert _resolve_combat(-1, 10, [(0, 15)]) == (0, 5), "neutral capture"
    assert _resolve_combat(-1, 10, [(0, 10)]) == (-1, 0), "exact = no flip"
    assert _resolve_combat(0, 10, [(0, 5)]) == (0, 15), "reinforce own"
    assert _resolve_combat(1, 10, [(0, 8), (2, 3)]) == (1, 5), "8-3=5 vs garr10 -> hold 5"
    assert _resolve_combat(1, 10, [(0, 25), (2, 3)]) == (0, 12), "22 vs 10 -> flip, 12"
    assert _resolve_combat(1, 10, [(0, 7), (2, 7)]) == (1, 10), "tie annihilates"
    print("combat unit checks PASS")

    # do-nothing sanity: owned planet grows by prod, neutral static, no fleets.
    planets = [(0, 0, 70.0, 50.0, 1.0, 10, 3), (1, -1, 30.0, 50.0, 1.0, 20, 2)]
    init_by_id = {0: planets[0], 1: planets[1]}
    tr, arr = project(planets, [], 0.0, init_by_id, 0, 5)
    assert tr[0]["ships"] == [10, 13, 16, 19, 22, 25], tr[0]["ships"]
    assert tr[1]["ships"] == [20, 20, 20, 20, 20, 20], tr[1]["ships"]
    assert all(o == 0 for o in tr[0]["owner"]) and all(o == -1 for o in tr[1]["owner"])
    print("do-nothing projection sanity PASS")

    # replay_planet must reproduce project()'s per-planet trajectory exactly (so the
    # touched-planet differential scorer is consistent with the full sim).
    planets2 = [(0, 0, 70.0, 50.0, 1.0, 10, 3), (1, -1, 50.0, 20.0, 1.0, 8, 2)]
    init2 = {p[0]: p for p in planets2}
    # a fleet from planet 0 aimed straight at planet 1
    import math as _m

    ang = _m.atan2(20.0 - 50.0, 50.0 - 70.0)
    fleets2 = [(0, 0, 70.0 + _m.cos(ang) * 1.1, 50.0 + _m.sin(ang) * 1.1, ang, 0, 30)]
    tr2, arr2 = project(planets2, fleets2, 0.0, init2, 0, 12)
    for pid in (0, 1):
        ro, rs = replay_planet(planets2[pid][1], planets2[pid][5], planets2[pid][6], arr2[pid], 12)
        assert ro == tr2[pid]["owner"] and rs == tr2[pid]["ships"], (pid, ro, tr2[pid]["owner"])
    print("replay_planet consistency PASS")
