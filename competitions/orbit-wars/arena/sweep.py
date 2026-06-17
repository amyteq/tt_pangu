"""Parallel garrison/cap tunable sweep. Gate = beat the frozen v1 snapshot.

Candidate = agent/main.py with OW_* overrides; opponent = v1.py (reads no env vars,
so it is unaffected by the overrides — a clean A/B).
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
V1 = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "v1.py"))

CONFIGS = {
    "v1-equiv (floors off)": dict(OW_REAR_FLOOR=0, OW_FRONTIER_FLOOR=0, OW_PROD_MULT=0, OW_INFLIGHT_CAP=5.0),
    "frontier=8": dict(OW_REAR_FLOOR=0, OW_FRONTIER_FLOOR=8, OW_PROD_MULT=0, OW_INFLIGHT_CAP=5.0),
    "frontier=14": dict(OW_REAR_FLOOR=0, OW_FRONTIER_FLOOR=14, OW_PROD_MULT=0, OW_INFLIGHT_CAP=5.0),
    "frontier=8+rear=3": dict(OW_REAR_FLOOR=3, OW_FRONTIER_FLOOR=8, OW_PROD_MULT=0, OW_INFLIGHT_CAP=5.0),
    "frontier=10+cap1.2": dict(OW_REAR_FLOOR=0, OW_FRONTIER_FLOOR=10, OW_PROD_MULT=0, OW_INFLIGHT_CAP=1.2),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--base", type=int, default=2000)
    args = ap.parse_args()
    seeds = list(range(args.base, args.base + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    print(f"=== garrison/cap sweep vs v1 ({len(seeds)} seeds x2, procs={procs}) ===")
    for name, ov in CONFIGS.items():
        r = P.h2h(MAIN, V1, seeds, overrides=ov, procs=procs)
        flag = "  <-- beats v1" if r["winpct"] > 50 else ""
        print(f"{name:24s}: {r['w']:>2}W {r['l']:>2}L {r['t']:>2}T  win%_vs_v1={r['winpct']:5.1f}{flag}")
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
