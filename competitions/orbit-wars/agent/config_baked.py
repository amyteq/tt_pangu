"""Baked Orbit Wars agent config (OW-ARCH-001 config layer).

WHY this file exists, and why it is plain Python (not YAML):
  - The online Kaggle agent ships as `main.py` + `core/` + this file, and the runtime
    sandbox may not have PyYAML. So the *runtime* default profile is baked here as a
    stdlib dict — NO third-party import at agent load time.
  - The human-editable source of truth is `config/default.yaml` (+ `config/profiles/*`).
    `BAKED` below mirrors `config/profiles/current.yaml`. To change a default: edit the
    YAML, then re-bake into this dict (see `config/README.md` for the bake step).

Contract:
  - Keys are the exact `OW_*` environment-variable names the policy reads.
  - Values are the default used when the env var is unset.
  - `core.config` reads an env override first, then this baked default, then a caller
    fallback — so behavior with no `OW_*` set and no edits here is byte-identical to the
    historical inline `os.environ.get("OW_X", <default>)` defaults (golden-verified).

Only the LIVE policy knobs (core/policy.py) are centralized here. The frozen snapshots in
agent/versions/* keep their own inline defaults on purpose (self-contained reproducibility).
"""

# Profile name baked in (mirrors config/profiles/current.yaml -> `profile:`).
PROFILE = "current"  # t14-tuned v3.2 "Forecast" + B11 rotation fix; safety gates ON, hybrid OFF

# env-var name -> default value (native type drives coercion in core.config)
BAKED = {
    # --- forward-sim planner core (t14 baked, issue #87 T2-R2) ---
    "OW_PROJ_H": 26,  # forward-sim horizon (ticks)
    # --- multi-source salvo (default OFF) ---
    "OW_MULTISRC": 0,
    "OW_HOLD_MULT": 1.6,
    # --- opening expander (default OFF) ---
    "OW_OPENING": 0,
    "OW_OPENING_TURNS": 25,
    "OW_OPENING_H": 50,
    # --- T8 true co-arrival strikes (default OFF) ---
    "OW_COARRIVAL": 0,
    "OW_COARR_MAX_SRC": 4,
    "OW_COARR_HOLD": 1.0,
    "OW_COARR_TOL": 1,
    # --- T11 ledger-constrained availability (default OFF) ---
    "OW_LEDGER": 0,
    # --- v2 garrison / in-flight discipline ---
    "OW_REAR_FLOOR": 0.0,
    "OW_FRONTIER_FLOOR": 5.0,
    "OW_FRONTIER_DIST": 20.0,
    "OW_PROD_MULT": 0.0,  # GARRISON_PROD_MULT
    "OW_INFLIGHT_CAP": 1.2,
    "OW_CAP_EARLY": 3.2,
    "OW_CAP_LATE": 1.3,
    # --- 4p-aware mode (default OFF -> 2p byte-identical) ---
    "OW_4P_MODE": 0,
    "OW_4P_ATK_SCALE": 0.5,
    "OW_4P_PEACE_TURNS": 25,
    "OW_4P_RIVAL_W": 1.0,
    "OW_4P_CAP_BUMP": 0.0,
    # --- consolidation (default OFF) ---
    "OW_CONSOLIDATE": 0,
    "OW_CONSOLIDATE_MIN": 12.0,
    "OW_CONSOLIDATE_MARGIN": 3.0,
    # --- layer [6] RuleEngine guardrail/re-weight (default OFF -> pass-through) ---
    "OW_RULE_ENGINE": 0,
    # --- layer [7] emission safety gate ---
    "OW_NO_SANITIZE": 0,  # sanitizer ON unless 1
    "OW_BLOCK_WRONG_HIT": 0,  # opt-in wrong-first-hit drop
    "OW_SANITIZE_LOG": "",  # path for per-turn counters ("" = off)
    # --- layer [5] hybrid model re-ranker (default OFF) ---
    "OW_HYBRID": 0,
    "OW_HYBRID_BETA": 0.5,
    "OW_HYBRID_TOPN": 80,
}
