"""Policy smoke tests (OW-ARCH-001): the thin entrypoint runs the layered policy, returns valid
sanitized actions, never crashes on a minimal obs, and the opt-in wrong-first-hit gate works."""

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

from core.oracle import FlightOracle  # noqa: E402


def _real_obs():
    import logging

    logging.disable(logging.INFO)
    from kaggle_environments import make

    env = make("orbit_wars", configuration={"seed": 31337})
    env.reset(num_agents=2)
    # advance a few steps so fleets/positions are non-trivial
    env.run(["do_nothing", "do_nothing"]) if False else None
    return env.steps[0][0]["observation"]


def test_agent_returns_valid_action_list():
    import main as entry  # the thin agent/main.py shim

    moves = entry.agent(_real_obs())
    assert isinstance(moves, list)
    for mv in moves:
        assert isinstance(mv, (list, tuple)) and len(mv) == 3
        int(mv[0])
        float(mv[1])
        int(mv[2])  # well-formed [src, angle, ships]


def test_no_crash_on_minimal_obs():
    import main as entry

    assert entry.agent({}) == []  # empty obs -> passive, never crash
    minimal = {
        "planets": [],
        "fleets": [],
        "initial_planets": [],
        "angular_velocity": 0.0,
        "step": 0,
        "comet_planet_ids": [],
        "player": 0,
    }
    assert entry.agent(minimal) == []  # no planets -> no moves


def test_emitted_actions_are_sanitized_no_sun_oob():
    import main as entry

    obs = _real_obs()
    orc = FlightOracle()
    for mv in entry.agent(obs):
        r = orc.first_hit(obs, int(mv[0]), float(mv[1]), int(mv[2]))
        assert r.first_hit_type not in ("sun", "oob"), (mv, r.first_hit_type)


def test_main_loads_and_acts_under_kaggle_exec_no_dunder_file():
    """REGRESSION (OW-ARCH-001): kaggle_environments loads an agent via exec(compile(raw, path), {})
    — an EMPTY namespace with NO __file__. main.py must locate core/ without touching __file__ at
    module load, or the whole agent fails to load and goes silently passive (returns []) — which is
    how a strong agent ends up losing to `random`. The golden (in-process) harness cannot catch this
    because __file__ exists there. This test reproduces the exact exec path and asserts the agent
    both loads AND produces at least one move within the opening (proving core.policy was imported)."""
    import logging

    logging.disable(logging.INFO)
    from kaggle_environments import make

    agent_dir = os.path.join(COMP, "agent")
    main_path = os.path.join(agent_dir, "main.py")
    if agent_dir not in sys.path:
        sys.path.append(agent_dir)  # kaggle appends the agent dir before exec; core/ is its parent
    with open(main_path) as f:
        raw = f.read()
    ns = {}  # exactly what kaggle_environments.agent.get_last_callable does
    exec(compile(raw, main_path, "exec"), ns)  # must NOT raise NameError on __file__
    loaded = [v for v in ns.values() if callable(v)][-1]  # kaggle picks the last callable
    assert loaded.__name__ == "agent", loaded.__name__

    env = make("orbit_wars", configuration={"seed": 4000})
    env.reset(num_agents=2)
    acted = False
    for _ in range(15):
        obs = env.steps[-1][0]["observation"]
        mv = loaded(obs)
        assert isinstance(mv, list)
        if mv:
            acted = True
        env.step([mv, []])
    assert acted, "agent loaded under exec({}) but never acted -> core.policy import is failing (passive)"


def test_wrong_first_hit_blocked_when_enabled():
    """With OW_BLOCK_WRONG_HIT=1, the emission gate drops a move whose first hit != intended target."""
    from core import policy

    # static lane: source@(10,50), real first-hit planet @ (35,50) id=1, but claim intended target id=2
    obs = {
        "planets": [
            [0, 0, 10.0, 50.0, 2.0, 50.0, 3],
            [1, -1, 35.0, 50.0, 2.0, 5.0, 2],
            [2, -1, 80.0, 20.0, 2.0, 5.0, 2],
        ],
        "fleets": [],
        "initial_planets": [
            [0, 0, 10.0, 50.0, 2.0, 50.0, 3],
            [1, -1, 35.0, 50.0, 2.0, 5.0, 2],
            [2, -1, 80.0, 20.0, 2.0, 5.0, 2],
        ],
        "angular_velocity": 0.0,
        "step": 5,
        "comet_planet_ids": [],
        "player": 0,
    }
    move = [0, 0.0, 30]  # angle 0 -> first hit is planet 1, NOT the claimed target 2
    try:
        policy._BLOCK_WRONG_HIT = True
        kept = policy._emit_gate(obs, [move], targets=[2])
        assert kept == [], kept  # wrong-first-hit dropped
        kept_ok = policy._emit_gate(obs, [move], targets=[1])
        assert kept_ok == [move], kept_ok  # correct intended target kept
    finally:
        policy._BLOCK_WRONG_HIT = False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} policy-smoke tests passed")
