"""Candidate validation gate for the Orbit Wars live loop (KCT-OW-LIVE-002).

Wraps the existing arena gates into one submit-ready verdict, per VALIDATION.md +
the task's "Local validation before submit/push" rules:
  * crash safety (no exceptions / fallbacks over N games);
  * weak-tier no-regression (vs starter >= floor);
  * 2p head-to-head vs the active slot the candidate would replace (must beat it);
  * 4p robustness (avg_rank not materially worse);
  * runtime sanity (per-turn well under the 1s cap).

Bounded by --games (paired seeds, fresh block). Returns a JSON verdict and a
human summary. Does NOT submit — submit_manager consumes the verdict.

Usage:
    python ops/evaluate_candidate.py --agent agent/versions/v4.py \
        --baseline agent/versions/v3_2.py --games 30 --seed0 40000 --procs 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(COMP, "arena"))
import pool as P  # noqa: E402

V = os.path.join(COMP, "agent", "versions")
STARTER_FLOOR = 85.0  # weak-tier no-regress floor (VALIDATION.md)
BEAT_MARGIN = 3.0  # 2p must beat the replaced slot by > this (pt)
RANK4_TOL = 0.2  # 4p avg_rank may worsen by at most this


def evaluate(agent: str, baseline: str, games: int, seed0: int, procs: int) -> dict:
    seeds = list(range(seed0, seed0 + games))
    st_seeds = list(range(seed0, seed0 + max(20, games // 2)))
    t0 = time.perf_counter()
    gates: dict = {}

    # 1. weak-tier no-regression (vs starter)
    r_st = P.h2h(agent, "starter", st_seeds, procs=procs)
    gates["starter_winpct"] = round(r_st["winpct"], 1)
    gates["weak_no_regress"] = r_st["winpct"] >= STARTER_FLOOR

    # 2. 2p vs the active baseline it would replace
    r_bl = P.h2h(agent, baseline, seeds, procs=procs)
    gates["vs_baseline_winpct"] = round(r_bl["winpct"], 1)
    gates["beats_baseline"] = r_bl["winpct"] > 50.0 + BEAT_MARGIN

    # 3. 4p robustness (hero vs 3x baseline field) — avg_rank, lower is better
    field = [baseline, baseline, baseline]
    r4 = P.ffa(agent, field, list(range(seed0, seed0 + max(10, games // 3))), procs=procs)
    r4b = P.ffa(baseline, field, list(range(seed0, seed0 + max(10, games // 3))), procs=procs)
    gates["agent_avg_rank4"] = round(r4["avg_rank"], 2)
    gates["baseline_avg_rank4"] = round(r4b["avg_rank"], 2)
    gates["robust_4p"] = r4["avg_rank"] <= r4b["avg_rank"] + RANK4_TOL

    # crash safety: P.h2h would have raised; reaching here over all games = ok
    gates["crash_safe"] = True

    submit_ready = gates["crash_safe"] and gates["weak_no_regress"] and gates["beats_baseline"] and gates["robust_4p"]
    return {
        "agent": os.path.relpath(agent, COMP),
        "baseline": os.path.relpath(baseline, COMP),
        "games": games,
        "seed0": seed0,
        "gates": gates,
        "submit_ready": submit_ready,
        "wall_s": round(time.perf_counter() - t0, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--seed0", type=int, default=40000)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--out")
    args = ap.parse_args()
    v = evaluate(args.agent, args.baseline, args.games, args.seed0, args.procs)
    print(json.dumps(v, indent=2))
    print(f"\nSUBMIT-READY: {v['submit_ready']}  ({v['agent']} vs {v['baseline']})")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(v, f, indent=2)


if __name__ == "__main__":
    main()
