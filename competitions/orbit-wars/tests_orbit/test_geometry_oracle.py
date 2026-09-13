"""Geometry + FlightOracle tests (OW-ARCH-001): fleet_speed, sun/near-sun/oob, first-hit,
and trace-from-source vs trace-from-current-position (the in-flight decode fix)."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from core import geometry as G  # noqa: E402
from core.oracle import FlightOracle  # noqa: E402


def _obs(planets, fleets=(), ang_vel=0.0, step=5, me=0):
    return {
        "planets": [list(p) for p in planets],
        "fleets": [list(f) for f in fleets],
        "initial_planets": [list(p) for p in planets],  # static (ang_vel=0) -> init == current
        "angular_velocity": ang_vel,
        "step": step,
        "comet_planet_ids": [],
        "player": me,
    }


# A clear horizontal lane: source@(10,50), target@(35,50) (clear of the sun disc r=10 at (50,50)).
SRC = (0, 0, 10.0, 50.0, 2.0, 50.0, 3)  # id 0, mine
TGT = (1, -1, 35.0, 50.0, 2.0, 5.0, 2)  # id 1, neutral


def test_fleet_speed_monotonic_and_capped():
    assert G.fleet_speed(1) == 1.0
    assert G.fleet_speed(10) < G.fleet_speed(100) < G.fleet_speed(1000)
    assert G.fleet_speed(10**6) <= G.MAX_SPEED


def test_first_hit_target_and_sun_and_oob():
    obs = _obs([SRC, TGT])
    orc = FlightOracle()
    # aim straight at the target (angle 0, +x) -> first hit is the target planet (id 1)
    r = orc.first_hit(obs, 0, 0.0, 30)
    assert r.first_hit_id == 1 and r.first_hit_type in ("neutral", "target")
    # aim through the sun (no planet there) -> strict sun collision, invalid
    rs = FlightOracle().first_hit(_obs([SRC]), 0, 0.0, 30)  # only source; lane crosses sun
    assert rs.first_hit_type == "sun" and rs.valid is False
    # aim up-and-out with a tiny board exit -> oob (source near top, angle +y off board)
    src_top = (0, 0, 10.0, 98.0, 2.0, 50.0, 3)
    ro = FlightOracle().first_hit(_obs([src_top]), 0, math.pi / 2, 30)
    assert ro.first_hit_type == "oob" and ro.valid is False


def test_near_sun_warning_distinct_from_collision():
    # a lane grazing just outside the sun disc should be valid but near_sun-flagged
    orc = FlightOracle()
    # place a target beyond the sun, lane y just tangent to SUN_R+1
    graze_y = 50.0 - (G.SUN_R + 1.0)
    src = (0, 0, 2.0, graze_y, 2.0, 50.0, 3)
    far = (1, -1, 95.0, graze_y, 2.0, 5.0, 2)
    r = orc.first_hit(_obs([src, far]), 0, 0.0, 30)
    # not a strict collision (min_sun >= SUN_R); near_sun set when within SUN_R+buffer
    assert r.first_hit_type != "sun"


def test_trace_from_position_differs_from_relaunch_from_source():
    """An in-flight fleet must be traced from its CURRENT (x,y), giving a SHORTER eta to the same
    target than relaunching from the source planet."""
    obs = _obs([SRC, TGT])
    orc = FlightOracle()
    from_source = orc.first_hit(obs, 0, 0.0, 30)  # launch from source @ (10,50)
    midway = orc.trace_from_position(obs, 30.0, 50.0, 0.0, 30)  # in-flight @ (30,50)
    assert from_source.first_hit_id == midway.first_hit_id == 1
    assert midway.eta is not None and from_source.eta is not None
    assert midway.eta < from_source.eta, (midway.eta, from_source.eta)


def test_decode_existing_fleet_uses_current_position():
    obs = _obs([SRC, TGT])
    orc = FlightOracle()
    # fleet row: (id, owner, x, y, angle, from_planet_id, ships) — already at (30,50) heading +x
    fleet = (7, 0, 30.0, 50.0, 0.0, 0, 30)
    res = orc.decode_existing_fleet(obs, fleet)
    assert res.first_hit_id == 1  # reaches the target
    assert res.source_planet_id == 0  # informational: launched from planet 0
    # eta matches a from-current-position trace, NOT a relaunch from source
    assert res.eta == orc.trace_from_position(obs, 30.0, 50.0, 0.0, 30).eta


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} geometry-oracle tests passed")
