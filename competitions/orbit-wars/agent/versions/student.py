"""T12 — distilled student agent (behavior-cloned from kuni05).

Scores every (my planet, other planet) pair with a tiny MLP (trained by
arena/distill_train.py; features must match arena/distill_prep.py:FEATS) and
launches `frac * src.ships` at the intercept angle for pairs above threshold.

Weights: OW_STUDENT_W env or ~/work/distill_student.npz (snorlax default).
Arena-only for now — deployment would inline weights + intercept math into a
single file. Knobs: OW_STUDENT_TH (launch prob threshold), OW_STUDENT_MAXMV.
"""

import math
import os as _os
import sys as _sys

import numpy as _np

try:
    _HERE = _os.path.dirname(_os.path.abspath(__file__))
except NameError:  # pragma: no cover
    _HERE = _os.getcwd()
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)
from forecast import _path_blocked, _solve_intercept  # noqa: E402
from forecast_sim import fleet_speed as _fspeed  # noqa: E402
from forecast_sim import project as _project  # noqa: E402

PROJ_H = 18  # must match arena/distill_prep.py

try:
    from kaggle_environments.envs.orbit_wars.orbit_wars import Planet
except Exception:  # pragma: no cover
    from collections import namedtuple

    Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])

_W_PATH = _os.environ.get("OW_STUDENT_W", _os.path.expanduser("~/work/distill_student.npz"))
_W = _np.load(_W_PATH)
THRESH = float(_os.environ.get("OW_STUDENT_TH", 0.5))
MAX_MOVES = int(_os.environ.get("OW_STUDENT_MAXMV", 3))


def _forward(x):
    """x: [n, 16] raw features -> (launch_prob[n], frac[n])."""
    z = (x - _W["mean"]) / _W["std"]
    h = _np.maximum(0.0, z @ _W["w0"].T + _W["b0"])
    h = _np.maximum(0.0, h @ _W["w1"].T + _W["b1"])
    logit = h @ _W["wl"].T + _W["bl"]
    frac = 1.0 / (1.0 + _np.exp(-(h @ _W["wf"].T + _W["bf"])))
    prob = 1.0 / (1.0 + _np.exp(-logit))
    return prob[:, 0], frac[:, 0]


def _inbound(tgt, fleets, player):
    mine = enemy = 0.0
    for f in fleets:
        hx, hy = math.cos(f[4]), math.sin(f[4])
        rx, ry = tgt.x - f[2], tgt.y - f[3]
        if rx * hx + ry * hy <= 0:
            continue
        if abs(rx * (-hy) + ry * hx) < tgt.radius + 2.0:
            if f[1] == player:
                mine += f[6]
            else:
                enemy += f[6]
    return mine, enemy


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
    init_by_id = {p[0]: p for p in (obs.get("initial_planets", []) or [])}
    comet_ids = set(obs.get("comet_planet_ids", []) or [])
    step = int(obs.get("step", 0) or 0)

    planets = [Planet(*p) for p in raw_planets]
    mine = [p for p in planets if p.owner == player]
    if not mine:
        return []
    my_tot = sum(p.ships for p in mine) or 1.0
    opp_tot = sum(p.ships for p in planets if p.owner not in (-1, player)) or 1.0
    n_my = len(mine)
    n_opp = sum(1 for p in planets if p.owner not in (-1, player))
    step_frac = step / 500.0

    traj, sched = _project(
        raw_planets,
        raw_fleets,
        ang_vel,
        {p[0]: p for p in (obs.get("initial_planets", []) or [])},
        step,
        PROJ_H,
        comet_ids=comet_ids,
    )

    feats, pairs = [], []
    for src in mine:
        if src.ships < 1:
            continue
        for tgt in planets:
            if tgt.id == src.id:
                continue
            mi, ei = _inbound(tgt, raw_fleets, player)
            d = math.hypot(src.x - tgt.x, src.y - tgt.y)
            eta = d / _fspeed(max(1, int(src.ships // 2) or 1))
            k = max(1, min(PROJ_H, int(math.ceil(eta))))
            tt = traj.get(tgt.id)
            if tt is not None:
                def_eta = tt["ships"][k]
                o_eta = tt["owner"][k]
                flips = 1.0 if any(tt["owner"][i] != tgt.owner for i in range(1, PROJ_H + 1)) else 0.0
            else:
                def_eta, o_eta, flips = tgt.ships, tgt.owner, 0.0
            fr_arr = sum(s for _k, o, s in sched.get(tgt.id, []) if o == player)
            en_arr = sum(s for _k, o, s in sched.get(tgt.id, []) if o not in (player, -1))
            feats.append(
                [
                    src.ships,
                    src.production,
                    1.0 if tgt.owner == player else 0.0,
                    1.0 if tgt.owner not in (-1, player) else 0.0,
                    1.0 if tgt.owner == -1 else 0.0,
                    tgt.ships,
                    tgt.production,
                    tgt.radius,
                    d,
                    eta,
                    mi,
                    ei,
                    step_frac,
                    min(10.0, my_tot / opp_tot),
                    n_my,
                    n_opp,
                    def_eta,
                    1.0 if o_eta == player else 0.0,
                    1.0 if o_eta not in (-1, player) else 0.0,
                    flips,
                    fr_arr,
                    en_arr,
                ]
            )
            pairs.append((src, tgt))
    if not feats:
        return []
    prob, frac = _forward(_np.asarray(feats, dtype=_np.float32))

    order = _np.argsort(-prob)
    moves = []
    spent = {}
    for i in order[: MAX_MOVES * 4]:
        if len(moves) >= MAX_MOVES or prob[i] < THRESH:
            break
        src, tgt = pairs[i]
        avail = src.ships - spent.get(src.id, 0)
        ships = int(round(float(frac[i]) * src.ships))
        if ships < 1 or ships > avail:
            continue
        sol = _solve_intercept(src.x, src.y, tgt.id, ships, step, init_by_id, ang_vel)
        if sol is None:
            continue
        angle, t_ticks, pos = sol
        if step + t_ticks > 498:
            continue
        if _path_blocked(src.x, src.y, pos[0], pos[1], src.id, tgt.id, planets, comet_ids):
            continue
        moves.append([src.id, angle, ships])
        spent[src.id] = spent.get(src.id, 0) + ships
    return moves
