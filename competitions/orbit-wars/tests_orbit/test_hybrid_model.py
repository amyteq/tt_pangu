"""Hybrid model scorer compat-guard smokes (OW-ARCH-001).

The feature contract grew to 25 (added tgt_owner_is_own). The deployed hybrid_weights.json was trained
on the old 24-feature contract, so it MUST now disable cleanly (load_default -> None -> rules-only),
never silently mis-score. Feature-contract correctness is covered in test_features_contract.py.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
for _p in (COMP, os.path.join(COMP, "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.features import FEATURE_NAMES  # noqa: E402


def test_incompatible_weights_disable_cleanly():
    """The deployed 24-feature weights are incompatible with the 25-feature contract -> None."""
    from hybrid_model import load_default

    sc = load_default(os.path.join(COMP, "agent", "hybrid_weights.json"))
    assert sc is None, "stale-contract weights must disable (rules-only), not silently mis-score"


def test_missing_weights_returns_none_not_raise():
    from hybrid_model import load_default

    assert load_default(os.path.join(COMP, "agent", "does_not_exist.json")) is None


def test_compatible_weights_load_and_score():
    """A synthetic weights doc that MATCHES the current contract loads and scores in [0, 1]."""
    import json
    import tempfile

    from hybrid_model import load_default

    n = len(FEATURE_NAMES)
    doc = {
        "features": list(FEATURE_NAMES),
        "mean": [0.0] * n,
        "std": [1.0] * n,
        "layers": [{"W": [[0.0] * n], "b": [0.0]}],  # 1-layer identity-ish -> sigmoid(0)=0.5
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        path = f.name
    sc = load_default(path)
    os.unlink(path)
    assert sc is not None, "contract-matching weights should load"
    s = sc.score_cf({"tgt_owner": 1, "my_id": 0, "ships": 20})
    assert 0.0 <= s <= 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        passed += 1
    print(f"\n{passed}/{len(fns)} hybrid-model tests passed")
