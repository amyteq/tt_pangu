"""4-player free-for-all arena. The competition runs 2 OR 4 player matches; this
covers the 4p case our 2p arena was blind to.

Metric: hero win-rate (placed 1st of 4) and avg finishing rank. Baselines: a random
or mirror field should give the hero ~25% win and ~2.5 rank.

Usage:
    python competitions/orbit-wars/arena/arena4.py --games 30 --procs 23
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
VER = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
PUB = os.path.join(VER, "pub_tactical.py")
V1 = os.path.join(VER, "v1.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30, help="seeds (x4 hero seats)")
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--base", type=int, default=6000, help="first seed (held out)")
    args = ap.parse_args()
    seeds = list(range(args.base, args.base + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    print(f"=== 4-PLAYER arena ({len(seeds)} seeds x4 seats, procs={procs}, base={args.base}) ===")

    # Hero = v2.1 against various 3-opponent fields.
    print(P.fmt4("v2.1 vs 3x random", P.ffa(MAIN, ["random"] * 3, seeds, procs=procs)))
    print(P.fmt4("v2.1 vs 3x starter", P.ffa(MAIN, ["starter"] * 3, seeds, procs=procs)))
    print(P.fmt4("v2.1 vs 3x pub_tactical", P.ffa(MAIN, [PUB] * 3, seeds, procs=procs)))
    print(P.fmt4("v2.1 vs [pub,v1,starter]", P.ffa(MAIN, [PUB, V1, "starter"], seeds, procs=procs)))
    # Sanity: mirror field -> hero should be ~25%.
    print(P.fmt4("v2.1 vs 3x v2.1 (mirror)", P.ffa(MAIN, [MAIN] * 3, seeds, procs=procs)))
    # How strong is pub_tactical itself in 4p?
    print(P.fmt4("pub_tactical vs 3x starter", P.ffa(PUB, ["starter"] * 3, seeds, procs=procs)))
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
