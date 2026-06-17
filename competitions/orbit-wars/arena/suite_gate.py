"""Diverse-opponent gate: evaluate an agent vs a fixed suite of public agents spanning
the strength range, so offline win-rate tracks the ladder (self-play does not).

Usage:
    python competitions/orbit-wars/arena/suite_gate.py <agent>           # one agent vs suite
    python competitions/orbit-wars/arena/suite_gate.py --all             # our agents + kuni05
    python competitions/orbit-wars/arena/suite_gate.py <agent> --games 20
"""

import argparse
import os

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))

# (label, resolved opponent) — ordered weak -> strong by observed strength.
SUITE = [
    ("random", "random"),
    ("starter", "starter"),
    ("adilshamim", f"{V}/suite/adilshamim.py"),
    ("pub_tactical", f"{V}/pub_tactical.py"),
    ("evogen1093", f"{V}/suite/evogen1093.py"),
    ("multifocus", f"{V}/suite/multifocus.py"),
    ("kuni05~1240", f"{V}/kuni05/main.py"),
]

AGENTS = {
    "v2.1": f"{V}/v2_1.py",
    "v3": f"{V}/v3.py",
    "v3.1": f"{V}/v3_1.py",
    "main": MAIN,
    "kuni05": f"{V}/kuni05/main.py",
    "evogen1093": f"{V}/suite/evogen1093.py",
}


def resolve(name):
    return AGENTS.get(name, name)


def eval_vs_suite(label, agent, seeds, procs):
    print(f"\n=== {label} vs suite ({len(seeds)} seeds x2 each) ===")
    tot_w = tot_n = 0
    for opp_label, opp in SUITE:
        if os.path.abspath(opp) == os.path.abspath(agent):
            continue  # skip self
        r = P.h2h(agent, opp, seeds, procs=procs)
        tot_w += r["w"]
        tot_n += r["n"]
        print(f"  vs {opp_label:14s}: {r['winpct']:5.1f}%  ({r['w']:>3}-{r['l']:>3}-{r['t']})")
    print(f"  >> SUITE AVERAGE: {100.0 * tot_w / tot_n:5.1f}%  ({tot_w}/{tot_n})")
    return 100.0 * tot_w / tot_n if tot_n else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", nargs="?", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--procs", type=int, default=None)
    args = ap.parse_args()
    seeds = list(range(7000, 7000 + args.games))  # held out from all prior tuning
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    if args.all:
        for label in ("v2.1", "v3", "v3.1", "kuni05"):
            eval_vs_suite(label, resolve(label), seeds, procs)
    elif args.agent:
        eval_vs_suite(args.agent, resolve(args.agent), seeds, procs)
    else:
        eval_vs_suite("main", MAIN, seeds, procs)


if __name__ == "__main__":
    main()
