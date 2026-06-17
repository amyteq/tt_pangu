"""Orbit Wars — verified building blocks for writing a new candidate agent.

Every function here is COPIED from the battle-tested agents (forecast.py /
main.py keep their own originals — this file is a teaching/reference library,
imported by nothing in production). All of them are verified against the real
engine: the forward simulator reproduces 3,672 planet-step states with ZERO
error, and the geometric helpers mirror the engine's own formulas.

How a turn works in the engine (kaggle_environments orbit_wars), in order:
  1. every owned planet gains `production` ships;
  2. every fleet moves `speed` along its fixed angle; a fleet is consumed by
     the FIRST body it touches (swept test, so fast fleets can't tunnel);
     leaving the board or touching the sun destroys it;
  3. orbiting planets rotate (angle += angular_velocity);
  4. combat resolves per planet over the fleets that arrived THIS turn.

A move is `[source_planet_id, angle_radians, num_ships]`. You cannot steer a
fleet after launch, and its speed is fixed by its size (see fleet_speed).

Quick-start for a new candidate:
    from utils import solve_intercept, path_blocked, project, replay_planet
    # 1. project() the do-nothing future once per turn;
    # 2. enumerate (my planet -> target) launches; solve_intercept gives the
    #    angle + arrival turn; path_blocked screens suicidal angles;
    # 3. score each launch by replaying only the touched planets
    #    (replay_planet) and comparing terminal value vs the baseline;
    # 4. fire the positive-value moves, best first.
"""

import math

# --- engine constants (mirrored from the engine source; do not tune) -------
BOARD = 100.0  # square board, (0,0)..(100,100)
CENTER = 50.0  # sun sits at the exact center
SUN_R = 10.0  # any fleet path touching this disc dies
ROT_LIMIT = 50.0  # planets with orbit_radius + planet_radius < 50 rotate
MAX_SPEED = 6.0  # speed cap (reached at fleet size 1000)
EPISODE_STEPS = 500  # game length; rewards settle on final ship counts


def fleet_speed(ships):
    """Engine speed law: bigger fleets fly FASTER (counter-intuitive but true).

    speed = 1 + 5 * (ln(n)/ln(1000))^1.5, capped at 6:
        1 ship -> 1.0   10 -> 2.0   100 -> 3.7   1000+ -> 6.0
    Consequence: splitting a force slows every part down and staggers the
    arrivals — for a single target, one big fleet strictly beats many small
    ones (verified in replay analysis #1 and by the engine formula itself).
    """
    if ships <= 1:
        return 1.0
    return min(MAX_SPEED, 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000.0)) ** 1.5)


def planet_pos(init_x, init_y, radius, ang_vel, step):
    """Exact position of a planet at absolute game step `step`.

    Planets are deterministic: orbiting ones (orbit radius + planet radius
    < 50) rotate uniformly around the sun from their INITIAL position; all
    others never move. Feed `initial_planets` coordinates, not current ones —
    that is what makes long-range prediction exact.
    """
    dx, dy = init_x - CENTER, init_y - CENTER
    orb = math.hypot(dx, dy)
    if orb + radius < ROT_LIMIT:
        a = math.atan2(dy, dx) + ang_vel * step
        return CENTER + orb * math.cos(a), CENTER + orb * math.sin(a)
    return init_x, init_y


def seg_point_dist(px, py, ax, ay, bx, by):
    """Minimum distance from point (px,py) to segment (ax,ay)-(bx,by).

    Used for cheap static screens, e.g. "does this straight path pass through
    the sun disc". For moving bodies use swept_hit instead.
    """
    l2 = (ax - bx) ** 2 + (ay - by) ** 2
    if l2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))


def swept_hit(A, B, P0, P1, r):
    """True iff a fleet moving A->B and a body moving P0->P1 come within r.

    This is the engine's own collision test (relative motion treated as linear
    within one tick) — using anything simpler makes fast fleets "tunnel"
    through planets in your model while dying in the real game.
    """
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
    """Engine combat at one planet for one turn. arrivals = [(owner, ships)].

    Rules (mirrors the interpreter exactly):
      * same-owner arrivals STACK (this is why co-arrival timing matters);
      * the largest stack survives with (largest - second largest) ships —
        a tie kills both;
      * the survivor then fights the garrison: if it has MORE ships than the
        garrison, it captures with the difference; otherwise the garrison
        just loses that many ships. Equal counts leave a 0-ship garrison to
        the defender.
    Returns (new_owner, new_ships).
    """
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
    """Aim at where the target WILL be, not where it is.

    Fixed-point iteration: guess flight time T from current distance, predict
    the target's position at step+T, re-measure, repeat until T converges
    (a few rounds suffice — orbits are slow relative to fleets). Returns
    (angle, T_ticks, (tx, ty)) or None. Without this, shots at orbiting
    planets simply miss and the fleet flies on to its death.

    init_by_id: {planet_id: initial_planet_row} from obs["initial_planets"].
    """
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


def path_blocked(mx, my, tx, ty, mine_id, tgt_id, planets, comet_ids, clearance=1.0):
    """True if a straight launch path clips the sun or any OTHER planet.

    The engine consumes a fleet on the FIRST body it touches, so an angle that
    grazes a bystander planet donates your fleet to it. `planets` = current
    obs planet objects with .id/.x/.y/.radius (namedtuple or alike).
    Static screen (current positions); good enough because launches are
    re-planned every turn — for long flights pair it with swept_hit checks.
    """
    if seg_point_dist(CENTER, CENTER, mx, my, tx, ty) < SUN_R:
        return True
    for p in planets:
        if p.id == mine_id or p.id == tgt_id or p.id in comet_ids:
            continue
        if seg_point_dist(p.x, p.y, mx, my, tx, ty) < p.radius + clearance:
            return True
    return False


def replay_planet(owner0, ships0, prod, arrivals, H):
    """Fast single-planet what-if: evolve one planet H turns given a schedule.

    arrivals = [(turn_k, owner, ships)] — the combat events that will hit this
    planet. Returns (owner_list[H+1], ships_list[H+1]). This is the cheap core
    of move evaluation: to score a launch you only need to replay the SOURCE
    (debited now) and the TARGET (your stack added at its arrival turn) and
    compare terminal value against the do-nothing baseline from project().
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
            owner, ships = resolve_combat(owner, ships, by_k[k])
        o_out.append(owner)
        s_out.append(ships)
    return o_out, s_out


def project(planets, fleets, ang_vel, init_by_id, step0, H, comet_ids=()):
    """Bit-exact 'do-nothing' projection of the whole board H turns ahead.

    Replays the engine loop (production -> fleet moves + swept collisions ->
    rotation -> combat) for every existing fleet and planet, assuming nobody
    launches anything new. Verified 0-error vs the real engine over 3,672
    planet-steps. Returns:
      traj:     {pid: {"owner": [H+1], "ships": [H+1]}} — future garrison and
                ownership of every planet, turn by turn;
      arrivals: {pid: [(k, owner, ships)]} — the combat schedule, i.e. which
                fleets land where and when. Feed these into replay_planet to
                evaluate candidate moves without re-simulating the board.
    planets/fleets are the raw obs rows: (id,owner,x,y,radius,ships,prod) and
    (id,owner,x,y,angle,from_id,ships). Comets are excluded (path-based
    motion isn't modelled; treat them as unknowns).
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
        for pid, p in pl.items():  # 1. production
            if p["owner"] != -1:
                p["ships"] += p["prod"]
        old_pos, new_pos = {}, {}
        for pid, p in pl.items():
            ix, iy = init.get(pid, (p["x"], p["y"]))
            old_pos[pid] = planet_pos(ix, iy, p["r"], ang_vel, step - 1)
            new_pos[pid] = planet_pos(ix, iy, p["r"], ang_vel, step)
        combat = {pid: [] for pid in pl}
        alive_fl = []
        for f in fl:  # 2. fleet movement + swept collision
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
                continue  # out of bounds -> fleet lost
            if seg_point_dist(CENTER, CENTER, A[0], A[1], B[0], B[1]) < SUN_R:
                continue  # touched the sun -> fleet lost
            f["x"], f["y"] = B
            alive_fl.append(f)
        fl = alive_fl
        for pid, p in pl.items():  # 3. rotation
            p["x"], p["y"] = new_pos[pid]
        for pid, arr in combat.items():  # 4. combat
            if arr:
                pl[pid]["owner"], pl[pid]["ships"] = resolve_combat(pl[pid]["owner"], pl[pid]["ships"], arr)
                for o, s in arr:
                    arrivals[pid].append((k, o, s))
        for pid, p in pl.items():
            traj[pid]["owner"].append(p["owner"])
            traj[pid]["ships"].append(p["ships"])
    return traj, arrivals


def terminal_value(owner_list, ships_list, me, H):
    """Conservation-correct move score: signed ships at horizon H.

    +ships if we own the planet at turn H, -ships if an opponent does, 0 if
    neutral. Because ships in transit have landed by H, launching is not
    wrongly penalized, and production accrued by H rewards EARLIER captures
    (tempo). Sum this over the planets a move touches, subtract the same sum
    from the do-nothing baseline, and you have the move's differential value —
    the single largest win-rate jump in this project (v2.1 556 -> v3 686)
    came from exactly this scoring.

    Hard-won discipline to keep alongside it: gate every change on the public
    -agent suite (self-play win-rate does NOT predict the ladder), use >=150
    paired seeds per comparison, and treat <+7pt as undecidable.
    """
    o, s = owner_list[H], ships_list[H]
    return s if o == me else (-s if o != -1 else 0.0)
