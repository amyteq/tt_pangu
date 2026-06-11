"""T8 — co-arrival strike A/B on the ladder-predictive gate (issue #87).

Baseline (forecast.py defaults) vs OW_COARRIVAL=1, measured per the T2 power
protocol: >= 150 paired seeds (300 games, +-3.5pt 95% CI) per config vs evogen,
plus a starter no-regress check (>= 85%). Fresh seed block 9500+ (7000s/8000s/
9000-9300 burned by suite gating and T2).

Usage:
    python arena/t8_ab.py --seeds 150 --procs 23
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
FC = f"{V}/forecast.py"
EVO = f"{V}/suite/evogen1093.py"

CONFIGS = [
    ("baseline", None),
    ("coarrival", {"OW_COARRIVAL": "1"}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=150)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--seed0", type=int, default=9500)
    args = ap.parse_args()
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    evo_seeds = list(range(args.seed0, args.seed0 + args.seeds))
    st_seeds = list(range(args.seed0, args.seed0 + max(30, args.seeds // 3)))

    print(
        f"=== T8 A/B: {len(evo_seeds)}x2 vs evogen + {len(st_seeds)}x2 vs starter "
        f"per config, procs={procs}, seeds {args.seed0}+ ===",
        flush=True,
    )
    for name, ov in CONFIGS:
        t0 = time.perf_counter()
        e = P.h2h(FC, EVO, evo_seeds, overrides=ov, procs=procs)
        s = P.h2h(FC, "starter", st_seeds, overrides=ov, procs=procs)
        dt = time.perf_counter() - t0
        print(
            f"{name:10s} evogen={e['winpct']:5.1f}% ({e['w']}-{e['l']}-{e['t']}/{e['n']})  "
            f"starter={s['winpct']:5.1f}% ({s['w']}-{s['l']}-{s['t']}/{s['n']})  "
            f"[{dt:.0f}s]",
            flush=True,
        )


if __name__ == "__main__":
    main()
