"""T8 — co-arrival A/B vs the rest of the strong tier (multifocus, kuni05).

Same power protocol as t8_ab.py (>= 150 paired seeds per cell, fresh block).
Run on snorlax (24 cores) while the evogen confirmation runs locally.

Usage:
    python arena/t8_strong.py --seeds 150 --seed0 10000 --procs 23
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
FC = f"{V}/forecast.py"

OPPONENTS = [
    ("multifocus", f"{V}/suite/multifocus.py"),
    ("kuni05", f"{V}/kuni05/main.py"),
]
CONFIGS = [
    ("baseline", None),
    ("coarrival", {"OW_COARRIVAL": "1"}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=150)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--seed0", type=int, default=10000)
    args = ap.parse_args()
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    seeds = list(range(args.seed0, args.seed0 + args.seeds))

    print(
        f"=== T8 strong-tier A/B: {len(seeds)}x2 per cell, procs={procs}, seeds {args.seed0}+ ===",
        flush=True,
    )
    for opp_name, opp in OPPONENTS:
        for cfg_name, ov in CONFIGS:
            t0 = time.perf_counter()
            r = P.h2h(FC, opp, seeds, overrides=ov, procs=procs)
            print(
                f"vs {opp_name:11s} {cfg_name:10s} {r['winpct']:5.1f}% "
                f"({r['w']}-{r['l']}-{r['t']}/{r['n']})  "
                f"[{time.perf_counter() - t0:.0f}s]",
                flush=True,
            )


if __name__ == "__main__":
    main()
