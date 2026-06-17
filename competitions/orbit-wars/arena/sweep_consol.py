"""Consolidation sensitivity sweep. Gate = beat v2.1 snapshot (consolidation absent).

If no setting beats ~50%, consolidation is a dead lever and should default OFF.
"""

import argparse, os, time
import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))
V21 = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "v2_1.py"))

CONFIGS = {
    "OFF (sanity ~50%)": {"OW_CONSOLIDATE": 0},
    "min=12 (default)": {"OW_CONSOLIDATE": 1, "OW_CONSOLIDATE_MIN": 12},
    "min=30": {"OW_CONSOLIDATE": 1, "OW_CONSOLIDATE_MIN": 30},
    "min=60": {"OW_CONSOLIDATE": 1, "OW_CONSOLIDATE_MIN": 60},
    "min=100": {"OW_CONSOLIDATE": 1, "OW_CONSOLIDATE_MIN": 100},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--base", type=int, default=2000)
    args = ap.parse_args()
    seeds = list(range(args.base, args.base + args.games))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    print(f"=== consolidation sweep vs v2.1 ({len(seeds)} seeds x2, procs={procs}) ===")
    for name, ov in CONFIGS.items():
        r = P.h2h(MAIN, V21, seeds, overrides=ov, procs=procs)
        flag = "  <-- beats v2.1" if r["winpct"] > 50 else ""
        print(f"{name:22s}: {r['w']:>3}W {r['l']:>3}L  win%_vs_v2.1={r['winpct']:5.1f}{flag}")
    print(f"[wall: {time.perf_counter() - t0:.1f}s]")


if __name__ == "__main__":
    main()
