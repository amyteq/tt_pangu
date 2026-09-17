"""Shared replay parsing for the Orbit Wars dataset pipeline (stdlib only).

A kaggle_environments replay JSON has:
  info.EpisodeId / info.TeamNames / info.Agents / seed
  rewards[seat]                         (final, seat-ordered)
  statuses[seat]
  steps[t][seat].observation            (full board on seat 0; .player, .planets, .fleets,
                                          .initial_planets, .angular_velocity, .comet_planet_ids, .step)
  steps[t][seat].action                 (that seat's launches: [[src, angle, ships], ...])

Constants (initial_planets / angular_velocity / comet_planet_ids) live on step 0's obs; this
module backfills them onto each step's board view so `core.state`/`core.oracle` can consume it.
"""

from __future__ import annotations

import glob
import json
import os


def iter_replays(root):
    """Yield (path, replay_dict) for every *.json under `root` (non-recursive + one level)."""
    paths = sorted(glob.glob(os.path.join(root, "*.json")) + glob.glob(os.path.join(root, "*", "*.json")))
    for p in paths:
        try:
            with open(p) as f:
                yield p, json.load(f)
        except Exception as e:  # malformed -> caller counts it
            yield p, {"__malformed__": str(e)}


def _steps(replay):
    return replay.get("steps") if isinstance(replay, dict) and "steps" in replay else replay


def parse_meta(path, replay):
    """Episode-index row. Returns dict (with malformed=True on parse failure)."""
    if not isinstance(replay, dict) or replay.get("__malformed__") or "steps" not in replay:
        return {"episode_id": None, "source_path": path, "malformed": True}
    info = replay.get("info") or {}
    steps = _steps(replay)
    rewards = replay.get("rewards") or [s.get("reward") for s in steps[-1]]
    names = info.get("TeamNames") or [a.get("Name") for a in (info.get("Agents") or [])]
    pcount = len(steps[0]) if steps else 0
    # winner = max reward seat (None reward -> -inf)
    rs = [(r if r is not None else float("-inf")) for r in (rewards or [])]
    winner_seat = max(range(len(rs)), key=lambda i: rs[i]) if rs else None
    obs0 = steps[0][0]["observation"] if steps else {}
    return {
        "episode_id": info.get("EpisodeId"),
        "source_path": path,
        "player_count": pcount,
        "seed": info.get("seed", obs0.get("seed")),
        "module_version": replay.get("module_version"),
        "team_names": names,
        "rewards": rewards,
        "winner_seat": winner_seat,
        "winner_name": (
            names[winner_seat] if (names and winner_seat is not None and winner_seat < len(names)) else None
        ),
        "num_steps": len(steps),
        "malformed": False,
    }


def _constants(replay):
    obs0 = _steps(replay)[0][0]["observation"]
    return {
        "initial_planets": obs0.get("initial_planets", obs0.get("planets", [])),
        "angular_velocity": obs0.get("angular_velocity", 0.0),
    }


def board_at(replay, t, seat=0):
    """Full board observation at step t, backfilled with constants, viewed as `seat` (sets
    obs['player']=seat so core.state treats that seat as 'me'). Returns None if unavailable."""
    steps = _steps(replay)
    if t >= len(steps):
        return None
    # full board lives on seat 0; other seats may carry a sparse view -> use seat 0's board
    base = dict(steps[t][0]["observation"])
    consts = _constants(replay)
    board = {
        "planets": base.get("planets", []),
        "fleets": base.get("fleets", []),
        "step": base.get("step", t),
        "comet_planet_ids": base.get("comet_planet_ids", []) or [],
        "initial_planets": base.get("initial_planets") or consts["initial_planets"],
        "angular_velocity": base.get("angular_velocity", consts["angular_velocity"]),
        "player": seat,
    }
    return board


def action_at(replay, t, seat):
    """The launches [[src, angle, ships], ...] that `seat` issued at step t (or [])."""
    steps = _steps(replay)
    if t >= len(steps) or seat >= len(steps[t]):
        return []
    act = steps[t][seat].get("action")
    return act if isinstance(act, list) else []
