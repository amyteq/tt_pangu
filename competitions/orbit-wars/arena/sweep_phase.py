"""Parallel phase-scaled in-flight cap sweep. Gate = beat the frozen v2 snapshot.

Candidate = agent/main.py with OW_CAP_EARLY/OW_CAP_LATE overrides; opponent = v2.py
snapshot, which predates those knobs and so stays pinned at flat-1.2 (clean A/B).
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
V2 = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "v2.py"))

CONFIGS = {
    "flat 1.2/1.2 (sanity)": (1.2, 1.2),
    "1.6 -> 0.9": (1.6, 0.9),
    "2.0 -> 1.0": (2.0, 1.0),
    "2.0 -> 0.8": (2.0, 0.8),
    "2.5 -> 0.8": (2.5, 0.8),
    "2.5 -> 0.6": (2.5, 0.6),
    "3.0 -> 0.7": (3.0, 0.7),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--base", type=int, default=2000)
    args = ap.parse_args()
    seeds = list(range(args.base, args.base + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    print(f"=== phase sweep vs v2 ({len(seeds)} seeds x2, procs={procs}) ===")
    for name, (early, late) in CONFIGS.items():
        ov = {"OW_CAP_EARLY": early, "OW_CAP_LATE": late}
        r = P.h2h(MAIN, V2, seeds, overrides=ov, procs=procs)
        flag = "  <-- beats v2" if r["winpct"] > 50 else ""
        print(f"{name:24s}: {r['w']:>2}W {r['l']:>2}L {r['t']:>2}T  win%_vs_v2={r['winpct']:5.1f}{flag}")
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
