"""ActionSanitizer + agent emission-gate smokes (prompt 02 integration)."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from core.action_sanitizer import ActionSanitizer, sanitize_default, new_counters  # noqa: E402
from core.oracle import FlightOracle  # noqa: E402
from core import geometry as G  # noqa: E402


def _obs(seed=12345):
    from kaggle_environments import make

    env = make("orbit_wars", configuration={"seed": seed})
    env.reset(num_agents=2)
    return env.steps[0][0]["observation"]


def test_sanitizer_blocks_sun_and_oob_keeps_valid():
    obs = _obs()
    me = obs.get("player", 0)
    mine = [p for p in obs["planets"] if p[1] == me]
    others = [p for p in obs["planets"] if p[1] != me]
    src = mine[0]
    orc = FlightOracle()
    # a valid launch (intercept angle to a real target)
    sol = G.solve_intercept(
        src[2],
        src[3],
        others[0][0],
        30,
        int(obs.get("step", 0)),
        {p[0]: tuple(p) for p in obs["initial_planets"]},
        obs.get("angular_velocity", 0.0),
    )
    good_angle = sol[0]
    sun_angle = math.atan2(G.CENTER - src[3], G.CENTER - src[2])  # straight at the sun
    # oob: aim away from the board (toward the nearest edge, away from center)
    oob_angle = math.atan2(src[3] - G.CENTER, src[2] - G.CENTER)
    actions = [
        [src[0], good_angle, 30],
        [src[0], sun_angle, 30],
        [src[0], oob_angle, 30],
    ]
    san = ActionSanitizer(orc)
    ctr = new_counters()
    clean, ctr = san.sanitize(obs, actions, counters=ctr)
    assert ctr["blocked_sun"] >= 1, ctr
    assert ctr["emitted_valid"] >= 1, ctr
    # every emitted action is sun-safe and not oob
    for mv in clean:
        r = orc.first_hit(obs, mv[0], mv[1], mv[2])
        assert r.first_hit_type not in ("sun", "oob")


def test_sanitizer_blocks_wrong_first_hit_when_target_given():
    obs = _obs()
    me = obs.get("player", 0)
    mine = [p for p in obs["planets"] if p[1] == me]
    others = [p for p in obs["planets"] if p[1] != me]
    src, tgt = mine[0], others[0]
    init = {p[0]: tuple(p) for p in obs["initial_planets"]}
    sol = G.solve_intercept(
        src[2],
        src[3],
        tgt[0],
        30,
        int(obs.get("step", 0)),
        init,
        obs.get("angular_velocity", 0.0),
    )
    # claim a DIFFERENT intended target than the one the angle actually hits -> wrong-first-hit block
    wrong_tgt = next((o[0] for o in others if o[0] != tgt[0]), tgt[0])
    san = ActionSanitizer()
    clean, ctr = san.sanitize(obs, [[src[0], sol[0], 30]], targets=[wrong_tgt])
    if wrong_tgt != tgt[0]:
        assert ctr["blocked_wrong_first_hit"] == 1 and clean == [], ctr
    # correct target -> emitted
    clean2, ctr2 = san.sanitize(obs, [[src[0], sol[0], 30]], targets=[tgt[0]])
    assert ctr2["emitted_valid"] == 1 and len(clean2) == 1


def test_sanitize_default_is_safe_noop_on_valid_actions():
    """sanitize_default must not drop a sanely-aimed action (zero-regression guarantee)."""
    obs = _obs()
    me = obs.get("player", 0)
    src = [p for p in obs["planets"] if p[1] == me][0]
    others = [p for p in obs["planets"] if p[1] != me]
    init = {p[0]: tuple(p) for p in obs["initial_planets"]}
    valid = []
    for o in others[:5]:
        sol = G.solve_intercept(
            src[2],
            src[3],
            o[0],
            30,
            int(obs.get("step", 0)),
            init,
            obs.get("angular_velocity", 0.0),
        )
        r = FlightOracle().first_hit(obs, src[0], sol[0], 30)
        if r.first_hit_type not in ("sun", "oob", "none"):
            valid.append([src[0], sol[0], 30])
    clean = sanitize_default(obs, valid)
    assert clean == valid  # nothing dropped


def test_agent_emit_gate_routes_and_blocks_sun():
    """core.policy._emit_gate (via core.action_emitter) drops a forged strict-sun action, keeps a valid one."""
    from core import policy as mod  # the emission gate now lives in core.policy (OW-ARCH-001)

    obs = _obs()
    me = obs.get("player", 0)
    src = [p for p in obs["planets"] if p[1] == me][0]
    others = [p for p in obs["planets"] if p[1] != me]
    init = {p[0]: tuple(p) for p in obs["initial_planets"]}
    sol = G.solve_intercept(
        src[2],
        src[3],
        others[0][0],
        30,
        int(obs.get("step", 0)),
        init,
        obs.get("angular_velocity", 0.0),
    )
    sun_angle = math.atan2(G.CENTER - src[3], G.CENTER - src[2])
    forged = [[src[0], sol[0], 30], [src[0], sun_angle, 30]]
    gated = mod._emit_gate(obs, forged)
    assert [src[0], sun_angle, 30] not in gated  # sun action dropped
    assert any(mv[0] == src[0] for mv in gated)  # valid action kept


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        passed += 1
    print(f"\n{passed}/{len(fns)} action-sanitizer tests passed")
