"""4-player FFA placement evaluation (KCT-OW-LIVE-002 follow-up).

The ladder runs BOTH 2p and 4p episodes and BOTH update μ (verified from the
flyingfox 205-episode history: ~half the games are 4p). Our suite_gate/league
are 2p-only — this fills the gap with a 4p PLACEMENT gate (μ in 4p is
placement-vs-rating, TrueSkill-like, so the metric is avg_rank, not just wins).

Metrics per arm: avg_rank (1=best of 4, 2.5=random), 1st-rate, and the two
strongest win/lose dividers from the flyingfox 4p analysis — eliminated-before
-t50 rate and planets-at-t50 — computed by replaying each FFA game's final +
mid states.

Usage:
    python arena/eval_4p.py --hero agent/main.py --field agent/versions/v3_2.py \
        --games 30 --seed0 60000 --procs 4 [--hero-env OW_4P_MODE=1]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import logging  # noqa: E402

logging.disable(logging.INFO)
from kaggle_environments import make  # noqa: E402

CENTER, SUN_R = 50.0, 10.0


def _planets_owned(obs, seat):
    return sum(1 for p in obs.get("planets", []) if p[1] == seat)


def _play(task):
    seat, hero, field, seed, hero_env = task
    # hero_env applies process-wide; the FIELD must ignore OW_* (use frozen
    # snapshots that don't read the swept keys, like the 2p sweep convention).
    for k in [k for k in os.environ if k.startswith("OW_")]:
        del os.environ[k]
    if hero_env:
        os.environ.update(hero_env)
    agents = field[:seat] + [hero] + field[seat:]
    env = make("orbit_wars", configuration={"seed": seed})
    env.run(agents)
    last = env.steps[-1][0]["observation"]
    rewards = [s["reward"] for s in env.steps[-1]]
    hr = rewards[seat]
    rank = 1 + sum(1 for r in rewards if r is not None and hr is not None and r > hr)
    # elimination + planets-at-t50 for the hero seat
    elim_t50 = 1 if (len(env.steps) > 50 and _planets_owned(env.steps[50][0]["observation"], seat) == 0) else 0
    planets_t50 = (
        _planets_owned(env.steps[50][0]["observation"], seat) if len(env.steps) > 50 else _planets_owned(last, seat)
    )
    final_planets = _planets_owned(last, seat)
    return rank, (1 if rank == 1 else 0), elim_t50, planets_t50, final_planets


def evaluate(hero, field3, games, seed0, procs, hero_env=None):
    tasks = []
    for seed in range(seed0, seed0 + games):
        for seat in range(4):
            tasks.append((seat, hero, field3, seed, hero_env))
    with Pool(procs) as pool:
        res = pool.map(_play, tasks)
    n = len(res)
    return {
        "n": n,
        "avg_rank": round(sum(r[0] for r in res) / n, 3),
        "first_rate": round(100 * sum(r[1] for r in res) / n, 1),
        "elim_t50_rate": round(100 * sum(r[2] for r in res) / n, 1),
        "planets_t50": round(sum(r[3] for r in res) / n, 2),
        "final_planets": round(sum(r[4] for r in res) / n, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", required=True)
    ap.add_argument("--field", required=True, help="opponent file (used x3)")
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--seed0", type=int, default=60000)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--hero-env", action="append", default=[], help="K=V applied to hero")
    args = ap.parse_args()
    hero_env = dict(kv.split("=", 1) for kv in args.hero_env)
    field3 = [args.field, args.field, args.field]
    t0 = time.perf_counter()
    r = evaluate(args.hero, field3, args.games, args.seed0, args.procs, hero_env)
    env_tag = (" env=" + ",".join(f"{k}={v}" for k, v in hero_env.items())) if hero_env else ""
    print(f"4p: {os.path.relpath(args.hero, COMP)} vs 3x {os.path.relpath(args.field, COMP)}{env_tag}")
    print(
        f"  avg_rank={r['avg_rank']}/4  1st={r['first_rate']}%  "
        f"elim_by_t50={r['elim_t50_rate']}%  planets@t50={r['planets_t50']}  "
        f"final_planets={r['final_planets']}  ({r['n']}g, {time.perf_counter() - t0:.0f}s)"
    )


if __name__ == "__main__":
    main()
