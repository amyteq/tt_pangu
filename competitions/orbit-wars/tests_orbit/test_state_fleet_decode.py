"""BattlefieldState fleet-decode tests (OW-ARCH-001): in-flight fleets are decoded from their
CURRENT position, not relaunched from the source planet."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from core.oracle import FlightOracle  # noqa: E402
from core.state import build_battlefield_state  # noqa: E402

SRC = (0, 0, 10.0, 50.0, 2.0, 50.0, 3)  # mine
TGT = (1, -1, 35.0, 50.0, 2.0, 5.0, 2)  # neutral target on a clear +x lane
# in-flight fleet of mine, already at (30,50) heading +x toward the target (from planet 0)
FLEET = (7, 0, 30.0, 50.0, 0.0, 0, 30)


def _obs(planets, fleets):
    return {
        "planets": [list(p) for p in planets],
        "fleets": [list(f) for f in fleets],
        "initial_planets": [list(p) for p in planets],  # static
        "angular_velocity": 0.0,
        "step": 5,
        "comet_planet_ids": [],
        "player": 0,
    }


def test_state_builds_from_minimal_obs():
    st = build_battlefield_state(_obs([SRC, TGT], []), horizon=40)
    assert 0 in st.planets and 1 in st.planets
    assert hasattr(st, "fleets")


def test_inflight_fleet_decoded_from_current_position():
    obs = _obs([SRC, TGT], [FLEET])
    st = build_battlefield_state(obs, horizon=40)
    fs = st.fleets[7]
    # decoded to the real target, traced from current (30,50)
    assert fs.decoded_first_hit_id == 1, fs.decoded_first_hit_id
    orc = FlightOracle()
    cur = orc.trace_from_position(obs, 30.0, 50.0, 0.0, 30)
    relaunch = orc.first_hit(obs, 0, 0.0, 30)  # WRONG (old) way: from source @ (10,50)
    assert fs.eta == cur.eta, (fs.eta, cur.eta)
    assert cur.eta < relaunch.eta, "current-position decode must give a shorter eta than relaunch"


def test_decode_is_stable_for_known_case():
    obs = _obs([SRC, TGT], [FLEET])
    a = build_battlefield_state(obs, horizon=40).fleets[7]
    b = build_battlefield_state(obs, horizon=40).fleets[7]
    assert (a.decoded_first_hit_id, a.eta, a.path_safety) == (b.decoded_first_hit_id, b.eta, b.path_safety)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} state-fleet-decode tests passed")
