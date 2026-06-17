"""T2 — systematic OW_* knob search on the ladder-predictive gate (issue #87, D1=C).

Zero-dependency random search (optuna not in env). Objective: maximize win% vs
evogen1093 subject to a no-regress constraint vs starter (>= 85%). Opponents read
no OW_* env vars, so overrides only affect the candidate (clean A/B).

RESULT OF ROUND 1 (2026-06-12, ~2,800 games over 3 stages): NEGATIVE — no config
significantly beats the baked defaults. Definitive 300-game/config test (seeds
9000+): baseline 11.3%±3.6 vs evogen, best challenger (H22) 10.3%±3.4, t05 5.3%±2.5
(worse). Earlier "25%" signals on 24-40-game batches were noise + selection bias.

POWER PROTOCOL (mandatory for any future round): the SAME config swings 8-27% vs
evogen across 24-60-game seed batches. Any comparison needs >= 150 paired seeds
(300 games, +-3.5pt 95% CI) per config; differences < ~7pt are not decidable.
With --procs 23 that costs ~1-2 min/config — budget accordingly (~30 configs/hour).

Usage:
    python arena/sweep_opt.py --trials 20 --games 150 --procs 23 [--rng 1]
"""

import argparse
import os
import random
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
FC = f"{V}/forecast.py"
EVO = f"{V}/suite/evogen1093.py"

SPACE = {
    "OW_PROJ_H": [12, 16, 18, 22, 26],
    "OW_FRONTIER_FLOOR": [0, 5, 10, 15, 25],
    "OW_FRONTIER_DIST": [20.0, 28.0, 36.0],
    "OW_PROD_MULT": [0, 1, 2],
    "OW_REAR_FLOOR": [0, 3],
    "OW_CAP_EARLY": [1.6, 2.0, 2.6, 3.2],
    "OW_CAP_LATE": [0.8, 1.0, 1.3],
}
BASELINE = {  # current baked defaults (v3.1-equivalent forecast.py)
    "OW_PROJ_H": 18,
    "OW_FRONTIER_FLOOR": 10,
    "OW_FRONTIER_DIST": 28.0,
    "OW_PROD_MULT": 0,
    "OW_REAR_FLOOR": 0,
    "OW_CAP_EARLY": 2.0,
    "OW_CAP_LATE": 1.0,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--games", type=int, default=12, help="seeds per opponent (x2 seats)")
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--rng", type=int, default=1)
    ap.add_argument("--seed0", type=int, default=8000, help="fresh block per VALIDATION.md")
    args = ap.parse_args()
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    evo_seeds = list(range(args.seed0, args.seed0 + args.games))
    st_seeds = list(range(args.seed0, args.seed0 + max(6, args.games // 2)))
    rng = random.Random(args.rng)

    configs = [("baseline", BASELINE)]
    seen = {tuple(sorted(BASELINE.items()))}
    while len(configs) < args.trials + 1:
        c = {k: rng.choice(v) for k, v in SPACE.items()}
        key = tuple(sorted(c.items()))
        if key not in seen:
            seen.add(key)
            configs.append((f"t{len(configs):02d}", c))

    print(
        f"=== T2 random search: {len(configs)} configs, evogen {len(evo_seeds)}x2 + "
        f"starter {len(st_seeds)}x2 games each, procs={procs}, seeds {args.seed0}+ ==="
    )
    results = []
    t0 = time.perf_counter()
    for name, cfg in configs:
        ov = {k: str(v) for k, v in cfg.items()}
        e = P.h2h(FC, EVO, evo_seeds, overrides=ov, procs=procs)
        s = P.h2h(FC, "starter", st_seeds, overrides=ov, procs=procs)
        ok = s["winpct"] >= 85.0
        results.append((e["winpct"] if ok else -1.0, name, cfg, e, s))
        flag = "" if ok else "  [REJECT: starter regress]"
        print(f"{name:9s} evogen={e['winpct']:5.1f}% ({e['w']}-{e['l']})  starter={s['winpct']:5.1f}%{flag}  cfg={cfg}")
    results.sort(reverse=True, key=lambda r: r[0])
    print(f"\n=== TOP 5 (wall {time.perf_counter() - t0:.0f}s) ===")
    for score, name, cfg, e, s in results[:5]:
        print(f"{name:9s} evogen={e['winpct']:5.1f}%  starter={s['winpct']:5.1f}%  {cfg}")


if __name__ == "__main__":
    main()
