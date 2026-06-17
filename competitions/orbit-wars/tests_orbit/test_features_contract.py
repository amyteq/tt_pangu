"""Feature contract tests (OW-ARCH-001): stable length/schema + own/enemy/neutral ownership."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from core.features import FEATURE_NAMES, feature_vector, ship_bucket_of  # noqa: E402


def _flags(owner, me):
    v = feature_vector({"tgt_owner": owner, "my_id": me, "ships": 10})
    i = (
        FEATURE_NAMES.index("tgt_owner_is_own"),
        FEATURE_NAMES.index("tgt_owner_is_enemy"),
        FEATURE_NAMES.index("tgt_owner_is_neutral"),
    )
    return (v[i[0]], v[i[1]], v[i[2]])


def test_vector_length_is_stable_and_floats():
    v = feature_vector({"tgt_owner": -1, "my_id": 0, "ships": 5}, ship_bucket=ship_bucket_of(5))
    assert len(v) == len(FEATURE_NAMES)
    assert all(isinstance(x, float) for x in v)


def test_schema_exposes_own_enemy_neutral():
    for name in ("tgt_owner_is_own", "tgt_owner_is_enemy", "tgt_owner_is_neutral"):
        assert name in FEATURE_NAMES, name


def test_ownership_flags_distinguish_own_enemy_neutral():
    # owner == me -> OWN (not enemy); owner != me and != -1 -> ENEMY; owner == -1 -> NEUTRAL
    assert _flags(2, 2) == (1.0, 0.0, 0.0), "own planet must NOT be flagged enemy"
    assert _flags(1, 2) == (0.0, 1.0, 0.0)
    assert _flags(-1, 2) == (0.0, 0.0, 1.0)
    # exactly one of the three is set
    for owner in (2, 1, -1):
        assert sum(_flags(owner, 2)) == 1.0


def test_missing_fields_degrade_safely():
    # empty cf must not crash and must still produce a full-length numeric vector
    v = feature_vector({})
    assert len(v) == len(FEATURE_NAMES)
    assert all(isinstance(x, float) for x in v)
    # missing my_id -> own cannot be asserted; must not crash and must not be flagged own
    own_i = FEATURE_NAMES.index("tgt_owner_is_own")
    assert feature_vector({"tgt_owner": 3, "ships": 1})[own_i] == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} features-contract tests passed")
