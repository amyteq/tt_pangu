"""T16 measurement step (issue #87): how much can sun/planet waypoint routing
buy? Instruments stock v3.2 (forecast_measure.py twin) to count value-positive
launches the main loop DROPS via _path_blocked, split by cause (sun vs planet)
and by whether a re-timed clear path exists, across opponent tiers.

Run: python arena/measure_t16.py --games 40
"""

import argparse
import json
import logging
import os
import statistics as st
import sys

logging.disable(logging.INFO)
os.environ["OW_PATHLOG"] = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
sys.path.insert(0, V)

import forecast_measure as FM  # noqa: E402
from kaggle_environments import make  # noqa: E402

STOCK = f"{V}/forecast.py"
OPPS = {
    "starter": "starter",
    "evogen": f"{V}/suite/evogen1093.py",
    "multifocus": f"{V}/suite/multifocus.py",
    "mirror": STOCK,
}


def _p0_actions(env):
    return [tuple(map(tuple, (s[0].get("action") or []))) for s in env.steps]


def identity_check(seeds):
    """forecast_measure (PATHLOG on) must emit the SAME P0 moves as stock
    forecast — logging is side-effect-only. Proves the twin doesn't drift."""
    mism = 0
    for sd in seeds:
        e1 = make("orbit_wars", configuration={"seed": sd})
        e1.run([FM.agent, "starter"])
        a1 = _p0_actions(e1)
        e2 = make("orbit_wars", configuration={"seed": sd})
        e2.run([STOCK, "starter"])
        a2 = _p0_actions(e2)
        if a1 != a2:
            mism += 1
            print(f"  MISMATCH seed {sd}: len {len(a1)} vs {len(a2)}")
    print(f"identity check: {len(seeds) - mism}/{len(seeds)} seeds identical")
    return mism == 0


def measure(seeds):
    FM._PLOG.clear()
    for opp_name, opp in OPPS.items():
        if not (opp == "starter" or os.path.exists(opp)):
            print(f"  (skip {opp_name}: missing)")
            continue
        for sd in seeds:
            FM._PLOG_TAG["opp"], FM._PLOG_TAG["seed"] = opp_name, sd
            env = make("orbit_wars", configuration={"seed": sd})
            env.run([FM.agent, opp])
    return list(FM._PLOG)


def analyze(plog, out):
    with open(out, "w") as f:
        for r in plog:
            f.write(json.dumps(r) + "\n")
    # group by game
    games = {}
    for r in plog:
        games.setdefault((r["opp"], r["seed"]), []).append(r)

    by_opp = {}
    for (opp, _sd), turns in games.items():
        d = by_opp.setdefault(
            opp,
            {
                "games": 0,
                "turns": 0,
                "turns_with_drop": 0,
                "pos": 0,
                "pos_sun": 0,
                "pos_planet": 0,
                "pos_uncommitted": 0,
                "pos_unc_retime": 0,
                "best_unc_retime_val": [],
                "drop_pos_val": [],
                "top_cand_val": [],
            },
        )
        d["games"] += 1
        for t in turns:
            d["turns"] += 1
            committed = set(t["committed"])
            if t.get("top_cand", 0) > 0:
                d["top_cand_val"].append(t["top_cand"])
            drops = [b for b in t["blocked"] if b["value"] > 0]
            if drops:
                d["turns_with_drop"] += 1
            best_unc_rt = 0.0
            for b in drops:
                d["pos"] += 1
                d["drop_pos_val"].append(b["value"])
                if b["cause"] == "sun":
                    d["pos_sun"] += 1
                else:
                    d["pos_planet"] += 1
                if b["tgt"] not in committed:
                    d["pos_uncommitted"] += 1
                    if b["retime_useful"]:
                        d["pos_unc_retime"] += 1
                        best_unc_rt = max(best_unc_rt, b["value"])
            if best_unc_rt > 0:
                d["best_unc_retime_val"].append(best_unc_rt)

    print(
        f"\n{'opp':11s} {'games':>5} {'turns':>6} | "
        f"{'drop+/g':>7} {'sun/pl':>9} {'uncomm/g':>8} {'retime/g':>8} | "
        f"{'medDropV':>8} {'medTopV':>8} {'sumRetimeV/g':>12}"
    )
    for opp, d in by_opp.items():
        g = max(1, d["games"])

        def med(x):
            return round(st.median(x), 1) if x else 0.0

        print(
            f"{opp:11s} {d['games']:>5} {d['turns']:>6} | "
            f"{d['pos'] / g:>7.2f} {d['pos_sun']}/{d['pos_planet']:>5} "
            f"{d['pos_uncommitted'] / g:>8.2f} {d['pos_unc_retime'] / g:>8.2f} | "
            f"{med(d['drop_pos_val']):>8} {med(d['top_cand_val']):>8} "
            f"{sum(d['best_unc_retime_val']) / g:>12.1f}"
        )
    print(
        "\nLegend: drop+/g = value-positive launches dropped by _path_blocked per game; "
        "sun/pl = of those, sun-block vs planet-block count; uncomm/g = value-positive "
        "drops whose target was NOT captured anyway, per game; retime/g = subset that a "
        "re-aimed (different arrival turn) clear path COULD reach (T16 upper bound), per "
        "game; medDropV/medTopV = median dropped-positive value vs median best committed "
        "launch value (scale); sumRetimeV/g = sum of per-turn best recoverable value per game."
    )
    return by_opp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--seed0", type=int, default=26000)
    ap.add_argument("--out", default="/tmp/claude/t16_pathlog.jsonl")
    args = ap.parse_args()
    seeds = list(range(args.seed0, args.seed0 + args.games))

    print("=== T16 identity check (8 seeds) ===")
    ok = identity_check(list(range(args.seed0, args.seed0 + 8)))
    if not ok:
        print("ABORT: instrumented twin diverges from stock v3.2 — measurement invalid.")
        sys.exit(1)
    print(f"\n=== T16 measurement ({args.games} seeds x {len(OPPS)} opps) ===")
    plog = measure(seeds)
    analyze(plog, args.out)
    print(f"\nraw per-turn log -> {args.out} ({len(plog)} turns)")


if __name__ == "__main__":
    main()
