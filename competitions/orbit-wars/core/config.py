"""Centralized config + env-override resolution (OW-ARCH-001 config layer).

Single place that reads `OW_*` environment overrides, so the policy no longer scatters
`os.environ.get(...)` across its body. Resolution order for every knob:

    1. environment variable `OW_*`  (live override; read at CALL time)
    2. baked default profile          (agent/config_baked.py BAKED -> from config/*.yaml)
    3. caller fallback                (the literal kept at the call site as a safety net)

Design constraints:
  - NO third-party import (PyYAML stays a dev-only tool). The baked profile is plain Python.
  - Reading at call time matters: the arena worker pool clears `OW_*` per task and reuses
    workers, so a cached module must re-read env each turn (same reason `_hybrid_cfg` did).
  - Behavior-preserving: with no `OW_*` set and BAKED == the historical inline defaults, the
    getters return byte-identical values to the old `int(os.environ.get("OW_X", <default>))`
    expressions (golden-verified). If the baked profile fails to import, getters fall back to
    the caller-supplied default, so the agent can never break on a config problem.
"""

import os as _os


def _load_baked():
    """Best-effort import of the baked profile. Tries the package path, then the flat
    agent/ sys.path layout the online agent uses. Any failure -> empty (caller fallbacks win)."""
    try:
        from agent.config_baked import BAKED  # when comp root is importable as a package

        return dict(BAKED)
    except Exception:
        pass
    try:
        import sys as _sys

        _here = _os.path.dirname(_os.path.abspath(__file__))  # core/
        _comp = _os.path.dirname(_here)
        _agent = _os.path.join(_comp, "agent")
        if _agent not in _sys.path:
            _sys.path.insert(0, _agent)
        from config_baked import BAKED  # flat layout: agent/ on sys.path

        return dict(BAKED)
    except Exception:
        return {}


_BAKED = _load_baked()


def _raw(name, default):
    """env override (string) -> baked default -> caller fallback, un-coerced."""
    v = _os.environ.get(name)
    if v is not None:
        return v
    if name in _BAKED:
        return _BAKED[name]
    return default


def geti(name, default=0):
    """Resolve an integer knob (mirrors the old int(os.environ.get(name, default)))."""
    return int(_raw(name, default))


def getf(name, default=0.0):
    """Resolve a float knob (mirrors the old float(os.environ.get(name, default)))."""
    return float(_raw(name, default))


def getstr(name, default=""):
    """Resolve a string knob (mirrors the old os.environ.get(name, default))."""
    v = _raw(name, default)
    return v if isinstance(v, str) else str(v)


def getb(name, default=False):
    """Resolve a 1/0 boolean knob (truthy iff the resolved int is non-zero)."""
    return geti(name, 1 if default else 0) != 0


def baked():
    """A copy of the baked default profile (for docs / logging)."""
    return dict(_BAKED)


def active_overrides():
    """The subset of baked `OW_*` knobs currently overridden by the environment.
    Useful for per-run audit logging — never includes anything not in the baked profile."""
    return {k: _os.environ[k] for k in _BAKED if k in _os.environ}


def snapshot():
    """Fully-resolved current values for every baked knob (env applied), as native types.
    Coercion follows the baked default's type (int/float/str)."""
    out = {}
    for k, dv in _BAKED.items():
        if isinstance(dv, bool):
            out[k] = getb(k, dv)
        elif isinstance(dv, int):
            out[k] = geti(k, dv)
        elif isinstance(dv, float):
            out[k] = getf(k, dv)
        else:
            out[k] = getstr(k, dv if isinstance(dv, str) else str(dv))
    return out
