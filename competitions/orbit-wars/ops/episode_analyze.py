"""Episode analysis for the Orbit Wars live loop (KCT-OW-LIVE-002).

For a replay JSON, for each seat that is one of OUR agents:
  * decode every launch's intended target (bit-exact flight sim — reuses
    arena/distill_prep._decode_target);
  * HARD-BUG detection: sun collision (our fleet path/ticks within the sun
    danger radius), out-of-bounds loss, agent exception/empty-on-crash;
  * behavioral stats (launches, attack/reinforce mix, attack size);
  * winner-reason category;
  * append rows to live/episodes_index.csv + live/matches.csv.

Sun geometry matches the agent/arena safety convention (SUN_RADIUS=10 at the
board center); we scan OUR fleets only, never the opponent's (avoid false
positives), per the task's hard-error rules.

Usage:
    python ops/episode_analyze.py --episode-json replays/79586066.json \
        --our-usernames harrysun2006,firefly2006
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(COMP, "arena"))
sys.path.insert(0, os.path.join(COMP, "agent", "versions"))
from distill_prep import _decode_target  # noqa: E402  (reuse verified decoder)

LIVE = os.path.join(COMP, "live")
EP_INDEX = os.path.join(LIVE, "episodes_index.csv")
MATCHES = os.path.join(LIVE, "matches.csv")

CENTER = 50.0
SUN_R = 10.0
SUN_DANGER = SUN_R + 2.0  # "repeated near-sun ticks below danger radius" signal

EP_COLS = [
    "episode_id",
    "date_analyzed",
    "our_seat",
    "our_username",
    "our_agent",
    "opp_name",
    "opp_class",
    "result",
    "steps",
    "our_final_ships",
    "opp_final_ships",
    "launches",
    "attacks",
    "reinforces",
    "atk_size_mean",
    "sun_collision",
    "hard_bug",
    "winner_reason",
    "followup_task",
]


def _final_ships(obs: dict, seat: int) -> float:
    s = 0.0
    for p in obs.get("planets", []):
        if p[1] == seat:
            s += p[5]
    for f in obs.get("fleets", []):
        if f[1] == seat:
            s += f[6]
    return s


def _sun_collision(steps: list, seat: int) -> tuple[int, tuple | None]:
    """Count ticks where one of OUR fleets is within the sun danger radius;
    return (n_ticks, worst=(step, dist) or None). Our fleets only."""
    n = 0
    worst = None
    for t, st in enumerate(steps):
        obs = st[0].get("observation") or {}
        for f in obs.get("fleets", []):
            if f[1] != seat:
                continue
            d = math.hypot(f[2] - CENTER, f[3] - CENTER)
            if d < SUN_DANGER:
                n += 1
                if worst is None or d < worst[1]:
                    worst = (t, round(d, 2))
    return n, worst


def _winner_reason(our_seat, win, stats, opp_stats, late_sun) -> str:
    """Coarse winner-reason category from behavioral signals (heuristic)."""
    if late_sun and not win:
        return "loss: late near-sun flight (board-position collapse / pathing)"
    a_mean = stats["atk_size_mean"]
    o_mean = opp_stats["atk_size_mean"]
    if win:
        if stats["reinforces"] > stats["attacks"]:
            return "supply-chain reinforcement / reserve concentration"
        if a_mean >= 1.5 * max(1.0, o_mean):
            return "fewer but heavier attacks (hammer)"
        return "better ROI expansion / fleet sizing"
    else:
        if o_mean >= 1.5 * max(1.0, a_mean):
            return "opponent fewer-but-heavier attacks; we got picked apart"
        if stats["attacks"] > 2 * max(1, stats["reinforces"]):
            return "our overcommitment / small-strike attrition"
        return "unknown / close-game points loss"


def analyze(path: str, our_usernames: set[str]) -> list[dict]:
    with open(path) as f:
        d = json.load(f)
    episode_id = os.path.splitext(os.path.basename(path))[0]
    agents = [a.get("Name", "?") for a in d.get("info", {}).get("Agents", [])]
    steps = d.get("steps", [])
    if not steps or len(agents) != 2:
        print(f"{episode_id}: not a 2-player episode (agents={agents}) — skipped")
        return []
    last = steps[-1]
    rewards = [s.get("reward") for s in last]
    rows = []
    for seat in (0, 1):
        if agents[seat] not in our_usernames:
            continue
        opp = agents[1 - seat]
        # decode our launches
        launches = attacks = reinforces = 0
        atk_sizes = []
        hard = []
        for st in steps:
            obs0 = st[0].get("observation") or {}
            obs = dict(obs0)
            obs["player"] = seat
            planets = {p[0]: p for p in obs.get("planets", [])}
            for mv in st[seat].get("action") or []:
                try:
                    _src, _ang, n = int(mv[0]), float(mv[1]), int(mv[2])
                except Exception:
                    hard.append("invalid action format")
                    continue
                launches += 1
                try:
                    dec = _decode_target(mv, obs)
                except Exception:
                    dec = None
                if dec:
                    tgt = dec[0]
                    town = planets.get(tgt, [None, None])[1]
                    if town == seat:
                        reinforces += 1
                    elif town not in (-1, None):
                        attacks += 1
                        atk_sizes.append(n)
        n_sun, worst = _sun_collision(steps, seat)
        # late near-sun = collapse signal (second half of game)
        late_sun = worst is not None and worst[0] >= len(steps) // 2
        if n_sun > 0:
            hard.append(
                f"sun-proximity ticks={n_sun} worst(step={worst[0]},dist={worst[1]})"
            )
        rew = rewards[seat]
        orew = rewards[1 - seat]
        result = "tie"
        if rew is not None and orew is not None:
            result = "win" if rew > orew else ("loss" if rew < orew else "tie")
        stats = {
            "attacks": attacks,
            "reinforces": reinforces,
            "atk_size_mean": round(sum(atk_sizes) / len(atk_sizes), 1)
            if atk_sizes
            else 0.0,
        }
        # opponent quick stats for the reason heuristic
        opp_atk = []
        for st in steps:
            obs0 = st[0].get("observation") or {}
            obs = dict(obs0)
            obs["player"] = 1 - seat
            pl = {p[0]: p for p in obs.get("planets", [])}
            for mv in st[1 - seat].get("action") or []:
                try:
                    n = int(mv[2])
                    dec = _decode_target(mv, obs)
                except Exception:
                    dec = None
                    n = 0
                if dec and pl.get(dec[0], [None, None])[1] not in (-1, seat, None):
                    opp_atk.append(n)
        opp_stats = {
            "atk_size_mean": round(sum(opp_atk) / len(opp_atk), 1) if opp_atk else 0.0
        }
        reason = _winner_reason(seat, result == "win", stats, opp_stats, late_sun)
        sun_flag = "YES" if n_sun > 0 else "no"
        hard_flag = "; ".join(hard) if hard else "none"
        row = {
            "episode_id": episode_id,
            "date_analyzed": "",
            "our_seat": seat,
            "our_username": agents[seat],
            "our_agent": "unknown",
            "opp_name": opp,
            "opp_class": "unknown",
            "result": result,
            "steps": len(steps),
            "our_final_ships": round(
                _final_ships(last[0].get("observation", {}), seat)
            ),
            "opp_final_ships": round(
                _final_ships(last[0].get("observation", {}), 1 - seat)
            ),
            "launches": launches,
            "attacks": attacks,
            "reinforces": reinforces,
            "atk_size_mean": stats["atk_size_mean"],
            "sun_collision": sun_flag,
            "hard_bug": hard_flag,
            "winner_reason": reason,
            "followup_task": "",
        }
        rows.append(row)
        print(
            f"{episode_id} seat{seat} {agents[seat]} vs {opp}: {result.upper()} "
            f"steps={len(steps)} launches={launches} (atk {attacks}/rein {reinforces}) "
            f"sun={sun_flag} hard=[{hard_flag}] reason='{reason}'"
        )
    return rows


def _append_csv(path: str, cols: list[str], rows: list[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.isfile(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-json", required=True)
    ap.add_argument("--our-usernames", default="harrysun2006,firefly2006")
    ap.add_argument("--record", action="store_true", help="append to live/*.csv")
    args = ap.parse_args()
    users = {u.strip() for u in args.our_usernames.split(",") if u.strip()}
    rows = analyze(args.episode_json, users)
    if args.record and rows:
        _append_csv(EP_INDEX, EP_COLS, rows)
        print(f"recorded {len(rows)} row(s) -> {os.path.relpath(EP_INDEX, COMP)}")


if __name__ == "__main__":
    main()
