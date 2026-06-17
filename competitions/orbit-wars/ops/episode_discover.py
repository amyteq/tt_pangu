"""Episode discovery via Kaggle's ListEpisodes API (KCT-OW-LIVE-002 follow-up).

Earlier the loop assumed auto-discovery was unavailable and relied on a manual
queue. In fact the public endpoint
  POST https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes
  {"submissionId": <id>}
returns the FULL match history for a submission: per episode the agent ids,
rewards (W/L), placement, and initial/updated μ (so opponent strength + game
FORMAT (2p vs 4p) are available without downloading replays). This is how the
"ladder is ~half 4p" finding was made.

Given a submissionId, prints a 2p/4p-aware match summary and can append the
episode ids to live/pending_episodes.txt for episode_analyze to deep-dive.

Usage:
    python ops/episode_discover.py --submission-id 53582503
    python ops/episode_discover.py --submission-id 53582503 --queue --losses-only
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
PENDING = os.path.join(COMP, "live", "pending_episodes.txt")
API = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"


def list_episodes(submission_id: int, timeout: int = 60, retries: int = 5) -> list[dict]:
    """Read-only ListEpisodes with exponential backoff on HTTP 429 (public rate limit).

    The endpoint rate-limits bursts; the ladder loop / BFS discovery hit it, so back off
    (2,4,8,16,32s) rather than fail the cycle. No creds, no writes.
    """
    body = json.dumps({"submissionId": submission_id}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            API,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "x"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read()).get("episodes", [])
        except urllib.error.HTTPError as e:  # noqa: PERF203
            last = e
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    if last:
        raise last
    return []


def summarize(submission_id: int) -> dict:
    eps = list_episodes(submission_id)
    rows = []
    for e in eps:
        ags = e.get("agents", [])
        me = next((a for a in ags if a.get("submissionId") == submission_id), None)
        if not me:
            continue
        size = len(ags)
        rs = sorted((a.get("reward", 0) or 0 for a in ags), reverse=True)
        place = 1 + rs.index(me.get("reward", 0) or 0)
        rows.append(
            {
                "ep": e["id"],
                "size": size,
                "place": place,
                "reward": me.get("reward"),
                "our_mu": me.get("initialScore"),
                "d_mu": (me.get("updatedScore") or 0) - (me.get("initialScore") or 0),
                "res": "win" if place == 1 else ("loss" if (size == 2) else f"p{place}"),
            }
        )
    return {"submission_id": submission_id, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission-id", type=int, required=True)
    ap.add_argument(
        "--queue",
        action="store_true",
        help="append episode ids to pending_episodes.txt",
    )
    ap.add_argument("--losses-only", action="store_true", help="queue only losses / non-1st")
    args = ap.parse_args()
    s = summarize(args.submission_id)
    rows = s["rows"]
    twop = [r for r in rows if r["size"] == 2]
    fourp = [r for r in rows if r["size"] == 4]
    print(f"submission {args.submission_id}: {len(rows)} episodes ({len(twop)} 2p, {len(fourp)} 4p)")
    if rows:
        mus = [r["our_mu"] for r in rows if r["our_mu"]]
        print(f"  our μ {min(mus):.0f}–{max(mus):.0f} (median {st.median(mus):.0f})")
    if twop:
        w = sum(r["place"] == 1 for r in twop)
        print(f"  2p: {w}W/{len(twop) - w}L ({100 * w / len(twop):.0f}%), net Δμ {sum(r['d_mu'] for r in twop):+.0f}")
    if fourp:
        from collections import Counter

        pc = Counter(r["place"] for r in fourp)
        print(
            f"  4p: placements {dict(sorted(pc.items()))}, net Δμ {sum(r['d_mu'] for r in fourp):+.0f} "
            f"(4p UPDATES μ — ~half the ladder)"
        )
    if args.queue:
        sel = [r for r in rows if (not args.losses_only) or r["place"] != 1]
        os.makedirs(os.path.dirname(PENDING), exist_ok=True)
        with open(PENDING, "a") as f:
            for r in sel:
                f.write(f"{r['ep']}\n")
        print(f"  queued {len(sel)} episode ids -> {os.path.relpath(PENDING, COMP)}")


if __name__ == "__main__":
    main()
