# Orbit Wars agent config (OW-ARCH-001)

Centralized configuration for the live agent (`core/policy.py`). One place reads `OW_*`
environment overrides — `core/config.py` — so knobs are no longer scattered as
`os.environ.get(...)` across the policy body.

## Files

| File | Role |
|---|---|
| `config/default.yaml` | Canonical **schema**: every knob, grouped, documented, with its default. Human reference. |
| `config/profiles/current.yaml` | The **active** profile shipped to Kaggle. A flat `OW_* → value` map under `knobs:`. |
| `config/profiles/hybrid_v0.yaml` | Example profile: enables the advisory hybrid re-ranker (`OW_HYBRID=1`). |
| `config/profiles/ladder_probe.yaml` | Example profile: enables the RuleEngine + wrong-first-hit gates (experimental). |
| `config/bake.py` | Regenerates `agent/config_baked.py` from a profile. PyYAML-free (stdlib only). |
| `agent/config_baked.py` | **Runtime** default profile as a plain-Python dict. This is what the online agent imports. |
| `core/config.py` | Resolves each knob at call time and exposes `geti/getf/getstr/getb/snapshot`. |

## Why baked Python and not YAML at runtime

The online Kaggle agent ships as `main.py` + `core/` + `agent/` and the runtime sandbox may
not have PyYAML. So the runtime default profile is **baked** into `agent/config_baked.py` as a
stdlib dict — no third-party import at agent load time. YAML stays a dev-time convenience for
humans editing/reviewing profiles.

## Resolution order (per knob, every turn)

```
1. environment variable  OW_*        (live override; read at CALL time)
2. baked default profile             (agent/config_baked.py BAKED)
3. call-site literal                 (the default kept inline in core/policy.py as a safety net)
```

Reading at call time matters: the arena worker pool clears `OW_*` per task and reuses workers,
so a cached module must re-read env each turn. If the baked profile fails to import for any
reason, the getters fall back to the inline literal, so the agent can never break on config.

**Behavior preservation:** with no `OW_*` set and `BAKED` == the historical inline defaults, the
getters return byte-identical values to the old `int(os.environ.get("OW_X", <default>))`
expressions. This is golden-verified (526-record obs→moves replay, 0 mismatches) and contract-
checked (`config/bake.py --check` + the resolution test).

## Editing a profile

1. Edit `config/profiles/current.yaml` (or add `config/profiles/<name>.yaml`).
2. Re-bake: `python config/bake.py [--profile <name>]` → rewrites `agent/config_baked.py`.
3. Verify no drift: `python config/bake.py --check`.
4. Golden-verify behavior is still intended (see `competitions/orbit-wars/README.md`).

`python config/bake.py --check` is cheap and stdlib-only; run it before any PR that touches
config so the YAML and the baked Python can never silently diverge.

## Scope

Only the **live** policy knobs (`core/policy.py`, 32 knobs) are centralized here. The frozen
agent snapshots in `agent/versions/*` keep their own inline `os.environ.get` defaults on purpose
— each is a self-contained reproducible artifact and must not change when a profile changes.

Knobs not yet migrated (experimental levers that only ever lived in `agent/versions/*`, e.g.
`OW_V4*`, `OW_EM*`, `OW_SUPPLY*`, `OW_POSTURE*`, `OW_STUDENT_*`) are intentionally out of scope:
they are not read by the live policy. If one is ever promoted into `core/policy.py`, add it to
`config/profiles/current.yaml`, re-bake, and route the read through `core.config`.
