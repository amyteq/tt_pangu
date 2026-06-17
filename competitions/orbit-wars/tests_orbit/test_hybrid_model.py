"""Hybrid model scorer + train/serve feature-contract smokes (prompt 06 integration)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
for _p in (COMP, os.path.join(COMP, "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.features import FEATURE_NAMES, feature_vector, ship_bucket_of  # noqa: E402


def test_feature_vector_shape_and_order():
    cf = {
        "ships": 30,
        "remaining_steps": 400,
        "phase": "midgame",
        "src_ships": 50,
        "tgt_owner": -1,
        "tgt_strategic_value": 42,
        "path_valid": 1,
        "path_eta": 7,
        "path_first_hit_type": "target",
    }
    vec = feature_vector(cf, ship_bucket=ship_bucket_of(30))
    assert len(vec) == len(FEATURE_NAMES) == 24
    assert all(isinstance(v, float) for v in vec)
    # neutral target -> owner_is_neutral=1, owner_is_enemy=0 (positions 8,9)
    assert vec[8] == 0.0 and vec[9] == 1.0
    # first-hit-is-target flag (last feature)
    assert vec[-1] == 1.0


def test_scorer_loads_and_scores_in_range():
    from hybrid_model import load_default

    sc = load_default(os.path.join(COMP, "agent", "hybrid_weights.json"))
    assert sc is not None, "deployed weights agent/hybrid_weights.json failed to load"
    # weights' first layer input dim must equal the feature contract
    assert len(sc.layers[0]["W"][0]) == len(FEATURE_NAMES)
    cf = {
        "ships": 20,
        "phase": "opening",
        "tgt_strategic_value": 80,
        "path_valid": 1,
        "path_first_hit_type": "target",
        "tgt_owner": 1,
    }
    s = sc.score_cf(cf, ship_bucket_of(20))
    assert 0.0 <= s <= 1.0


def test_missing_weights_returns_none_not_raise():
    from hybrid_model import load_default

    assert load_default(os.path.join(COMP, "agent", "does_not_exist.json")) is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        passed += 1
    print(f"\n{passed}/{len(fns)} hybrid-model tests passed")
