# =====================================================================
# explore — heuristic frame-diff explorer for ARC-AGI-3 (no NN / no GPU)
#
# Idea: with no instructions, the cheapest useful signal is "did my action
# change the world?". Track, per level, an action's empirical change-rate and
# prefer actions that move the state, with epsilon exploration to escape ruts.
# For coordinate actions (ACTION6) sweep a coarse lattice of untried cells.
# Pure-Python + numpy: robust, fast, and immune to torch/CUDA failure in the
# competition rerun (a deliberate hedge against the CNN agents).
#
# Compatibility: gateway sends available_actions as raw ints [1..6] and may
# omit `score`; we normalize both and fall back to levels_completed.
# =====================================================================
import hashlib
import random
import time
import traceback
from typing import Any

import numpy as np

from agents.agent import Agent
from arcengine import GameAction, GameState

SIMPLE = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5]


def _avail_ids(latest_frame) -> list[int]:
    """available_actions may be GameAction enums (local) or raw ints (gateway)."""
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
    """Heuristic explorer: prefer state-changing actions; lattice-sweep clicks."""

    MAX_ACTIONS = float("inf")
    STRIDE = 8  # coarse lattice for ACTION6 coordinate sweep
    EPSILON = 0.15  # exploration rate over simple actions
    ACTION6_SHARE = 0.25  # fraction of turns to spend probing coordinates when available

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = (int(time.time() * 1e6) + hash(self.game_id)) % (2**32 - 1)
        random.seed(seed)
        np.random.seed(seed)
        self.start_time = time.time()
        self.current_level = -1
        self.prev_grid = None
        self.prev_action_id = None  # 1..6
        # per-action stats: id -> [tries, changes]
        self.stats = {i: [0, 0] for i in range(1, 7)}
        self.coord_queue: list[tuple[int, int]] = []
        self.seen_hashes: set[str] = set()

    def _has_time_elapsed(self) -> bool:
        return (time.time() - self.start_time) >= 8 * 3600 - 5 * 60

    def _reset_level(self) -> None:
        self.prev_grid = None
        self.prev_action_id = None
        self.stats = {i: [0, 0] for i in range(1, 7)}
        self.coord_queue = []
        self.seen_hashes = set()

    def _build_coord_queue(self) -> None:
        cells = [
            (x, y) for y in range(self.STRIDE // 2, 64, self.STRIDE) for x in range(self.STRIDE // 2, 64, self.STRIDE)
        ]
        random.shuffle(cells)
        self.coord_queue = cells

    def is_done(self, frames, latest_frame) -> bool:
        try:
            return bool(latest_frame.state is GameState.WIN or self._has_time_elapsed())
        except Exception:
            return True

    def _change_rate(self, aid: int) -> float:
        tries, changes = self.stats[aid]
        return (changes + 1.0) / (tries + 2.0)  # Laplace-smoothed

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
            # learn from the previous action's effect
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

            # occasionally probe coordinates if ACTION6 is available
            if has_click and random.random() < self.ACTION6_SHARE:
                if not self.coord_queue:
                    self._build_coord_queue()
                x, y = self.coord_queue.pop()
                act = GameAction.ACTION6
                act.set_data({"x": int(x), "y": int(y)})
                act.reasoning = {"strategy": "lattice-sweep", "x": int(x), "y": int(y)}
                self.prev_grid = grid
                self.prev_action_id = 6
                return act

            # else pick a simple action: epsilon-greedy on change-rate
            if random.random() < self.EPSILON:
                aid = random.choice(simple_ids)
            else:
                aid = max(simple_ids, key=self._change_rate)
            act = SIMPLE[aid - 1]
            act.reasoning = f"explore aid={aid} change_rate={self._change_rate(aid):.2f}"
            self.prev_grid = grid
            self.prev_action_id = aid
            return act

        except Exception as e:
            traceback.print_exc()
            a = random.choice(SIMPLE[:4])
            a.reasoning = f"fallback after error: {e}"
            return a
