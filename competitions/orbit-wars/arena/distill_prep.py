"""T12 phase B prep — decode teacher moves and build the BC pair dataset.

Each raw teacher move is [src_id, angle, ships]; the intended TARGET is implicit
in the angle. We recover it by simulating the fleet's flight with the bit-exact
engine dynamics (size-dependent speed, straight line, moving planets, swept
collision) until it hits a planet. Moves that hit nothing within FLIGHT_H ticks
(or die to sun/bounds) are dropped (~rare; kuni05 doesn't waste fleets).

Output: one .npz with
    X        float32 [N, F]   per-(src, tgt) features at decision time
    y_launch float32 [N]      1 if the teacher launched src->tgt this turn
    y_frac   float32 [N]      ships / src.ships when launched, else 0
    game     int32   [N]      game index (for grouped train/val split)
    won      float32 [N]      1 if the teacher won that game

Usage:
    python arena/distill_prep.py --data ~/work/distill_data \
        --out ~/work/distill_pairs.npz --procs 23
"""

import argparse
import glob
import gzip
import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
sys.path.insert(0, V)
from forecast_sim import (  # noqa: E402
    _planet_pos,
    _swept_hit,
    fleet_speed,
    project,
)

BOARD = 100.0
CENTER = 50.0
SUN_R = 10.0
FLIGHT_H = 80  # decode horizon (slow 1-ship fleets cross ~100 units in ~100 ticks)
PROJ_H = 18  # forward-sim horizon for the v1 features
FEATS = [
    "src_ships",
    "src_prod",
    "tgt_mine",
    "tgt_enemy",
    "tgt_neutral",
    "tgt_ships",
    "tgt_prod",
    "tgt_radius",
    "dist",
    "eta",
    "my_inbound",
    "enemy_inbound",
    "step_frac",
    "ship_ratio",
    "my_planets",
    "opp_planets",
    # v1: forward-sim features (T12 v1 — what the teacher actually reasons about)
    "def_at_eta",  # projected garrison at our arrival turn
    "mine_at_eta",  # we already own it at arrival (projection)
    "enemy_at_eta",  # enemy owns it at arrival
    "tgt_flips",  # target changes owner within PROJ_H in the do-nothing run
    "fr_arr",  # friendly ships already scheduled to arrive (in-flight)
    "en_arr",  # enemy ships already scheduled to arrive
]


def _decode_target(move, obs):
    """Simulate the launched fleet; return (tgt_id, eta) or None."""
    src_id, ang, ships = int(move[0]), float(move[1]), int(move[2])
    pl = {p[0]: p for p in obs["planets"]}
    if src_id not in pl:
        return None
    init = {p[0]: p for p in obs["initial_planets"]}
    ang_vel = obs["angular_velocity"]
    step0 = obs["step"]
    sp = fleet_speed(ships)
    dx, dy = math.cos(ang) * sp, math.sin(ang) * sp
    x, y = pl[src_id][2], pl[src_id][3]
    for k in range(1, FLIGHT_H + 1):
        step = step0 + k
        nx, ny = x + dx, y + dy
        for pid, p in pl.items():
            if pid == src_id and k <= 2:
                continue  # freshly launched fleet clears its own source first
            ip = init.get(pid, p)
            P0 = _planet_pos(ip[2], ip[3], p[4], ang_vel, step - 1)
            P1 = _planet_pos(ip[2], ip[3], p[4], ang_vel, step)
            if _swept_hit((x, y), (nx, ny), P0, P1, p[4]):
                return pid, k
        if not (0 <= nx <= BOARD and 0 <= ny <= BOARD):
            return None
        # sun check (segment vs static disc)
        t = max(0.0, min(1.0, ((CENTER - x) * dx + (CENTER - y) * dy) / (sp * sp)))
        if math.hypot(CENTER - (x + t * dx), CENTER - (y + t * dy)) < SUN_R:
            return None
        x, y = nx, ny
    return None


def _inbound(tgt, fleets, player):
    """(my, enemy) ship totals on fleets whose heading passes near tgt."""
    mine = enemy = 0.0
    tx, ty, tr = tgt[2], tgt[3], tgt[4]
    for f in fleets:
        hx, hy = math.cos(f[4]), math.sin(f[4])
        rx, ry = tx - f[2], ty - f[3]
        if rx * hx + ry * hy <= 0:
            continue
        if abs(rx * (-hy) + ry * hx) < tr + 2.0:
            if f[1] == player:
                mine += f[6]
            else:
                enemy += f[6]
    return mine, enemy


def _eta(src, tgt, ships):
    d = math.hypot(src[2] - tgt[2], src[3] - tgt[3])
    return d / fleet_speed(max(1, ships))


def _process_file(args):
    path, game_idx = args
    rows_X, rows_yl, rows_yf, rows_g, rows_w = [], [], [], [], []
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            obs, moves, won = r["obs"], r["moves"], r.get("won", False)
            player = obs["player"]
            planets = obs["planets"]
            fleets = obs["fleets"]
            mine = [p for p in planets if p[1] == player]
            if not mine:
                continue
            launched = {}  # (src, tgt) -> ships
            for mv in moves:
                dec = _decode_target(mv, obs)
                if dec is not None:
                    launched[(int(mv[0]), dec[0])] = launched.get((int(mv[0]), dec[0]), 0) + int(mv[2])
            my_tot = sum(p[5] for p in mine) or 1.0
            opp_tot = sum(p[5] for p in planets if p[1] not in (-1, player)) or 1.0
            n_my = len(mine)
            n_opp = sum(1 for p in planets if p[1] not in (-1, player))
            step_frac = obs["step"] / 500.0
            init_by_id = {p[0]: p for p in obs["initial_planets"]}
            comets = set(obs.get("comet_planet_ids", []) or [])
            traj, sched = project(
                planets,
                fleets,
                obs["angular_velocity"],
                init_by_id,
                obs["step"],
                PROJ_H,
                comet_ids=comets,
            )
            for src in mine:
                if src[5] < 1:
                    continue
                for tgt in planets:
                    if tgt[0] == src[0]:
                        continue
                    mi, ei = _inbound(tgt, fleets, player)
                    eta_v = _eta(src, tgt, int(src[5] // 2) or 1)
                    k = max(1, min(PROJ_H, int(math.ceil(eta_v))))
                    tt = traj.get(tgt[0])
                    if tt is not None:
                        def_eta = tt["ships"][k]
                        o_eta = tt["owner"][k]
                        flips = 1.0 if any(tt["owner"][i] != tgt[1] for i in range(1, PROJ_H + 1)) else 0.0
                    else:
                        def_eta, o_eta, flips = tgt[5], tgt[1], 0.0
                    fr_arr = sum(s for _k, o, s in sched.get(tgt[0], []) if o == player)
                    en_arr = sum(s for _k, o, s in sched.get(tgt[0], []) if o not in (player, -1))
                    rows_X.append(
                        [
                            src[5],
                            src[6],
                            1.0 if tgt[1] == player else 0.0,
                            1.0 if tgt[1] not in (-1, player) else 0.0,
                            1.0 if tgt[1] == -1 else 0.0,
                            tgt[5],
                            tgt[6],
                            tgt[4],
                            math.hypot(src[2] - tgt[2], src[3] - tgt[3]),
                            eta_v,
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
                    s = launched.get((src[0], tgt[0]), 0)
                    rows_yl.append(1.0 if s > 0 else 0.0)
                    rows_yf.append(min(1.0, s / src[5]) if s > 0 else 0.0)
                    rows_g.append(game_idx)
                    rows_w.append(1.0 if won else 0.0)
    return rows_X, rows_yl, rows_yf, rows_g, rows_w, len(rows_X)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.expanduser("~/work/distill_data"))
    ap.add_argument("--out", default=os.path.expanduser("~/work/distill_pairs.npz"))
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0, help="debug: only N files")
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(args.data, "*.jsonl.gz")))
    if args.limit:
        files = files[: args.limit]
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    print(f"=== distill_prep: {len(files)} games, procs={procs} ===", flush=True)

    X, yl, yf, g, w = [], [], [], [], []
    tasks = [(p, i) for i, p in enumerate(files)]
    with Pool(procs) as pool:
        for i, res in enumerate(pool.imap_unordered(_process_file, tasks)):
            X += res[0]
            yl += res[1]
            yf += res[2]
            g += res[3]
            w += res[4]
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(files)} files, {len(X)} pairs", flush=True)
    Xa = np.asarray(X, dtype=np.float32)
    np.savez_compressed(
        args.out,
        X=Xa,
        y_launch=np.asarray(yl, dtype=np.float32),
        y_frac=np.asarray(yf, dtype=np.float32),
        game=np.asarray(g, dtype=np.int32),
        won=np.asarray(w, dtype=np.float32),
        feats=np.asarray(FEATS),
    )
    pos = sum(yl)
    print(
        f"DONE: {Xa.shape[0]} pairs ({Xa.shape[1]} feats), "
        f"{int(pos)} launches ({100.0 * pos / max(1, len(yl)):.2f}% positive) "
        f"-> {args.out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
