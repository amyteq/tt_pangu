"""Orbit Wars — thin reference wrapper over core.geometry (OW-ARCH-001).

Historically a standalone "verified building blocks" library that kept its OWN copies of the engine
physics; it is imported by nothing in production and its planet_pos had drifted stale (pre-B11). It
now RE-EXPORTS the canonical primitives from `core.geometry` — the single source of truth, including
the B11 planet-rotation phase fix — so there is no second, drift-prone implementation. Two small
non-primitive helpers (path_blocked, terminal_value) are kept here, built on the re-exported
primitives, for reference / quick-start agents.
"""

import os as _os
import sys as _sys

_COMP = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # competitions/orbit-wars
if _COMP not in _sys.path:
    _sys.path.insert(0, _COMP)

from core.geometry import (  # noqa: E402  (single source of physics/geometry primitives)
    BOARD,
    CENTER,
    EPISODE_STEPS,
    MAX_SPEED,
    ROT_LIMIT,
    SUN_R,
    fleet_speed,
    is_orbiting,
    orbital_radius,
    planet_pos,
    project,
    replay_planet,
    resolve_combat,
    seg_point_dist,
    solve_intercept,
    swept_hit,
)

__all__ = [
    "BOARD",
    "CENTER",
    "SUN_R",
    "ROT_LIMIT",
    "MAX_SPEED",
    "EPISODE_STEPS",
    "fleet_speed",
    "planet_pos",
    "seg_point_dist",
    "swept_hit",
    "resolve_combat",
    "solve_intercept",
    "replay_planet",
    "project",
    "orbital_radius",
    "is_orbiting",
    "path_blocked",
    "terminal_value",
]


def path_blocked(mx, my, tx, ty, mine_id, tgt_id, planets, comet_ids, clearance=1.0):
    """True if a straight launch path clips the sun or any OTHER planet (current-position screen;
    the engine consumes a fleet on the FIRST body it touches). Built on core.geometry.seg_point_dist."""
    if seg_point_dist(CENTER, CENTER, mx, my, tx, ty) < SUN_R:
        return True
    for p in planets:
        if p.id == mine_id or p.id == tgt_id or p.id in comet_ids:
            continue
        if seg_point_dist(p.x, p.y, mx, my, tx, ty) < p.radius + clearance:
            return True
    return False


def terminal_value(owner_list, ships_list, me, H):
    """Conservation-correct move score: +ships if we own the planet at horizon H, -ships if an
    opponent does, 0 if neutral (ships in transit have landed by H, so launching isn't penalized)."""
    o, s = owner_list[H], ships_list[H]
    return s if o == me else (-s if o != -1 else 0.0)
