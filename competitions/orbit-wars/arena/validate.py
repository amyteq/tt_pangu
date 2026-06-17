"""Parallel clean validation of the baked agent on FRESH unseen seeds (4000+)."""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
VER = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--base", type=int, default=4000, help="first seed (held out from tuning)")
    args = ap.parse_args()
    seeds = list(range(args.base, args.base + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    print(f"=== validation on {len(seeds)} FRESH seeds ({args.base}+), x2, procs={procs} ===")
    print(P.fmt("current vs v2", P.h2h(MAIN, os.path.join(VER, "v2.py"), seeds, procs=procs)))
    print(P.fmt("current vs v1", P.h2h(MAIN, os.path.join(VER, "v1.py"), seeds, procs=procs)))
    print(P.fmt("current vs starter", P.h2h(MAIN, "starter", seeds, procs=procs)))
    print(P.fmt("current vs random", P.h2h(MAIN, "random", seeds, procs=procs)))
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
