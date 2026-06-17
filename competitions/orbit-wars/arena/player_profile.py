"""Batch behavioral profiler for ladder players (issue #87 — tech-route &
strategy inference for top contenders).

For each requested player, samples their episodes (wins AND losses) from the
public dataset and aggregates the behavioral metrics used in EPISODES.md
analysis #1, plus signals that help infer the implementation route:

  rule engine vs learned model vs hybrid (heuristic signals, NOT proof):
    * size_entropy   — rule engines emit exact computed sizes (defender+buf):
                       high spread, weak clustering; fraction-policies cluster
                       at round ratios of source garrison;
    * frac_modes     — share of launches at 25/50/75/90%+ of source garrison;
    * reaction_lag   — turns between an enemy launch targeting our planet and
                       our first reinforcement of it (rule engines react the
                       same tick they see the threat; models can be sloppier);
    * tempo_regular  — std of gaps between launch turns (scripted cadence vs
                       event-driven bursts).

Usage:
    python arena/player_profile.py --data <episodes_dir> --index <csv> \
        --players "Isaiah @ Tufa Labs,Hober Malloc" --per-player 40 \
        --out profiles.json --procs 6
"""

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from multiprocessing import Pool

from distill_prep import _decode_target


def _profile_episode(args):
    path, seat, player_name = args
    try:
        d = json.load(open(path))
    except Exception:
        return None
    steps = d.get("steps", [])
    if not steps:
        return None
    rewards = [s.get("reward") for s in steps[-1]]
    won = rewards[seat] is not None and rewards[seat] == max(r for r in rewards if r is not None)
    m = {
        "player": player_name,
        "won": bool(won),
        "steps": len(steps),
        "launches": 0,
        "attacks": 0,
        "reinforce": 0,
        "neutral": 0,
        "atk_ships": [],
        "rein_dist": [],
        "frac_of_src": [],
        "launch_turns": [],
        "opening25": 0,
        "coarrival": 0,
        "react_lags": [],
    }
    arrivals = defaultdict(list)
    threat_seen = {}  # planet id -> turn we first saw an enemy fleet inbound
    for t, st in enumerate(steps):
        obs0 = st[0].get("observation") or {}
        planets = {p[0]: p for p in (obs0.get("planets") or [])}
        fleets = obs0.get("fleets") or []
        obs = dict(obs0)
        obs["player"] = seat
        # track first-threat times for reaction-lag measurement
        for f in fleets:
            if f[1] == seat:
                continue
            for pid, p in planets.items():
                if p[1] != seat:
                    continue
                hx, hy = math.cos(f[4]), math.sin(f[4])
                rx, ry = p[2] - f[2], p[3] - f[3]
                if rx * hx + ry * hy > 0 and abs(rx * (-hy) + ry * hx) < p[4] + 2.0:
                    threat_seen.setdefault(pid, t)
        for mv in st[seat].get("action") or []:
            try:
                src, _ang, n = int(mv[0]), float(mv[1]), int(mv[2])
            except Exception:
                continue
            m["launches"] += 1
            m["launch_turns"].append(t)
            if t <= 25:
                m["opening25"] += 1
            srow = planets.get(src)
            if srow and srow[5] > 0:
                m["frac_of_src"].append(min(2.0, n / srow[5]))
            try:
                dec = _decode_target(mv, obs)
            except Exception:
                dec = None
            if not dec:
                continue
            tgt, eta = dec
            trow = planets.get(tgt)
            town = trow[1] if trow else None
            if town == seat:
                m["reinforce"] += 1
                if srow and trow:
                    m["rein_dist"].append(math.hypot(srow[2] - trow[2], srow[3] - trow[3]))
                if tgt in threat_seen:
                    m["react_lags"].append(t - threat_seen.pop(tgt))
            elif town == -1:
                m["neutral"] += 1
            else:
                m["attacks"] += 1
                m["atk_ships"].append(n)
            arrivals[(tgt, t + eta)].append(src)
    m["coarrival"] = sum(1 for v in arrivals.values() if len(set(v)) >= 2)
    return m


def _agg(metrics):
    """Aggregate per-episode metrics into one player profile dict."""
    n = len(metrics)
    if not n:
        return {}
    wins = [m for m in metrics if m["won"]]

    def avg(key, sub=None):
        pool_ = sub if sub is not None else metrics
        vals = [v for m in pool_ for v in (m[key] if isinstance(m[key], list) else [m[key]])]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    atk = [v for m in metrics for v in m["atk_ships"]]
    fr = [v for m in metrics for v in m["frac_of_src"]]
    gaps = []
    for m in metrics:
        ts = sorted(set(m["launch_turns"]))
        gaps += [b - a for a, b in zip(ts, ts[1:])]
    frac_modes = round(sum(1 for v in fr if v >= 0.85) / len(fr), 2) if fr else 0.0
    return {
        "episodes": n,
        "win_rate": round(len(wins) / n, 2),
        "avg_game_len": avg("steps"),
        "launches_per_game": avg("launches"),
        "opening25": avg("opening25"),
        "mix_attack": round(
            sum(m["attacks"] for m in metrics) / max(1, sum(m["launches"] for m in metrics)),
            2,
        ),
        "mix_reinforce": round(
            sum(m["reinforce"] for m in metrics) / max(1, sum(m["launches"] for m in metrics)),
            2,
        ),
        "mix_neutral": round(
            sum(m["neutral"] for m in metrics) / max(1, sum(m["launches"] for m in metrics)),
            2,
        ),
        "atk_size_mean": round(sum(atk) / len(atk), 1) if atk else 0,
        "atk_size_p90": sorted(atk)[int(0.9 * len(atk))] if atk else 0,
        "rein_hop_dist": avg("rein_dist"),
        "coarrival_per_game": avg("coarrival"),
        "frac_full_drain": frac_modes,  # share of launches >=85% of source
        "tempo_gap_mean": round(sum(gaps) / len(gaps), 2) if gaps else 0,
        "react_lag_mean": avg("react_lags"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--players", required=True)
    ap.add_argument("--per-player", type=int, default=40)
    ap.add_argument("--out", default="profiles.json")
    ap.add_argument("--procs", type=int, default=6)
    args = ap.parse_args()
    players = [p.strip() for p in args.players.split(",") if p.strip()]

    rows = list(csv.DictReader(open(args.index)))
    tasks = []
    for name in players:
        eps = [r for r in rows if name in (r["p0"], r["p1"])]
        eps = eps[: args.per_player]
        for r in eps:
            seat = 0 if r["p0"] == name else 1
            path = os.path.join(args.data, r["episode"] + ".json")
            if os.path.exists(path):
                tasks.append((path, seat, name))
    print(f"profiling {len(players)} players over {len(tasks)} episodes", flush=True)

    by_player = defaultdict(list)
    with Pool(args.procs) as pool:
        for m in pool.imap_unordered(_profile_episode, tasks):
            if m:
                by_player[m["player"]].append(m)

    profiles = {name: _agg(ms) for name, ms in by_player.items()}
    with open(args.out, "w") as f:
        json.dump(profiles, f, indent=1, ensure_ascii=False)
    for name in players:
        print(f"\n=== {name} ===")
        print(json.dumps(profiles.get(name, {}), indent=1))


if __name__ == "__main__":
    main()
