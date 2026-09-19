"""Per-step, per-player aggregates over a replay corpus, reusing core.state.PlayerState.

  python build_step_table.py --replay-root <dir> --out-root <dir> [--step-stride 5]

Output: <out-root>/step_table.csv (one row per (episode, step, player)).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from _replay import iter_replays, parse_meta, board_at  # noqa: E402
from core.state import build_battlefield_state  # noqa: E402

FIELDS = [
    "episode_id",
    "step",
    "player_id",
    "phase",
    "planets_owned",
    "production_total",
    "ships_on_planets",
    "ships_in_flight",
    "score_estimate",
    "leader_gap",
]


def build(replay_root, out_root, stride=5, horizon=40, max_steps=None):
    os.makedirs(out_root, exist_ok=True)
    out = os.path.join(out_root, "step_table.csv")
    n = 0
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for path, replay in iter_replays(replay_root):
            meta = parse_meta(path, replay)
            if meta.get("malformed"):
                continue
            ns = meta["num_steps"]
            steps = range(0, ns if max_steps is None else min(ns, max_steps), stride)
            for t in steps:
                board = board_at(replay, t, seat=0)
                if board is None:
                    continue
                try:
                    st = build_battlefield_state(board, horizon=horizon)
                except Exception:
                    continue
                for pid, ps in st.players.items():
                    if pid == -1:
                        continue
                    w.writerow(
                        {
                            "episode_id": meta["episode_id"],
                            "step": t,
                            "player_id": pid,
                            "phase": st.glob.phase,
                            "planets_owned": ps.planet_count,
                            "production_total": ps.production_total,
                            "ships_on_planets": round(ps.ships_on_planets, 1),
                            "ships_in_flight": round(ps.ships_in_flight, 1),
                            "score_estimate": round(ps.score_now, 1),
                            "leader_gap": round(ps.leader_gap, 1),
                        }
                    )
                    n += 1
    print(f"step_table: {n} rows -> {out}")
    return n


def main():
    ap = argparse.ArgumentParser(description="Build per-step per-player table from replays.")
    ap.add_argument("--replay-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--step-stride", type=int, default=5)
    ap.add_argument("--horizon", type=int, default=40)
    ap.add_argument("--max-steps", type=int, default=None)
    args = ap.parse_args()
    build(args.replay_root, args.out_root, args.step_stride, args.horizon, args.max_steps)


if __name__ == "__main__":
    main()
