"""Generate LOCAL self/cross-play episodes as kaggle_environments replays (no Kaggle, no network).

Purpose: a reproducible multi-episode corpus for the prompt-05 *plumbing* cycle when no ladder
replays are cached. The "teacher" here is whichever local agent played the seat — so imitation
metrics describe imitation-of-LOCAL-agent, NOT ladder teachers. The real ladder-teacher corpus
comes from `ops/episode_fetch.py` + snorlax (see datasets/README.md, models/README.md). We pick the
STRONGEST locally available agents as teachers (kuni05 ~1240 / evogen ~1093) so the signal is at
least competent play.

Writes one replay JSON per episode to --out, with a synthetic info.EpisodeId (so episode-split
works). Deterministic: episodes are fixed (agents, seed) pairs.

  python gen_local_episodes.py --out datasets/cache/replays [--seeds 7000 7001 7002] [--two-only]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# strongest locally-available teachers live in the MAIN checkout (suite/ + kuni05/ are gitignored
# in worktrees). Fall back to in-worktree versions if the main checkout is absent.
HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
MAIN_COMP = "/home/harry/test/tt_pangu/competitions/orbit-wars"


def _agent(rel):
    for base in (MAIN_COMP, COMP):
        p = os.path.join(base, "agent", "versions", rel)
        if os.path.exists(p):
            return p
    return None


def _runnable(*paths):
    return [p for p in paths if p]


def main():
    ap = argparse.ArgumentParser(description="Generate local Orbit Wars replays for the plumbing cycle.")
    ap.add_argument("--out", default=os.path.join(COMP, "datasets", "cache", "replays"))
    ap.add_argument("--seeds", type=int, nargs="+", default=[7000, 7001, 7002])
    ap.add_argument("--two-only", action="store_true", help="skip the 4p episodes")
    args = ap.parse_args()

    os.environ["OMP_NUM_THREADS"] = "1"  # B8: torch opponents spin OMP threads
    import logging

    logging.disable(logging.INFO)
    from kaggle_environments import make

    kuni = _agent("kuni05/main.py")
    evogen = _agent("suite/evogen1093.py")
    v4 = _agent("v4.py")
    v32 = _agent("v3_2.py")
    pub = _agent("pub_tactical.py")
    # ensure package-based agents (kuni05 imports orbit_lite from its own dir) import
    for a in _runnable(kuni, evogen, v4, v32, pub):
        d = os.path.dirname(os.path.abspath(a))
        if d not in sys.path:
            sys.path.insert(0, d)

    # 2p pairings: prefer strong-vs-strong; fall back to whatever exists
    pool2 = _runnable(kuni, evogen, v4, v32, pub)
    if len(pool2) < 2:
        print(json.dumps({"blocker": "need >=2 local agents; none found in main checkout or worktree"}))
        return
    pairings = []
    for i in range(len(pool2)):
        for j in range(i + 1, len(pool2)):
            pairings.append((pool2[i], pool2[j]))
    pairings = pairings[:4]  # cap to keep the cycle bounded
    quad = _runnable(kuni, evogen, v4, v32)[:4]

    os.makedirs(args.out, exist_ok=True)
    written = []
    for seed in args.seeds:
        for p0, p1 in pairings:
            tag = f"{_name(p0)}-{_name(p1)}"
            eid = f"local2-{tag}-{seed}"
            path = os.path.join(args.out, eid + ".json")
            if os.path.exists(path):
                written.append(eid)
                continue
            env = make("orbit_wars", configuration={"seed": seed})
            env.run([p0, p1])
            _dump(env, eid, path)
            written.append(eid)
        if not args.two_only and len(quad) == 4:
            eid = f"local4-{seed}"
            path = os.path.join(args.out, eid + ".json")
            if not os.path.exists(path):
                env = make("orbit_wars", configuration={"seed": seed})
                env.run(list(quad))
                _dump(env, eid, path)
            written.append(eid)
    print(json.dumps({"out": args.out, "episodes": len(written), "ids": written}, indent=2))


def _name(path):
    b = os.path.basename(os.path.dirname(path)) if path.endswith("main.py") else os.path.basename(path)
    return os.path.splitext(b)[0].replace("_", "")


def _dump(env, eid, path):
    rep = env.toJSON()
    info = rep.setdefault("info", {})
    info["EpisodeId"] = eid
    info.setdefault("TeamNames", [f"seat{i}" for i in range(len(env.steps[-1]))])
    with open(path, "w") as f:
        json.dump(rep, f)


if __name__ == "__main__":
    main()
