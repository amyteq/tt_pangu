"""Per-submission episode tracker (orbit5 loop, 2026-06-16).

One bounded cycle (`--once`): pull the match history for a submission via
ListEpisodes, pick the next UNPROCESSED episode (oldest first), download its
replay (one episode / cycle — the loop paces this at ~4 min), analyze + tag it
(sun-collision / hard-bug / winner-reason via episode_analyze), append a row to
live/track_<sub>.csv, and print a running μ/W-L summary + a keep/replace
recommendation once >= --decide-after episodes are processed.

Identity note: episode_analyze matches OUR seat by PROFILE name (e.g. flyingfox
= harrysun2006), not account name — this tool auto-detects the profile from the
replay by reward-matching the tracked submission, so it works regardless.

Usage:
    python ops/track_submission.py --once --submission-id 53730511
    python ops/track_submission.py --once --submission-id 53730511 --decide-after 10 --max 20
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import episode_analyze as ea
import episode_discover as ed
import episode_fetch as ef

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
LIVE = os.path.join(COMP, "live")
REPLAYS = os.path.join(COMP, "replays")

FIELDS = [
    "ep",
    "size",
    "place",
    "result",
    "our_mu0",
    "our_mu1",
    "d_mu",
    "profile",
    "tag",
    "sun_collision",
    "hard_bug",
    "winner_reason",
    "followup",
]


def _track_path(sub: int) -> str:
    return os.path.join(LIVE, f"track_{sub}.csv")


def _load(sub: int) -> list[dict]:
    p = _track_path(sub)
    if not os.path.exists(p):
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _append(sub: int, row: dict) -> None:
    p = _track_path(sub)
    new = not os.path.exists(p)
    os.makedirs(LIVE, exist_ok=True)
    with open(p, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def _our_seat_and_profile(replay: dict, our_reward) -> tuple[int | None, str]:
    """Find our seat by matching the ListEpisodes reward against the replay's
    seat-ordered rewards; profile = info.TeamNames[seat]."""
    rewards = replay.get("rewards") or []
    names = (replay.get("info") or {}).get("TeamNames") or []
    seats = [i for i, r in enumerate(rewards) if r == our_reward]
    seat = seats[0] if len(seats) == 1 else (seats[0] if seats else None)
    profile = names[seat] if (seat is not None and seat < len(names)) else "?"
    return seat, profile


def _recommend(rows: list[dict], decide_after: int) -> str:
    n = len(rows)
    if n < decide_after:
        return f"ACCUMULATING ({n}/{decide_after} episodes; need more before a call)"
    mus0 = [float(r["our_mu0"]) for r in rows if r.get("our_mu0")]
    mus1 = [float(r["our_mu1"]) for r in rows if r.get("our_mu1")]
    if not mus0 or not mus1:
        return f"n={n} but μ data incomplete"
    first, last = mus0[0], mus1[-1]
    twop = [r for r in rows if r["size"] == "2"]
    wins = sum(1 for r in twop if r["result"] == "win")
    bugs = sum(1 for r in rows if r.get("hard_bug") not in ("", "NO", "no"))
    trend = last - first
    base = f"n={n} | μ {first:.0f}→{last:.0f} (Δ{trend:+.0f}) | 2p {wins}W-{len(twop) - wins}L | hard-bugs {bugs}"
    if bugs:
        return base + " | ⚠ HARD BUG present → REVIEW before keeping the slot"
    if last >= 1150 and trend > 0:
        return base + " | KEEP: climbing toward the >1200 keep-a-slot bar"
    if trend <= -40 or last < first - 40:
        return base + " | EARLY-STOP/REPLACE: μ trending down, won't reach 1200"
    return (
        base + " | FLAT in our ~640–760 band: won't reach 1200 → replace per policy "
        "OR keep as own-agent slot and focus the main branch (human call)"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission-id", type=int, required=True)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--decide-after", type=int, default=10)
    ap.add_argument("--max", type=int, default=20)
    args = ap.parse_args()
    sub = args.submission_id

    done = _load(sub)
    done_ids = {r["ep"] for r in done}
    if len(done) >= args.max:
        print(f"track {sub}: reached --max {args.max} processed episodes.")
        print("  RECOMMENDATION:", _recommend(done, args.decide_after))
        return

    eps = ed.list_episodes(sub)
    # oldest first (smallest id) so we judge the submission's first games
    eps_sorted = sorted(eps, key=lambda e: e["id"])
    nxt = next((e for e in eps_sorted if str(e["id"]) not in done_ids), None)
    if nxt is None:
        print(
            f"track {sub}: no new episode yet ({len(done)} processed; "
            f"{len(eps)} total). Waiting for the ladder to schedule more."
        )
        print("  RECOMMENDATION:", _recommend(done, args.decide_after))
        return

    ep = nxt["id"]
    ags = nxt.get("agents", [])
    me = next((a for a in ags if a.get("submissionId") == sub), None)
    our_reward = me.get("reward") if me else None
    mu0 = me.get("initialScore") if me else None
    mu1 = me.get("updatedScore") if me else None
    size = len(ags)
    rs = sorted((a.get("reward", 0) or 0 for a in ags), reverse=True)
    place = 1 + rs.index(our_reward or 0) if me else 0
    result = "win" if place == 1 else ("loss" if size == 2 else f"p{place}")

    print(f"track {sub}: cycle on episode {ep} (size {size}, place {place}, {result})")
    path = ef.fetch(str(ep))
    tag = sun = hard = reason = followup = ""
    profile = "?"
    if path and os.path.exists(path):
        try:
            replay = json.load(open(path))
            seat, profile = _our_seat_and_profile(replay, our_reward)
            rows = ea.analyze(path, {profile}) if profile != "?" else []
            mine = next((r for r in rows if str(r.get("our_seat")) == str(seat)), None) or (rows[0] if rows else None)
            if mine:
                tag = mine.get("interesting", "")
                sun = mine.get("sun_collision", "")
                hard = mine.get("hard_bug", "")
                reason = mine.get("winner_reason", "")
                followup = mine.get("followup", "")
        except Exception as e:  # never let one bad replay kill the loop
            tag = f"analyze-error:{type(e).__name__}"
    else:
        tag = "fetch-failed"

    row = {
        "ep": ep,
        "size": size,
        "place": place,
        "result": result,
        "our_mu0": round(mu0, 1) if mu0 else "",
        "our_mu1": round(mu1, 1) if mu1 else "",
        "d_mu": round((mu1 or 0) - (mu0 or 0), 1) if (mu0 and mu1) else "",
        "profile": profile,
        "tag": tag,
        "sun_collision": sun,
        "hard_bug": hard,
        "winner_reason": reason,
        "followup": followup,
    }
    _append(sub, row)
    allrows = _load(sub)
    print(
        f"  ep {ep}: {result} | μ {row['our_mu0']}→{row['our_mu1']} (Δ{row['d_mu']}) | "
        f"profile={profile} | tag={tag or 'clean'} | bug={hard or 'NO'}"
    )
    if followup:
        print(f"  FOLLOWUP: {followup}")
    print(
        f"  processed {len(allrows)}/{args.max}.  RECOMMENDATION:",
        _recommend(allrows, args.decide_after),
    )


if __name__ == "__main__":
    main()
