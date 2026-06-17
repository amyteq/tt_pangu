"""Orbit Wars local arena — parallel round-robin / head-to-head on the REAL engine.

Usage:
    python competitions/orbit-wars/arena/arena.py                 # default suite
    python competitions/orbit-wars/arena/arena.py --games 24 --procs 16
    python competitions/orbit-wars/arena/arena.py --a v1 --b starter

AGENT may be a builtin name ("random","starter"), "v1"/"v2"/"v2.1"/"main", or a path.
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
VERSIONS = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))


def resolve(name):
    if name in ("random", "starter"):
        return name
    if name in ("main", "v2.1", "v21"):
        return MAIN
    if name in ("v1", "v2"):
        return os.path.join(VERSIONS, f"{name}.py")
    if name in ("pub", "pub_tactical", "tactical"):
        return os.path.join(VERSIONS, "pub_tactical.py")
    if name in ("kuni", "kuni05"):
        return os.path.join(VERSIONS, "kuni05", "main.py")
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=16, help="seeds (x2 orderings)")
    ap.add_argument("--procs", type=int, default=None, help="worker processes (default cpu-1)")
    ap.add_argument("--a", default=None)
    ap.add_argument("--b", default=None)
    args = ap.parse_args()
    seeds = list(range(1000, 1000 + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()

    if args.a and args.b:
        r = P.h2h(resolve(args.a), resolve(args.b), seeds, procs=procs)
        print(P.fmt(f"{args.a} vs {args.b}", r))
    else:
        print(f"=== Orbit Wars arena (procs={procs}, {len(seeds)} seeds x2) ===")
        print(P.fmt("v2.1 vs random", P.h2h(MAIN, "random", seeds, procs=procs)))
        print(P.fmt("v2.1 vs starter", P.h2h(MAIN, "starter", seeds, procs=procs)))
        print(P.fmt("v2.1 vs pub_tactical", P.h2h(MAIN, os.path.join(VERSIONS, "pub_tactical.py"), seeds, procs=procs)))
        print(P.fmt("v2.1 vs v1", P.h2h(MAIN, os.path.join(VERSIONS, "v1.py"), seeds, procs=procs)))
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
