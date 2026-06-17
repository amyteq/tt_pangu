"""Discover a STRONG-TIER teacher corpus by walking the ladder graph (read-only Kaggle API).

Our own submissions sit at μ~1077 — too weak a teacher (prompt-06 hybrid: AUC 0.88 offline, flat on
the ladder; the gap is strategy, not ranking). To imitate strong play we need episodes where a
STRONG seat (μ ≥ --strong-mu) actually played. The public ListEpisodes endpoint returns, per episode,
every agent's submissionId + μ in SEAT ORDER (verified vs replay rewards on 310 eps), so:

  1. BFS the ladder graph from seed submissions: each episode reveals opponents + their μ; any
     submission seen at μ ≥ strong-mu is enqueued, so we hop from our games -> strong opponents ->
     their strong-vs-strong games.
  2. Emit a manifest of TEACHER episodes: episode_id -> the seat indices whose μ ≥ teacher-mu (the
     seats whose launches are worth imitating), with each teacher's μ / reward / win flag / size.

No replays are downloaded here (that is ops/episode_fetch). No Kaggle writes. Output:
  datasets/strong_corpus/manifest.json   (episode_id -> {size, teacher_seats:[...]})
  datasets/strong_corpus/episode_ids.txt (one id per line, winners-first, for fetching)

  python ops/discover_strong_corpus.py --seed-subs 53582503 53730511 --strong-mu 1200 --max-subs 150
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import episode_discover as ed  # noqa: E402

OUT_DIR = os.path.join(COMP, "datasets", "strong_corpus")


def _mu(a):
    return a.get("updatedScore") or a.get("initialScore") or 0.0


def discover(seed_subs, strong_mu, teacher_mu, max_subs):
    visited = set()
    frontier = deque(seed_subs)
    queued = set(seed_subs)
    episodes = {}  # episode_id -> agents list (seat order)
    strong_subs = set()
    calls = 0
    while frontier and calls < max_subs:
        sub = frontier.popleft()
        visited.add(sub)
        try:
            eps = ed.list_episodes(sub)
        except Exception as e:  # noqa: BLE001 - network best-effort
            print(f"  list_episodes({sub}) failed: {type(e).__name__}: {e}")
            continue
        calls += 1
        for e in eps:
            episodes[e["id"]] = e.get("agents", [])
            for a in e.get("agents", []):
                sid = a.get("submissionId")
                if sid is None:
                    continue
                if _mu(a) >= strong_mu:
                    strong_subs.add(sid)
                    if sid not in visited and sid not in queued:
                        frontier.append(sid)
                        queued.add(sid)
        if calls % 10 == 0:
            print(
                f"  ... {calls} subs queried, {len(episodes)} episodes seen, "
                f"{len(strong_subs)} strong subs, frontier {len(frontier)}"
            )

    # teacher episodes: any episode with >=1 seat at mu >= teacher_mu
    manifest = {}
    for eid, agents in episodes.items():
        rewards = [a.get("reward") for a in agents]
        best = max((r for r in rewards if r is not None), default=None)
        seats = []
        for seat, a in enumerate(agents):
            if _mu(a) >= teacher_mu:
                seats.append(
                    {
                        "seat": seat,
                        "sub": a.get("submissionId"),
                        "mu": round(_mu(a), 1),
                        "reward": a.get("reward"),
                        "won": (a.get("reward") == best and best is not None),
                    }
                )
        if seats:
            manifest[eid] = {"size": len(agents), "teacher_seats": seats}
    return manifest, strong_subs, calls, len(episodes)


def main():
    ap = argparse.ArgumentParser(description="Discover a strong-tier teacher corpus manifest.")
    ap.add_argument("--seed-subs", type=int, nargs="+", default=[53582503, 53730511])
    ap.add_argument(
        "--strong-mu",
        type=float,
        default=1200.0,
        help="μ to count a sub as strong (BFS expansion)",
    )
    ap.add_argument(
        "--teacher-mu",
        type=float,
        default=1200.0,
        help="μ for a seat to be a teacher (labeling)",
    )
    ap.add_argument(
        "--max-subs",
        type=int,
        default=150,
        help="cap on ListEpisodes calls (API budget)",
    )
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    manifest, strong_subs, calls, n_eps = discover(args.seed_subs, args.strong_mu, args.teacher_mu, args.max_subs)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # winners-first ordering for bounded fetching
    def _key(item):
        eid, m = item
        won = any(s["won"] for s in m["teacher_seats"])
        bestmu = max(s["mu"] for s in m["teacher_seats"])
        return (0 if won else 1, -bestmu)

    ordered = sorted(manifest.items(), key=_key)
    with open(os.path.join(args.out_dir, "episode_ids.txt"), "w") as f:
        for eid, _m in ordered:
            f.write(f"{eid}\n")

    twop = sum(1 for m in manifest.values() if m["size"] == 2)
    fourp = sum(1 for m in manifest.values() if m["size"] == 4)
    won_eps = sum(1 for m in manifest.values() if any(s["won"] for s in m["teacher_seats"]))
    print(
        f"\nBFS: {calls} subs queried, {n_eps} episodes seen, {len(strong_subs)} strong subs (μ≥{args.strong_mu:.0f})"
    )
    print(
        f"teacher episodes (≥1 seat μ≥{args.teacher_mu:.0f}): {len(manifest)} ({twop} 2p, {fourp} 4p; {won_eps} have a winning teacher seat)"
    )
    print(f"manifest -> {os.path.relpath(os.path.join(args.out_dir, 'manifest.json'), COMP)}")
    print(f"episode ids -> {os.path.relpath(os.path.join(args.out_dir, 'episode_ids.txt'), COMP)}")


if __name__ == "__main__":
    main()
