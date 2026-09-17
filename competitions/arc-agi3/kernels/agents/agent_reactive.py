# =====================================================================
# reactive — object-centric, novelty-seeking heuristic agent (no NN / no GPU)
#
# Two ideas distinct from the lattice explorer:
#   1. Object-centric clicks: instead of sweeping a blind lattice, ACTION6
#      targets the centroids of distinct non-background colour regions (the
#      Core-Knowledge "objectness" prior) — far fewer, more meaningful clicks,
#      which matters because RHAE penalises wasted actions quadratically.
#   2. Count-based novelty: prefer the simple action least recently taken that
#      still tends to change the world, breaking the "spam one direction" rut.
#
# Compatibility: handles available_actions as ints or enums; uses
# levels_completed for level-change detection.
# =====================================================================
import hashlib
import random
import time
import traceback
from collections import Counter
from typing import Any

import numpy as np

from agents.agent import Agent
from arcengine import GameAction, GameState

SIMPLE = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5]


def _avail_ids(latest_frame) -> list[int]:
    raw = getattr(latest_frame, "available_actions", None) or []
    ids = []
    for a in raw:
        try:
            ids.append(a.value if hasattr(a, "value") else int(a))
        except (TypeError, ValueError):
            continue
    return ids


def _grid(latest_frame):
    f = getattr(latest_frame, "frame", None)
    if not f:
        return None
    try:
        return np.array(f[-1], dtype=np.int16)
    except (ValueError, TypeError):
        return None


def _fhash(grid) -> str:
    return hashlib.md5(grid.tobytes()).hexdigest() if grid is not None else "none"


class MyAgent(Agent):
    """Object-centric, novelty-seeking explorer."""

    MAX_ACTIONS = float("inf")
    ACTION6_SHARE = 0.30

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = (int(time.time() * 1e6) + hash(self.game_id)) % (2**32 - 1)
        random.seed(seed)
        np.random.seed(seed)
        self.start_time = time.time()
        self.current_level = -1
        self.prev_grid = None
        self.prev_action_id = None
        self.stats = {i: [0, 0] for i in range(1, 7)}  # id -> [tries, changes]
        self.last_used = {i: -999 for i in range(1, 7)}  # recency for novelty
        self.clicked: set[tuple[int, int]] = set()
        self.seen_hashes: set[str] = set()

    def _has_time_elapsed(self) -> bool:
        return (time.time() - self.start_time) >= 8 * 3600 - 5 * 60

    def _reset_level(self) -> None:
        self.prev_grid = None
        self.prev_action_id = None
        self.stats = {i: [0, 0] for i in range(1, 7)}
        self.last_used = {i: -999 for i in range(1, 7)}
        self.clicked = set()
        self.seen_hashes = set()

    def is_done(self, frames, latest_frame) -> bool:
        try:
            return bool(latest_frame.state is GameState.WIN or self._has_time_elapsed())
        except Exception:
            return True

    def _object_centroids(self, grid) -> list[tuple[int, int]]:
        """Centroid (x,y) of each distinct non-background colour region."""
        if grid is None:
            return []
        flat = grid.flatten()
        bg = Counter(flat.tolist()).most_common(1)[0][0]  # modal colour = background
        out = []
        for color in np.unique(grid):
            if color == bg:
                continue
            ys, xs = np.where(grid == color)
            if len(xs) == 0:
                continue
            out.append((int(round(xs.mean())), int(round(ys.mean()))))
        return out

    def _score_simple(self, aid: int) -> float:
        tries, changes = self.stats[aid]
        rate = (changes + 1.0) / (tries + 2.0)
        recency_bonus = 0.1 * (self.action_counter - self.last_used[aid])  # novelty
        return rate + min(recency_bonus, 1.0)

    def choose_action(self, frames, latest_frame) -> GameAction:
        try:
            level = getattr(latest_frame, "levels_completed", 0) or 0
            if level != self.current_level:
                self._reset_level()
                self.current_level = level

            if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
                self.prev_grid = None
                self.prev_action_id = None
                a = GameAction.RESET
                a.reasoning = "reset (not_played/game_over)"
                return a

            grid = _grid(latest_frame)
            if self.prev_grid is not None and self.prev_action_id is not None:
                changed = grid is None or not np.array_equal(self.prev_grid, grid)
                self.stats[self.prev_action_id][0] += 1
                if changed:
                    self.stats[self.prev_action_id][1] += 1
            if grid is not None:
                self.seen_hashes.add(_fhash(grid))

            ids = _avail_ids(latest_frame)
            simple_ids = [i for i in ids if 1 <= i <= 5] or [1, 2, 3, 4]
            has_click = 6 in ids

            if has_click and random.random() < self.ACTION6_SHARE:
                centroids = [c for c in self._object_centroids(grid) if c not in self.clicked]
                if not centroids:
                    self.clicked.clear()  # all clicked -> start over
                    centroids = self._object_centroids(grid)
                if centroids:
                    x, y = random.choice(centroids)
                    self.clicked.add((x, y))
                    act = GameAction.ACTION6
                    act.set_data({"x": int(x), "y": int(y)})
                    act.reasoning = {"strategy": "object-centroid", "x": int(x), "y": int(y)}
                    self.last_used[6] = self.action_counter
                    self.prev_grid = grid
                    self.prev_action_id = 6
                    return act

            aid = max(simple_ids, key=self._score_simple)
            act = SIMPLE[aid - 1]
            act.reasoning = f"reactive aid={aid} score={self._score_simple(aid):.2f}"
            self.last_used[aid] = self.action_counter
            self.prev_grid = grid
            self.prev_action_id = aid
            return act

        except Exception as e:
            traceback.print_exc()
            a = random.choice(SIMPLE[:4])
            a.reasoning = f"fallback after error: {e}"
            return a
