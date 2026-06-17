"""Orbit Wars agent — thin Kaggle entrypoint (OW-ARCH-001).

The full layered policy lives under core/: `core.policy` orchestrates the data flow
    obs -> BattlefieldState -> ArrivalLedger/ThreatLedger -> CandidateGenerator
        -> features -> RuleEngine / (optional) model scorer -> ActionEmitter -> ActionSanitizer
built on core.geometry (single physics source) + core.oracle (FlightOracle). This file only adapts
Kaggle's agent(obs) entrypoint to that policy and guarantees a crash never forfeits (returns []).

Submission: package `agent/main.py` + `core/` (+ `agent/hybrid_model.py` + `agent/hybrid_weights.json`
when a compatible model is enabled) as a tar.gz. A bare single-file main.py without core/ is
intentionally passive (returns []) — the deployed agent always bundles core/.

IMPORTANT (why we do not use __file__ here): kaggle_environments loads an agent by
`exec(compile(raw, path), {})` — an EMPTY namespace with NO `__file__`. Touching `__file__` at
module load would raise NameError, the whole agent would fail to load, and it would go silently
passive (returns []) — which is exactly how a strong agent ends up losing to `random` in the
local arena. So we locate core/ by scanning sys.path instead (kaggle appends the agent's own
directory before exec; core/ is that dir or its parent), falling back to __file__ only when the
module IS imported normally (tests, in-process tooling).

See competitions/orbit-wars/ARCHITECTURE.md for the layer map and config/README.md for configuration.
"""

import os as _os
import sys as _sys


def _locate_core():
    """Put the directory that contains `core/policy.py` on sys.path, robustly across:
    in-process import (tests; __file__ defined), kaggle's exec({}) (no __file__; the agent dir
    is on sys.path and core/ is that dir or its parent), and the deployed tar.gz layout."""
    cands = []
    try:  # normal import / tooling context
        here = _os.path.dirname(_os.path.abspath(__file__))
        cands += [here, _os.path.dirname(here)]
    except NameError:  # kaggle exec({}) context — no __file__
        pass
    for d in list(_sys.path):  # kaggle appended the agent dir; core/ is here or one level up
        if d:
            cands += [d, _os.path.dirname(d)]
    seen = set()
    for d in cands:
        if not d or d in seen:
            continue
        seen.add(d)
        if _os.path.isfile(_os.path.join(d, "core", "policy.py")):
            if d not in _sys.path:
                _sys.path.insert(0, d)
            return True
    return False


_locate_core()


def agent(obs):
    try:
        from core.policy import get_default_policy

        return get_default_policy().act(obs)
    except Exception:
        return []
