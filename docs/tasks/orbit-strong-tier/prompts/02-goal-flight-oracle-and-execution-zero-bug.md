---
id: OW-P0-FLIGHT-ORACLE-001
title: Build FlightOracle and zero-bug execution layer for Orbit Wars
kind: claude-code-task
status: ready
scope: competition-foundation-code-and-tests
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: none
allowed_paths:
  - competitions/orbit-wars/**
  - docs/tasks/competition-tracking/orbit-strong-tier/**
forbidden_paths:
  - .kca/**
  - tools/**
  - src/**
  - services/**
  - supabase/**
  - ui/**
  - tests/**
  - .github/workflows/**
  - .env
  - .env.*
  - kaggle.json
  - .kaggle/kaggle.json
  - secrets/**
---

# Task: Build FlightOracle and zero-bug execution layer for Orbit Wars

## Mission

Implement a deterministic FlightOracle / execution-safety layer that every rules/model/hybrid strategy can rely on.

This is P0. Do not start model integration until this substrate exists.

## Read first

- `competitions/orbit-wars/agent/main.py`
- `competitions/orbit-wars/agent/utils.py`
- `competitions/orbit-wars/agent/versions/v4.py`
- `competitions/orbit-wars/arena/distill_prep.py`
- `competitions/orbit-wars/ops/episode_analyze.py`
- `competitions/orbit-wars/rules.md`
- `competitions/orbit-wars/bugs.md`
- `competitions/orbit-wars/tasks.md`
- `competitions/orbit-wars/tracking.md`
- example replay if present: `competitions/orbit-wars/replays/79228928.json` or external fixture path referenced by docs

## Problem to solve

Current path checks and target decode are spread across multiple files. Some checks are cheap/static and may miss:

- moving planet first-hit mismatch;
- landing target miscalculation;
- strict sun collision vs near-sun warning;
- out-of-bounds fleet loss;
- comet path interference;
- non-target planet hit before intended target.

The final action emitter should not emit actions unless the deterministic oracle predicts the first hit is the intended target or a documented safe exception.

## Desired architecture

Create or update these modules, preserving existing working code where possible:

```text
competitions/orbit-wars/core/__init__.py
competitions/orbit-wars/core/geometry.py
competitions/orbit-wars/core/oracle.py
competitions/orbit-wars/core/action_sanitizer.py
competitions/orbit-wars/tests_orbit/test_flight_oracle.py
competitions/orbit-wars/tests_orbit/fixtures/README.md
```

If the repo already has an equivalent location, use that instead and document the mapping.

## FlightOracle API

Implement an API similar to:

```python
@dataclass
class FlightResult:
    valid: bool
    first_hit_type: str      # target | friendly | enemy | neutral | comet | sun | oob | none | unknown
    first_hit_id: int | None
    eta: int | None
    min_sun_distance: float | None
    path_ticks: int
    source_planet_id: int
    intended_target_id: int | None
    ships: int
    angle: float
    reason: str

class FlightOracle:
    def first_hit(self, obs, source_planet_id, angle, ships, horizon=120) -> FlightResult: ...
    def validate_target(self, obs, source_planet_id, target_id, ships, horizon=120) -> FlightResult: ...
```

Rules:

- Use engine-equivalent position updates and swept collision where possible.
- Distinguish `strict_sun_collision` from `near_sun_warning`.
- Use `agent/utils.py` or `arena/distill_prep.py` proven logic if available, but centralize final logic.
- Treat comets conservatively if exact comet modeling is incomplete; document blocker.
- Never silently emit a risky action.

## Integration

Replace final action validation in `agent/main.py` or a minimal wrapper so that candidate actions pass through:

```text
candidate -> FlightOracle -> ActionSanitizer -> emit or block with reason
```

Keep a cheap prefilter if useful, but final emission must use the oracle.

Add debug counters, disabled by default online:

```text
blocked_sun
blocked_oob
blocked_wrong_first_hit
blocked_no_target
emitted_valid
```

## Tests

Add tests/smoke fixtures:

- `test_oracle_imports_and_handles_empty_obs`
- `test_first_hit_target_validation_smoke`
- `test_strict_sun_collision_vs_near_sun_warning`
- `test_wrong_first_hit_target_is_blocked`
- `test_agent_final_actions_pass_oracle_on_sample_seeds`
- `test_replay_79228928_decode_smoke` if fixture exists or can be referenced

Do not commit large replay JSONs. Use compact fixture slices if needed.

## Validation commands

Run:

```bash
python -m py_compile competitions/orbit-wars/agent/main.py
python -m py_compile competitions/orbit-wars/core/*.py
python -m py_compile competitions/orbit-wars/ops/*.py
python competitions/orbit-wars/arena/validate.py --games 10 --procs 4
python competitions/orbit-wars/arena/suite_gate.py main --games 12 --procs 4
```

If there is a local test runner for `tests_orbit`, run it. Otherwise run the test file directly if possible.

## Documentation updates

Update:

```text
competitions/orbit-wars/bugs.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/VALIDATION.md
competitions/orbit-wars/insights.md
```

Mark any old pathing/landing bug as fixed only if tests pass.

## Acceptance criteria

- A centralized FlightOracle exists.
- Final actions are gated by FlightOracle / ActionSanitizer.
- Strict sun collision, near-sun warning, OOB, and wrong-first-hit are distinguishable.
- Regression tests/smokes exist.
- Existing arena gates run or blockers are documented.
- No model integration is required for this task.
- No Kaggle remote write is performed.
- No secrets are read.

## Stop conditions

Stop if:

- engine-equivalent collision cannot be implemented without more rule evidence;
- candidate action generation would need a full rewrite beyond this task;
- tests expose a severe unresolved mismatch that should be fixed before continuing;
- changes would touch forbidden paths.

## Final response requirements

Report:

- new modules/classes;
- safety semantics;
- integration points;
- tests added;
- validation results;
- remaining known mismatches;
- next tasks.
