"""T12 v2 prep — winner-side BC pairs from TOP-PLAYER replay episodes (方案 1).

Same 22-feature pair format as distill_prep.py (which extracts from locally
generated kuni05 games); here the teacher is whoever WON a selected ladder
episode, so the data covers the actual 1500-1700 tier. Select episodes via the
index CSV (episodes_index.py) by winner name or min final-ship margin.

Usage:
    python arena/episodes_prep.py --data ../../data/orbit-wars-episodes \
        --index ~/work/episodes_index.csv \
        --winners "Jake Will" --min-games 1 \
        --out ~/work/episode_pairs.npz --procs 22
"""

import argparse
import csv
import json
import math
import os
from multiprocessing import Pool

import numpy as np
from distill_prep import FEATS, PROJ_H, _decode_target, _eta, _inbound, project


def _process_episode(args):
    path, winner_seat = args
    rows_X, rows_yl, rows_yf, rows_g = [], [], [], []
    try:
        d = json.load(open(path))
    except Exception:
        return rows_X, rows_yl, rows_yf, rows_g
    gid = int(os.path.basename(path).split(".")[0]) % 2_000_000_000
    for st in d.get("steps", []):
        obs0 = st[0].get("observation") or {}
        moves = st[winner_seat].get("action") or []
        planets = obs0.get("planets") or []
        fleets = obs0.get("fleets") or []
        player = winner_seat
        mine = [p for p in planets if p[1] == player]
        if not mine:
            continue
        obs = {
            "planets": planets,
            "fleets": fleets,
            "angular_velocity": obs0.get("angular_velocity", 0.0),
            "initial_planets": obs0.get("initial_planets", []),
            "comet_planet_ids": obs0.get("comet_planet_ids", []),
            "step": obs0.get("step", 0),
            "player": player,
        }
        launched = {}
        for mv in moves:
            try:
                dec = _decode_target(mv, obs)
            except Exception:
                dec = None
            if dec is not None:
                key = (int(mv[0]), dec[0])
                launched[key] = launched.get(key, 0) + int(mv[2])
        my_tot = sum(p[5] for p in mine) or 1.0
        opp_tot = sum(p[5] for p in planets if p[1] not in (-1, player)) or 1.0
        n_my = len(mine)
        n_opp = sum(1 for p in planets if p[1] not in (-1, player))
        step_frac = obs["step"] / 500.0
        init_by_id = {p[0]: p for p in obs["initial_planets"]}
        comets = set(obs["comet_planet_ids"] or [])
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
                    def_eta, o_eta = tt["ships"][k], tt["owner"][k]
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
                rows_g.append(gid)
    return rows_X, rows_yl, rows_yf, rows_g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--winners", default="", help="comma-separated winner names; empty = all")
    ap.add_argument("--min-steps", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.expanduser("~/work/episode_pairs.npz"))
    ap.add_argument("--procs", type=int, default=None)
    args = ap.parse_args()
    want = {w.strip() for w in args.winners.split(",") if w.strip()}

    tasks = []
    with open(args.index) as f:
        for r in csv.DictReader(f):
            if r["winner"] == "tie":
                continue
            if want and r["winner"] not in want:
                continue
            if int(r["steps"]) < args.min_steps:
                continue
            seat = 0 if r["winner"] == r["p0"] else 1
            path = os.path.join(args.data, r["episode"] + ".json")
            if os.path.exists(path):
                tasks.append((path, seat))
    if args.limit:
        tasks = tasks[: args.limit]
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    print(f"=== episodes_prep: {len(tasks)} episodes, procs={procs} ===", flush=True)

    X, yl, yf, g = [], [], [], []
    n_pairs = 0
    with Pool(procs) as pool:
        for i, res in enumerate(pool.imap_unordered(_process_episode, tasks)):
            if res[0]:
                # float32 per episode keeps peak memory ~2x the final array size
                X.append(np.asarray(res[0], dtype=np.float32))
                yl.append(np.asarray(res[1], dtype=np.float32))
                yf.append(np.asarray(res[2], dtype=np.float32))
                g.append(np.asarray(res[3], dtype=np.int32))
                n_pairs += len(res[1])
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(tasks)} episodes, {n_pairs} pairs", flush=True)
    Xa = np.vstack(X) if X else np.zeros((0, len(FEATS)), dtype=np.float32)
    yla = np.concatenate(yl) if yl else np.zeros(0, dtype=np.float32)
    yfa = np.concatenate(yf) if yf else np.zeros(0, dtype=np.float32)
    ga = np.concatenate(g) if g else np.zeros(0, dtype=np.int32)
    np.savez_compressed(
        args.out,
        X=Xa,
        y_launch=yla,
        y_frac=yfa,
        game=ga,
        won=np.ones(len(yla), dtype=np.float32),  # winner-side only by construction
        feats=np.asarray(FEATS),
    )
    pos = float(yla.sum())
    print(
        f"DONE: {Xa.shape[0]} pairs, {int(pos)} launches "
        f"({100.0 * pos / max(1, len(yla)):.2f}% positive) -> {args.out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
