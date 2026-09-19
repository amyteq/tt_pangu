"""Build the episode index over a replay corpus (stdlib only; no raw JSON committed).

Walks --replay-root for *.json replays, parses metadata (episode id, players, seed, team
names, rewards, winner), and writes episodes.jsonl + episodes.csv to --out-root.

  python build_episode_index.py --replay-root <dir> --out-root <dir> [--top-players a,b,c]

Full corpus runs on snorlax (see datasets/README.md); here it runs on a small fixture dir.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from _replay import iter_replays, parse_meta

FIELDS = [
    "episode_id",
    "source_path",
    "player_count",
    "seed",
    "module_version",
    "team_names",
    "rewards",
    "winner_seat",
    "winner_name",
    "num_steps",
    "top_player_flag",
]


def build(replay_root, out_root, top_players=None):
    os.makedirs(out_root, exist_ok=True)
    top = set(top_players or [])
    rows, malformed = [], 0
    for path, replay in iter_replays(replay_root):
        meta = parse_meta(path, replay)
        if meta.get("malformed"):
            malformed += 1
            continue
        names = meta.get("team_names") or []
        meta["top_player_flag"] = bool(top and any(n in top for n in names))
        rows.append(meta)
    jl = os.path.join(out_root, "episodes.jsonl")
    with open(jl, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    cv = os.path.join(out_root, "episodes.csv")
    with open(cv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(r.get(k)) if isinstance(r.get(k), (list, dict)) else r.get(k)) for k in FIELDS})
    summary = {
        "replays_seen": len(rows) + malformed,
        "indexed": len(rows),
        "malformed": malformed,
        "p2": sum(1 for r in rows if r["player_count"] == 2),
        "p4": sum(1 for r in rows if r["player_count"] == 4),
        "top_player_episodes": sum(1 for r in rows if r["top_player_flag"]),
        "total_steps": sum(r["num_steps"] for r in rows),
    }
    with open(os.path.join(out_root, "episode_index_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    ap = argparse.ArgumentParser(description="Build Orbit Wars episode index from a replay corpus.")
    ap.add_argument(
        "--replay-root",
        required=True,
        help="dir of *.json replays (small fixture here; 20G corpus on snorlax)",
    )
    ap.add_argument(
        "--out-root",
        required=True,
        help="output dir for episodes.{jsonl,csv} + summary",
    )
    ap.add_argument(
        "--top-players",
        default="",
        help="comma-separated team names to flag as top players",
    )
    args = ap.parse_args()
    top = [s.strip() for s in args.top_players.split(",") if s.strip()]
    s = build(args.replay_root, args.out_root, top)
    print("episode index:", json.dumps(s))


if __name__ == "__main__":
    main()
