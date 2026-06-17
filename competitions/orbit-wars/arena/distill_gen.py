"""T12 phase A — behavior-cloning data from kuni05 (teacher, LB ~1240).

Plays kuni05 against a diverse opponent pool and records every (observation,
teacher_moves) pair from kuni05's seats as gzipped JSONL, one file per game:

    {"seed": int, "seat": 0|1, "opp": str, "step": int,
     "obs": {planets, fleets, angular_velocity, initial_planets,
             comet_planet_ids, step, player},
     "moves": [[src_id, angle, ships], ...]}

CPU-only, embarrassingly parallel — designed for snorlax's 24 cores. ~500
samples per game; 300 games ~= 150k samples (~100 MB gz total).

Usage:
    python arena/distill_gen.py --games-per-opp 75 --seed0 11000 \
        --out ~/work/distill_data --procs 23
"""

import argparse
import gzip
import importlib.util
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
KUNI = f"{V}/kuni05/main.py"

OPPONENTS = [
    ("forecast", f"{V}/forecast.py"),
    ("evogen1093", f"{V}/suite/evogen1093.py"),
    ("multifocus", f"{V}/suite/multifocus.py"),
    ("kuni05", KUNI),  # mirror games: teacher vs itself
]


def _load_agent(path):
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location("teacher_" + os.path.basename(d), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look the module up in sys.modules
    spec.loader.exec_module(mod)
    return mod.agent


def _obs_to_dict(obs):
    return {
        "planets": obs.get("planets", []),
        "fleets": obs.get("fleets", []),
        "angular_velocity": obs.get("angular_velocity", 0.0),
        "initial_planets": obs.get("initial_planets", []),
        "comet_planet_ids": obs.get("comet_planet_ids", []),
        "step": obs.get("step", 0),
        "player": obs.get("player", 0),
    }


def _play(task):
    seed, seat, opp_name, opp_path, out_dir = task
    import logging

    logging.disable(logging.INFO)
    for k in [k for k in os.environ if k.startswith("OW_")]:
        del os.environ[k]
    from kaggle_environments import make

    teacher = _load_agent(KUNI)
    rows = []

    def hero(obs, cfg=None):
        mv = teacher(obs) or []
        rows.append(
            {
                "seed": seed,
                "seat": seat,
                "opp": opp_name,
                "step": obs.get("step", 0),
                "obs": _obs_to_dict(obs),
                "moves": mv,
            }
        )
        return mv

    env = make("orbit_wars", configuration={"seed": seed})
    players = [hero, opp_path] if seat == 0 else [opp_path, hero]
    env.run(players)
    rewards = [s["reward"] for s in env.steps[-1]]
    won = rewards[seat] > rewards[1 - seat]
    fn = os.path.join(out_dir, f"kuni05_{opp_name}_s{seed}_p{seat}.jsonl.gz")
    with gzip.open(fn, "wt") as f:
        for r in rows:
            r["won"] = won
            f.write(json.dumps(r) + "\n")
    return fn, len(rows), won


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-per-opp", type=int, default=75)
    ap.add_argument("--seed0", type=int, default=11000)
    ap.add_argument("--out", default=os.path.expanduser("~/work/distill_data"))
    ap.add_argument("--procs", type=int, default=None)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)

    tasks = []
    for i, (opp_name, opp_path) in enumerate(OPPONENTS):
        for j in range(args.games_per_opp):
            seed = args.seed0 + i * args.games_per_opp + j
            tasks.append((seed, j % 2, opp_name, opp_path, args.out))

    print(
        f"=== distill_gen: {len(tasks)} games, procs={procs}, out={args.out} ===",
        flush=True,
    )
    wins = total = samples = 0
    with Pool(procs) as pool:
        for fn, n, won in pool.imap_unordered(_play, tasks):
            total += 1
            samples += n
            wins += int(won)
            if total % 25 == 0:
                print(
                    f"  {total}/{len(tasks)} games, {samples} samples, teacher wins {wins}",
                    flush=True,
                )
    print(
        f"DONE: {total} games, {samples} samples, teacher win-rate {100.0 * wins / total:.1f}%",
        flush=True,
    )


if __name__ == "__main__":
    main()
