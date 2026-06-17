"""Episode fetch for the Orbit Wars live loop (KCT-OW-LIVE-002).

Downloads replay JSON for an episode id from the public Kaggle episode store
(same source EPISODES.md analysis #1/#2 used), or drains the manual queue
live/pending_episodes.txt (one episode id or full URL per line). Raw replays go
to the gitignored replays/ dir; we never commit large raw JSON.

Automatic ladder->episode discovery via the Kaggle API is not exposed for this
competition, so this falls back to the manual queue (task: "Do not block only
because automatic discovery is unavailable").

Usage:
    python ops/episode_fetch.py --episode-id 79586066
    python ops/episode_fetch.py --drain-queue
"""

from __future__ import annotations

import argparse
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
REPLAYS = os.path.join(COMP, "replays")
PENDING = os.path.join(COMP, "live", "pending_episodes.txt")
EPISODE_URL = "https://www.kaggleusercontent.com/episodes/{id}.json"


def _episode_id(token: str) -> str | None:
    """Accept a bare id or any URL containing episodeId=<n> / /episodes/<n>."""
    token = token.strip()
    if not token or token.startswith("#"):
        return None
    if token.isdigit():
        return token
    m = re.search(r"episodeId=(\d+)", token) or re.search(r"/episodes/(\d+)", token)
    return m.group(1) if m else None


def fetch(episode_id: str, timeout: int = 60) -> str | None:
    """Download one episode replay to replays/<id>.json. Returns path or None."""
    os.makedirs(REPLAYS, exist_ok=True)
    dst = os.path.join(REPLAYS, f"{episode_id}.json")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        print(f"  {episode_id}: cached ({os.path.getsize(dst)} bytes)")
        return dst
    url = EPISODE_URL.format(id=episode_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "orbit-live-loop"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if not data or data[:1] not in (b"{", b"["):
            print(f"  {episode_id}: not JSON ({len(data)} bytes) — skipped")
            return None
        with open(dst, "wb") as f:
            f.write(data)
        print(f"  {episode_id}: downloaded {len(data)} bytes -> {os.path.relpath(dst, COMP)}")
        return dst
    except Exception as e:  # noqa: BLE001 - network best-effort
        print(f"  {episode_id}: fetch failed ({type(e).__name__}: {e})")
        return None


def drain_queue() -> list[str]:
    """Download every episode listed in live/pending_episodes.txt. Returns paths."""
    if not os.path.isfile(PENDING):
        print(f"no manual queue at {os.path.relpath(PENDING, COMP)} (nothing to drain)")
        return []
    ids = []
    with open(PENDING) as f:
        for line in f:
            eid = _episode_id(line)
            if eid:
                ids.append(eid)
    print(f"queue: {len(ids)} episode id(s)")
    return [p for eid in ids if (p := fetch(eid))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-id")
    ap.add_argument("--drain-queue", action="store_true")
    args = ap.parse_args()
    if args.episode_id:
        eid = _episode_id(args.episode_id)
        if not eid:
            raise SystemExit(f"could not parse episode id from {args.episode_id!r}")
        fetch(eid)
    elif args.drain_queue:
        drain_queue()
    else:
        ap.error("give --episode-id <id> or --drain-queue")


if __name__ == "__main__":
    main()
