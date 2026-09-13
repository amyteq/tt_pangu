"""RuleEngine wiring (OW-ARCH-001): the layer [6] gate is PASS-THROUGH by default
(OW_RULE_ENGINE unset -> identical candidate list) and, when enabled, blocks/re-weights
candidates without crashing and the agent still emits a valid sanitized action list."""

import os
import sys

os.environ["OMP_NUM_THREADS"] = "1"
for _k in list(os.environ):
    if _k.startswith("OW_"):
        del os.environ[_k]
HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
for _p in (COMP, os.path.join(COMP, "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import policy  # noqa: E402
from core.oracle import FlightOracle  # noqa: E402

# clear lane: source@(10,50) mine, neutral target@(35,50); a synthetic candidate list
SRC = (0, 0, 10.0, 50.0, 2.0, 50.0, 3)
TGT = (1, -1, 35.0, 50.0, 2.0, 5.0, 2)
OBS = {
    "planets": [list(SRC), list(TGT)],
    "fleets": [],
    "initial_planets": [list(SRC), list(TGT)],
    "angular_velocity": 0.0,
    "step": 5,
    "comet_planet_ids": [],
    "player": 0,
}
# candidate tuple format used by the greedy commit: (value, src_id, tgt_id, angle, needed)
CANDS = [(10.0, 0, 1, 0.0, 6)]


def test_pass_through_identity_when_disabled():
    # OW_RULE_ENGINE unset -> the exact same list comes back unchanged
    out = policy._rule_gate(OBS, list(CANDS))
    assert out == CANDS, out


def test_enabled_does_not_crash_and_returns_well_formed():
    os.environ["OW_RULE_ENGINE"] = "1"
    try:
        out = policy._rule_gate(OBS, list(CANDS))
        assert isinstance(out, list)
        for tup in out:
            assert len(tup) == 5
            value, src, tgt, ang, need = tup
            float(value)
            int(src)
            int(tgt)
            float(ang)
            int(need)
        # the clear-lane candidate is valid -> not blocked away
        assert any(t[1:] == (0, 1, 0.0, 6) for t in out), out
    finally:
        del os.environ["OW_RULE_ENGINE"]


def test_agent_still_valid_with_rule_engine_on():
    import logging

    logging.disable(logging.INFO)
    from kaggle_environments import make

    env = make("orbit_wars", configuration={"seed": 31337})
    env.reset(num_agents=2)
    obs = env.steps[0][0]["observation"]
    import main as entry

    os.environ["OW_RULE_ENGINE"] = "1"
    try:
        moves = entry.agent(obs)
        assert isinstance(moves, list)
        orc = FlightOracle()
        for mv in moves:
            assert isinstance(mv, (list, tuple)) and len(mv) == 3
            r = orc.first_hit(obs, int(mv[0]), float(mv[1]), int(mv[2]))
            assert r.first_hit_type not in ("sun", "oob"), (mv, r.first_hit_type)
    finally:
        del os.environ["OW_RULE_ENGINE"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} rule-engine-wiring tests passed")
