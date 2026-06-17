"""Fidelity test: forecast_sim.project vs the REAL engine, with fleets in flight.

Strategy: one agent launches several fleets ONLY on step 0, then both agents no-op.
With no further launches, the engine's evolution from step 1 is a pure do-nothing
projection — exactly what project() computes. Compare planet (owner, ships) over H.
"""

import logging

logging.disable(logging.INFO)
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kaggle_environments import make
import forecast_sim as fs

_FIRED = {}


def launcher(obs):
    pid = obs["player"]
    step = obs.get("step", 0)
    if step != 0:
        return []
    planets = obs["planets"]
    mine = [p for p in planets if p[1] == pid]
    others = [p for p in planets if p[1] != pid]
    moves = []
    for mp in mine:
        # fire at the 3 nearest other planets, splitting ships, to create varied fleets
        others.sort(key=lambda t: math.hypot(mp[2] - t[2], mp[3] - t[3]))
        budget = mp[5]
        for t in others[:3]:
            send = max(5, int(budget // 4))
            if send < 1:
                break
            ang = math.atan2(t[3] - mp[3], t[2] - mp[2])
            moves.append([mp[0], ang, send])
    return moves


def noop(obs):
    return []


def run(seed):
    env = make("orbit_wars", configuration={"seed": seed})
    env.run([launcher, noop])
    steps = env.steps
    H = 18
    # state at real step 1 (fleets now in flight; no further launches by either side)
    o1 = steps[1][0]["observation"]
    planets = [list(p) for p in o1["planets"]]
    fleets = [list(f) for f in o1["fleets"]]
    ang = o1["angular_velocity"]
    init_by_id = {p[0]: p for p in o1["initial_planets"]}
    comet_ids = set(o1.get("comet_planet_ids", []) or [])
    traj, _arr = fs.project(planets, fleets, ang, init_by_id, 1, H, comet_ids=comet_ids)

    max_ship_err = 0.0
    owner_mism = 0
    cells = 0
    for k in range(1, H + 1):
        if 1 + k >= len(steps):
            break
        real = {p[0]: p for p in steps[1 + k][0]["observation"]["planets"]}
        for pid, t in traj.items():
            if pid not in real or pid in comet_ids:
                continue
            cells += 1
            rs, ro = real[pid][5], real[pid][1]
            ps, po = t["ships"][k], t["owner"][k]
            max_ship_err = max(max_ship_err, abs(rs - ps))
            if ro != po:
                owner_mism += 1
    return max_ship_err, owner_mism, cells


tot_err = 0.0
tot_mis = 0
tot_cells = 0
for seed in range(1, 9):
    e, m, c = run(seed)
    tot_err = max(tot_err, e)
    tot_mis += m
    tot_cells += c
    print(f"seed {seed}: max_ship_err={e:.3f}  owner_mismatches={m}/{c}")
print(f"\nOVERALL: max_ship_err={tot_err:.3f}  owner_mismatches={tot_mis}/{tot_cells}")
print("PASS" if tot_err < 1e-3 and tot_mis == 0 else "MISMATCH — sim diverges from engine")
