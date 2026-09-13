"""Config-layer contract (OW-ARCH-001): core.config resolves env -> baked -> fallback, the
baked profile actually loads, env overrides win and coerce, and the baked Python matches the
YAML profile (no silent drift)."""

import os
import sys

for _k in list(os.environ):
    if _k.startswith("OW_"):
        del os.environ[_k]
HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
for _p in (COMP, os.path.join(COMP, "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import config as C  # noqa: E402


def test_baked_profile_loads_not_empty():
    baked = C.baked()
    assert baked, "BAKED failed to import -> getters would silently use only call-site fallbacks"
    assert "OW_PROJ_H" in baked and baked["OW_PROJ_H"] == 26


def test_resolution_matches_historical_inline_defaults():
    # a representative spread across int / float / str knobs
    assert C.geti("OW_PROJ_H", 26) == 26
    assert C.geti("OW_MULTISRC", 0) == 0
    assert C.getf("OW_HOLD_MULT", 1.6) == 1.6
    assert C.getf("OW_CAP_EARLY", 3.2) == 3.2
    assert C.getf("OW_FRONTIER_DIST", 20.0) == 20.0
    assert C.geti("OW_RULE_ENGINE", 0) == 0
    assert C.geti("OW_NO_SANITIZE", 0) == 0
    assert C.getstr("OW_SANITIZE_LOG", "") == ""


def test_env_override_wins_and_coerces_then_clears():
    os.environ["OW_PROJ_H"] = "40"
    os.environ["OW_HOLD_MULT"] = "2.5"
    try:
        assert C.geti("OW_PROJ_H", 26) == 40
        assert C.getf("OW_HOLD_MULT", 1.6) == 2.5
        assert C.getb("OW_PROJ_H") is True  # non-zero
    finally:
        del os.environ["OW_PROJ_H"]
        del os.environ["OW_HOLD_MULT"]
    assert C.geti("OW_PROJ_H", 26) == 26, "override leaked after unset"


def test_active_overrides_and_snapshot():
    os.environ["OW_HYBRID"] = "1"
    try:
        assert C.active_overrides() == {"OW_HYBRID": "1"}
    finally:
        del os.environ["OW_HYBRID"]
    snap = C.snapshot()
    assert set(snap) == set(C.baked()), "snapshot must cover exactly the baked knobs"


def test_baked_python_matches_yaml_profile():
    # the runtime baked dict must equal what config/profiles/current.yaml bakes to (no drift)
    sys.path.insert(0, os.path.join(COMP, "config"))
    import bake  # config/bake.py

    _profile, knobs = bake.parse_profile(os.path.join(COMP, "config", "profiles", "current.yaml"))
    from config_baked import BAKED

    assert dict(knobs) == dict(BAKED), "agent/config_baked.py drifted from config/profiles/current.yaml"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    n = 0
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
        n += 1
    print(f"\n{n}/{len(fns)} config-layer tests passed")
