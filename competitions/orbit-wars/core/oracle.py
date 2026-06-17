"""FlightOracle — deterministic launch-safety / first-hit decode.

Given a launch (source planet, angle, ship count), trace the fleet tick-by-tick with
the engine-verified swept-collision (`geometry.swept_hit` against every moving planet,
plus sun + out-of-bounds) and report the FIRST body it hits. This is the single source
of truth the action emitter and the ledger use: never emit an action unless the first
hit is the intended target (or a documented safe exception).

Distinguishes:
  - strict_sun_collision (path enters the sun disc, radius SUN_R -> fleet dies)   -> INVALID
  - near_sun_warning     (path grazes within SUN_R + NEAR_SUN_BUFFER, survives)   -> valid + flagged
  - out_of_bounds        (fleet leaves the board)                                 -> INVALID
  - wrong first hit      (a friendly/enemy/neutral/comet body before the target)  -> INVALID for validate_target
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import geometry as G

NEAR_SUN_BUFFER = 2.0  # within SUN_R + this (but not inside SUN_R) = near-sun warning


@dataclass
class FlightResult:
    valid: bool
    first_hit_type: str  # target|friendly|enemy|neutral|comet|sun|oob|none|unknown
    first_hit_id: int | None
    eta: int | None
    min_sun_distance: float | None
    path_ticks: int
    source_planet_id: int
    intended_target_id: int | None
    ships: int
    angle: float
    reason: str
    near_sun: bool = False


def _parse(obs):
    planets = [tuple(p) for p in obs.get("planets", [])]  # (id,owner,x,y,r,ships,prod)
    fleets = [tuple(f) for f in obs.get("fleets", [])]
    init_by_id = {p[0]: tuple(p) for p in obs.get("initial_planets", [])}
    ang_vel = obs.get("angular_velocity", 0.0)
    step = int(obs.get("step", 0))
    comet_ids = set(obs.get("comet_planet_ids", []) or [])
    me = obs.get("player", 0)
    return planets, fleets, init_by_id, ang_vel, step, comet_ids, me


class FlightOracle:
    """Stateless per-observation flight oracle (cheap to re-instantiate per turn)."""

    def first_hit(self, obs, source_planet_id, angle, ships, horizon=120) -> FlightResult:
        """Trace a NEW launch from `source_planet_id` (engine launch point = radius + 0.1 outward)."""
        planets, fleets, init_by_id, ang_vel, step, comet_ids, me = _parse(obs)
        by_id = {p[0]: p for p in planets}
        src = by_id.get(source_planet_id)
        if src is None:
            return FlightResult(
                False,
                "unknown",
                None,
                None,
                None,
                0,
                source_planet_id,
                None,
                int(ships),
                float(angle),
                "source planet not found",
            )
        dx, dy = math.cos(angle), math.sin(angle)
        # engine launches the fleet just OUTSIDE the source (radius + 0.1)
        ax = src[2] + dx * (src[4] + 0.1)
        ay = src[3] + dy * (src[4] + 0.1)
        return self._trace_from(
            (planets, by_id, init_by_id, ang_vel, step, comet_ids, me),
            ax,
            ay,
            angle,
            ships,
            source_planet_id,
            None,
            horizon,
        )

    def trace_from_position(self, obs, x, y, angle, ships, owner=None, horizon=120) -> FlightResult:
        """Trace from an ARBITRARY current position (e.g. an in-flight fleet's (x, y)) — does NOT
        relaunch from a source planet. `owner` is accepted for API symmetry (tracing is owner-agnostic)."""
        planets, fleets, init_by_id, ang_vel, step, comet_ids, me = _parse(obs)
        by_id = {p[0]: p for p in planets}
        return self._trace_from(
            (planets, by_id, init_by_id, ang_vel, step, comet_ids, me),
            float(x),
            float(y),
            angle,
            ships,
            -1,
            None,
            horizon,
        )

    def decode_existing_fleet(self, obs, fleet_row, horizon=120) -> FlightResult:
        """Decode an in-flight fleet to its first-hit target by tracing from its CURRENT position.
        fleet_row = (id, owner, x, y, angle, from_planet_id, ships) — engine fleet tuple."""
        _fid, fowner, fx, fy, fang, ffrom, fships = (
            fleet_row[0],
            fleet_row[1],
            fleet_row[2],
            fleet_row[3],
            fleet_row[4],
            fleet_row[5],
            fleet_row[6],
        )
        res = self.trace_from_position(obs, fx, fy, fang, int(fships), fowner, horizon)
        res.source_planet_id = ffrom  # informational: which planet it launched from
        return res

    def _trace_from(self, parsed, ax, ay, angle, ships, source_planet_id, intended_target_id, horizon) -> FlightResult:
        """Shared tick-by-tick swept trace from start point (ax, ay). Used by first_hit (launch
        point) and trace_from_position (in-flight current position) — single source of trace logic."""
        planets, by_id, init_by_id, ang_vel, step, comet_ids, me = parsed
        ships = int(ships)
        spd = G.fleet_speed(ships)
        dx, dy = math.cos(angle), math.sin(angle)
        min_sun = float("inf")
        for k in range(1, horizon + 1):
            bx, by = ax + dx * spd, ay + dy * spd
            # planet swept positions for this tick (step+k-1 -> step+k), mirrors project()
            hit_pid = None
            for p in planets:
                ip = init_by_id.get(p[0], p)
                p0 = G.planet_pos(ip[2], ip[3], p[4], ang_vel, step + k - 1)
                p1 = G.planet_pos(ip[2], ip[3], p[4], ang_vel, step + k)
                if G.swept_hit((ax, ay), (bx, by), p0, p1, p[4]):
                    hit_pid = p[0]
                    break
            d_sun = G.seg_point_dist(G.CENTER, G.CENTER, ax, ay, bx, by)
            min_sun = min(min_sun, d_sun)
            if hit_pid is not None:
                p = by_id[hit_pid]
                if hit_pid in comet_ids:
                    htype = "comet"
                elif p[1] == me:
                    htype = "friendly"
                elif p[1] == -1:
                    htype = "neutral"
                else:
                    htype = "enemy"
                near = G.SUN_R <= min_sun < G.SUN_R + NEAR_SUN_BUFFER
                return FlightResult(
                    True,
                    htype,
                    hit_pid,
                    k,
                    round(min_sun, 3),
                    k,
                    source_planet_id,
                    None,
                    ships,
                    float(angle),
                    f"first hit {htype} planet {hit_pid} at eta {k}",
                    near,
                )
            # no planet hit this tick — sun / OOB checks (engine order: collision, then OOB, then sun)
            if not (0.0 <= bx <= G.BOARD and 0.0 <= by <= G.BOARD):
                return FlightResult(
                    False,
                    "oob",
                    None,
                    k,
                    round(min_sun, 3),
                    k,
                    source_planet_id,
                    None,
                    ships,
                    float(angle),
                    f"out of bounds at eta {k}",
                )
            if d_sun < G.SUN_R:
                return FlightResult(
                    False,
                    "sun",
                    None,
                    k,
                    round(min_sun, 3),
                    k,
                    source_planet_id,
                    None,
                    ships,
                    float(angle),
                    f"strict_sun_collision at eta {k} (min_sun_distance {min_sun:.2f} < {G.SUN_R})",
                )
            ax, ay = bx, by
        return FlightResult(
            False,
            "none",
            None,
            None,
            round(min_sun, 3),
            horizon,
            source_planet_id,
            None,
            ships,
            float(angle),
            f"no body hit within horizon {horizon}",
        )

    def validate_target(self, obs, source_planet_id, target_id, ships, horizon=120) -> FlightResult:
        """Solve the intercept angle to `target_id`, trace it, and accept ONLY if the
        intended target is the first hit (no wrong-first-hit, no strict sun, no OOB)."""
        planets, fleets, init_by_id, ang_vel, step, comet_ids, me = _parse(obs)
        by_id = {p[0]: p for p in planets}
        src = by_id.get(source_planet_id)
        if src is None or target_id not in by_id:
            return FlightResult(
                False,
                "unknown",
                None,
                None,
                None,
                0,
                source_planet_id,
                target_id,
                int(ships),
                0.0,
                "source or target planet not found",
            )
        sol = G.solve_intercept(src[2], src[3], target_id, int(ships), step, init_by_id, ang_vel)
        if sol is None:
            return FlightResult(
                False,
                "unknown",
                None,
                None,
                None,
                0,
                source_planet_id,
                target_id,
                int(ships),
                0.0,
                "no intercept solution",
            )
        angle, _eta, _pos = sol
        res = self.first_hit(obs, source_planet_id, angle, ships, horizon)
        res.intended_target_id = target_id
        if res.first_hit_id == target_id:
            res.first_hit_type = "target"
            res.valid = True
            res.reason = f"intended target {target_id} is first hit at eta {res.eta}" + (
                " (near-sun warning)" if res.near_sun else ""
            )
        else:
            res.valid = False
            if res.first_hit_type in ("sun", "oob"):
                res.reason = f"blocked: {res.reason} before reaching target {target_id}"
            else:
                res.reason = (
                    f"blocked: wrong first hit — {res.first_hit_type} planet "
                    f"{res.first_hit_id} (eta {res.eta}) before intended target {target_id}"
                )
        return res
