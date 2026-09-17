"""BattlefieldState / ArrivalLedger / RuleEngine smokes (pytest or direct run)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from core.state import build_battlefield_state  # noqa: E402
from core.ledger import build_ledger  # noqa: E402
from core.features import candidate_features  # noqa: E402
from core.rule_engine import RuleEngine  # noqa: E402
from core.oracle import FlightOracle  # noqa: E402


def _run_obs(seed, step):
    from kaggle_environments import make

    env = make("orbit_wars", configuration={"seed": seed})
    env.run(["random", "random"])
    idx = step if step < len(env.steps) else len(env.steps) - 1
    return env.steps[idx][0]["observation"]


def test_state_builds_without_exceptions_on_samples():
    for seed in (12345, 777, 4242):
        for step in (0, 30, 80):
            st = build_battlefield_state(_run_obs(seed, step), horizon=60)
            assert len(st.planets) > 0
            assert st.glob.phase in ("opening", "midgame", "endgame")
            assert st.glob.my_id in st.players


def test_strategic_value_bounded_and_decomposable():
    st = build_battlefield_state(_run_obs(12345, 30), horizon=60)
    for p in st.planets.values():
        assert 1 <= p.strategic_value_1_100 <= 100
        assert set(
            [
                "prod_roi",
                "holdability",
                "frontier_leverage",
                "centrality_hubness",
                "enemy_pressure",
            ]
        ).issubset(p.value_components)


def test_ledger_projection_shape_and_consistency():
    obs = _run_obs(12345, 30)
    me = obs.get("player", 0)
    led = build_ledger(obs, horizon=50)
    for p in obs["planets"]:
        po = led.projected_owner(p[0])
        ps = led.projected_ships(p[0])
        assert len(po) == 51 and len(ps) == 51  # H+1
        assert po[0] == p[1]  # turn 0 == current owner
    # a planet we own with no incoming threat should have defense_slack <= its ships
    mine = [p for p in obs["planets"] if p[1] == me]
    if mine:
        assert led.defense_slack(mine[0][0]) <= mine[0][5] + 1e-6


def test_ledger_handfixture_capture_matches_replay_planet():
    """Hand fixture: a neutral planet with N ships, our fleet of N+ arriving at turn k,
    must flip to us by k in the projection (cross-check replay_planet)."""
    from core import geometry as G

    o, s = G.replay_planet(-1, 10.0, 0, [(3, 0, 15.0)], 6)
    assert o[2] == -1 and o[3] == 0  # neutral until turn 3, ours after
    assert s[3] == 5.0  # 15 vs 10 -> capture with 5


def test_rule_engine_blocks_sun_and_allows_clean():
    from kaggle_environments import make

    e = make("orbit_wars", configuration={"seed": 12345})
    e.reset(num_agents=2)
    obs = e.steps[0][0]["observation"]
    me = obs.get("player", 0)
    st = build_battlefield_state(obs, horizon=60)
    orc = FlightOracle()
    re = RuleEngine(orc)
    mine = [p for p in st.planets.values() if p.owner == me]
    others = [p for p in st.planets.values() if p.owner != me]
    # clean candidate -> allow (if path valid)
    cand = {
        "source": mine[0].id,
        "target": others[0].id,
        "ships": int(mine[0].ships) // 2 + 1,
    }
    feat = candidate_features(st, cand, obs, orc)
    v = re.evaluate(st, feat)
    if feat["path_valid"]:
        assert v.decision == "allow" and v.weight > 0
    # a sun-aimed "candidate": forge a feature dict flagged as sun -> must block
    sun_feat = dict(feat)
    sun_feat["path_first_hit_type"] = "sun"
    sun_feat["path_valid"] = 0
    assert re.evaluate(st, sun_feat).decision == "block"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        passed += 1
    print(f"\n{passed}/{len(fns)} state/ledger tests passed")
