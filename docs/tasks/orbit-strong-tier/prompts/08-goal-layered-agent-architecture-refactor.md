---
id: OW-ARCH-001
title: Refactor Orbit Wars agent into layered core architecture
kind: claude-code-task
status: ready
scope: orbit-wars-code-refactor
competition_slug: orbit-wars
target_dir: competitions/orbit-wars
canonical_language: English
remote_side_effects: forbidden
created: 2026-06-17

allowed_paths:
  - competitions/orbit-wars/**
  - docs/tasks/orbit-strong-tier/prompts/08-goal-layered-agent-architecture-refactor.md

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

# Task: Refactor Orbit Wars agent into layered core architecture

## Mission

Refactor the Orbit Wars agent code under `competitions/orbit-wars/` so the online agent follows a clean layered data flow:

```text
[0] Physics primitives
      ↓
[1] State perception
      ↓
[2] Projection / ledger
      ↓
[3] Candidate generation
      ↓
[4] Feature extraction
      ↓
[5] Model scorer
      ↓
[6] Rule engine
      ↓
[7] Flight oracle + action sanitizer + action emitter
      ↓
Kaggle actions
````

The goal is to reduce duplicated physics/geometry logic, make final action safety target-aware, fix likely in-flight fleet target decoding issues, and prepare the architecture for hybrid model/rule-based development.

This is a code architecture refactor and correctness hardening task.

Do not run Kaggle submit.
Do not push Kaggle kernels.
Do not upload Kaggle datasets.
Do not modify KCA core.
Do not touch credentials.

## Read first

Read these files before editing:

* `CLAUDE.md`
* `README.md`
* `PROJECT_STATE.md` if present
* `competitions/orbit-wars/README.md`
* `competitions/orbit-wars/ARCHITECTURE.md` if present
* `competitions/orbit-wars/VALIDATION.md` if present
* `competitions/orbit-wars/LEAGUE.md` if present
* `competitions/orbit-wars/tasks.md`
* `competitions/orbit-wars/tracking.md`
* `competitions/orbit-wars/bugs.md`
* `competitions/orbit-wars/rules.md`
* `competitions/orbit-wars/agent/main.py`
* `competitions/orbit-wars/agent/utils.py` if present
* `competitions/orbit-wars/core/*.py`
* `competitions/orbit-wars/datasets/*.py`
* `competitions/orbit-wars/models/*.py`
* `competitions/orbit-wars/ops/*.py`

Also inspect a small replay fixture if present:

* `competitions/orbit-wars/fixtures/79228928*.json`
* `competitions/orbit-wars/replays/79228928*.json`
* any local copy of `79228928` referenced by docs

If the replay fixture is not present, do not block the entire refactor. Create tests that can run without it, and document that replay-based regression tests are pending fixture availability.

## Non-goals

Do not:

* implement a new high-level strategy;
* train models;
* rebuild the replay dataset;
* run long arena sweeps;
* run live ladder loops;
* submit to Kaggle;
* push Kaggle kernels;
* edit credentials;
* modify `.kca/skills`, KCA core, repo CI, GitHub workflows, or non-Orbit product code;
* close or update GitHub issues.

This task should preserve current strategy behavior as much as possible, except where a safety/correctness bug is clearly fixed.

## Current concerns to address

The current code appears to have these architecture risks:

1. `agent/main.py` is too monolithic and contains policy logic, geometry, projection, path checking, candidate generation, scoring, and action emission in one file.
2. `agent/main.py`, `agent/utils.py`, and `core/geometry.py` likely duplicate physics/geometry primitives.
3. Existing in-flight fleet decoding may be wrong if it replays a fleet from its source planet instead of tracing from the fleet's current `(x, y)` position.
4. Final action sanitizer may not receive intended target metadata, so it cannot reliably block wrong-first-hit or landing-target mismatch.
5. `core/rule_engine.py` may exist but not be integrated into the main decision flow.
6. `core/features.py` may have insufficient or incorrect ownership features, especially distinguishing own, enemy, and neutral targets.
7. Environment variables are useful for arena sweeps, but long-term configuration should be layered and reproducible.
8. Runtime agent should not depend on non-stdlib YAML parsing inside Kaggle.

## Target architecture

Normalize toward this structure:

```text
competitions/orbit-wars/
  agent/
    main.py
    config_baked.py
    hybrid_model.py
    hybrid_weights.json

  config/
    README.md
    default.yaml
    profiles/
      current.yaml
      hybrid_v0.yaml
      ladder_probe.yaml

  core/
    geometry.py
    config.py
    state.py
    ledger.py
    candidates.py
    valuation.py
    features.py
    hybrid_model.py        # optional only if cleaner than agent/hybrid_model.py
    rule_engine.py
    oracle.py
    action_sanitizer.py
    action_emitter.py
    policy.py

  tests/
    test_geometry_oracle.py
    test_state_fleet_decode.py
    test_features_contract.py
    test_policy_smoke.py
```

Use this structure as guidance. Do not create unnecessary files if the existing repo already has better names. Prefer small, cohesive modules.

## Layer responsibilities

### [0] Physics primitives — `core/geometry.py`

This must be the single source of truth for low-level mechanics:

* constants;
* `fleet_speed`;
* planet position prediction;
* segment-point distance;
* swept collision;
* combat resolution;
* intercept solving;
* simple projection helpers if already present.

Do not keep independent implementations of these primitives in `agent/main.py` or `agent/utils.py`.

Allowed compatibility:

* `agent/utils.py` may remain as a thin wrapper importing from `core.geometry`.
* It must not keep separate implementations.

### [1] State perception — `core/state.py`

Responsibilities:

* parse raw Kaggle observation;
* build `BattlefieldState`;
* build `PlanetState`;
* build `FleetState`;
* build `PlayerState`;
* build `GlobalState`;
* compute basic derived state;
* decode existing fleets using the flight oracle from the fleet's current position, not by relaunching from source planet.

Required fix:

Add or use a method similar to:

```python
FlightOracle.trace_from_position(obs, x, y, angle, ships, owner=None, horizon=120)
FlightOracle.decode_existing_fleet(obs, fleet_row, horizon=120)
```

Then update `core/state.py` so in-flight fleet target/ETA/path safety are based on current fleet position.

### [2] Projection / ledger — `core/ledger.py`

Responsibilities:

* arrival schedules;
* projected owner/ships;
* defense slack;
* incoming friendly/enemy pressure;
* source safety after launch;
* future threat windows.

Keep ledger independent from candidate ranking. Ledger may depend on `BattlefieldState` and `FlightOracle`.

### [3] Candidate generation — `core/candidates.py`

Create a typed candidate representation if missing.

Suggested dataclass:

```python
@dataclass
class CandidateAction:
    source_id: int
    target_id: int
    angle: float
    ships: int
    eta: int | None = None
    candidate_type: str = "unknown"  # expand | attack | defend | reinforce | supply | comet | bank | unknown
    base_value: float = 0.0
    reason: str = ""
    features: dict | None = None
    rule_weight: float = 1.0
    model_score: float | None = None
    final_score: float = 0.0
```

Candidate generation should:

* produce candidate actions with intended target IDs;
* use cheap filters if useful;
* avoid final path authority decisions;
* leave final first-hit validation to FlightOracle / ActionSanitizer.

### [4] Feature extraction — `core/features.py`

Feature extraction should use:

* `BattlefieldState`;
* `ArrivalLedger`;
* `CandidateAction`;
* `FlightOracle`;
* replay-derived schema assumptions.

Required fix:

Target ownership features must distinguish:

```text
target_is_own
target_is_enemy
target_is_neutral
```

Do not encode `target owner != -1` as enemy.

Feature extraction should include or prepare for:

* source ships;
* source production;
* source defense slack;
* source remaining ships after launch;
* target owner class;
* target production;
* target ships;
* target strategic value;
* distance;
* ETA;
* fleet speed;
* path validity;
* first-hit target match;
* min sun distance;
* projected target ships/owner at ETA when available;
* player count;
* 2p vs 4p;
* phase / remaining turns.

Do not overbuild the full model feature stack in this task. The goal is a clean, correct v1 feature contract.

### [5] Model scorer

The model scorer should remain advisory.

Rules:

* Do not train a model in this task.
* Do not require PyTorch or numpy in Kaggle runtime.
* If model weights are missing or disabled, policy must still work.
* Online model inference should be pure Python / stdlib unless already proven otherwise.
* The model should score candidates, not directly emit raw angles.

### [6] Rule engine — `core/rule_engine.py`

Integrate the rule engine into the candidate scoring/filtering path.

Rule engine may:

* block unsafe or strategically invalid candidates;
* downweight risky candidates;
* upweight tactical opportunities;
* produce human-readable reasons.

It should not duplicate physics validation. Use FlightOracle for physics.

Expected flow:

```text
candidate
  → features
  → rule_engine verdict
  → optional model score
  → final candidate score
```

### [7] Oracle + sanitizer + emitter

`core/oracle.py`:

* authoritative final path/first-hit/sun/OOB checker;
* supports launch-from-source and trace-from-current-position;
* distinguishes hard sun collision from near-sun warning.

`core/action_sanitizer.py`:

* validates final actions;
* receives intended target IDs;
* blocks wrong-first-hit when configured;
* blocks sun/OOB invalid actions.

`core/action_emitter.py`:

* converts selected `CandidateAction` objects into Kaggle action lists;
* passes both actions and intended targets into the sanitizer;
* returns final `[[source_id, angle, ships], ...]`.

Required change:

Final emission must preserve target intent until the last step. Do not reduce candidates to raw action lists before safety validation.

## `agent/main.py` target

Refactor `agent/main.py` into a thin Kaggle entrypoint.

Target shape:

```python
def agent(obs):
    try:
        from core.policy import get_default_policy
        return get_default_policy().act(obs)
    except Exception:
        return []
```

Exact implementation may vary, but `agent/main.py` should no longer contain duplicated physics, projection, path checking, candidate generation, feature extraction, or final action validation.

Preferred line count target:

```text
agent/main.py <= 120 lines
```

If this cannot be safely achieved in one pass, reduce it substantially and document the remaining monolith sections in the final report.

## Configuration policy

Move toward layered YAML configuration, but keep Kaggle runtime stdlib-safe.

Create or update:

```text
competitions/orbit-wars/config/README.md
competitions/orbit-wars/config/default.yaml
competitions/orbit-wars/config/profiles/current.yaml
competitions/orbit-wars/agent/config_baked.py
competitions/orbit-wars/core/config.py
```

Rules:

* YAML is the human source of truth.
* Online Kaggle agent must not require `PyYAML`.
* Bake selected config into `agent/config_baked.py` or a stdlib JSON file.
* Environment variables may remain as local/arena overrides.
* Arena sweeps may continue to use `OW_*` env vars.
* The policy should centralize env override handling in `core/config.py`, not scatter `os.environ.get(...)` across `main.py`.

Do not migrate every historical knob if doing so risks behavior regression. Migrate enough to establish the pattern and remove direct config sprawl from `main.py`.

## Data flow contract

Implement or document this flow in `core/policy.py`:

```text
obs
  → load_config()
  → BattlefieldState.from_obs(obs)
  → ArrivalLedger / ThreatLedger
  → CandidateGenerator.generate(state, ledger)
  → candidate_features(state, ledger, candidate, oracle)
  → RuleEngine.evaluate(...)
  → optional HybridModel.score(...)
  → Scheduler / selector
  → ActionEmitter.emit(obs, selected_candidates)
  → ActionSanitizer.sanitize(actions, intended_targets)
  → Kaggle action list
```

If a separate scheduler module already exists, reuse it. Otherwise keep selection simple and local in `core/policy.py` for this refactor.

## Compatibility requirements

Preserve existing agent behavior as much as possible.

* Existing local arena commands should still work.
* Existing `OW_*` arena override workflows should continue to work where practical.
* If an old env var is replaced by config, document the mapping.
* Existing hybrid model weights should not break import.
* If model loading fails, fallback to rules-only policy.
* If a candidate fails final FlightOracle validation, it must be dropped rather than emitted.

## Tests to add or update

Create or update tests under:

```text
competitions/orbit-wars/tests/
```

Required tests:

### `test_geometry_oracle.py`

Cover:

* `fleet_speed`;
* sun collision vs near-sun warning;
* OOB detection;
* first-hit target validation;
* trace from source;
* trace from current fleet position.

### `test_state_fleet_decode.py`

Cover:

* `BattlefieldState` builds from a minimal observation;
* in-flight fleet decoding uses current fleet position;
* decoded first-hit / ETA are stable for a known synthetic case.

### `test_features_contract.py`

Cover:

* feature vector length is stable;
* feature names/schema are stable if names are exposed;
* target ownership flags distinguish own / enemy / neutral;
* missing model/ledger fields degrade safely.

### `test_policy_smoke.py`

Cover:

* `agent.main.agent(obs)` returns a valid list;
* policy does not crash on minimal valid obs;
* final actions are sanitized;
* wrong-first-hit candidates are blocked in a synthetic case if possible.

If existing tests use another layout or command, adapt to repo convention.

## Validation commands

Run lightweight checks first:

```bash
git status --short
git diff --stat
git diff --name-status
find competitions/orbit-wars -maxdepth 4 -type f | sort
python -m py_compile competitions/orbit-wars/agent/main.py
python -m py_compile competitions/orbit-wars/core/*.py
```

If tests are present or added:

```bash
python -m pytest competitions/orbit-wars/tests -q
```

Run local Orbit validation if available:

```bash
python competitions/orbit-wars/arena/validate.py --games 10 --procs 4
python competitions/orbit-wars/arena/suite_gate.py main --games 12 --procs 4
```

If these arena commands are missing or incompatible, run the closest documented commands from `VALIDATION.md` and explain the substitution.

Do not run long sweeps.
Do not run model training.
Do not run live ladder loop.
Do not run Kaggle submit or push.

## Documentation updates

Update docs only as needed:

* `competitions/orbit-wars/ARCHITECTURE.md`
* `competitions/orbit-wars/README.md`
* `competitions/orbit-wars/tracking.md`
* `competitions/orbit-wars/tasks.md`
* `competitions/orbit-wars/bugs.md`
* `competitions/orbit-wars/config/README.md`

Record:

* the new 8-layer architecture;
* module responsibilities;
* config policy;
* env override policy;
* remaining migration tasks;
* known limitations.

If this task fixes a known bug, update `bugs.md`.

If this task creates follow-up tasks, use the next available task IDs in `tasks.md` and `tracking.md`.

## Process

1. Run `git status --short`.

   * Stop if unrelated uncommitted changes exist.
2. Read required docs and current code.
3. Create a short internal refactor plan:

   * current files;
   * target modules;
   * move map;
   * behavior-preservation risks.
4. Implement P0 correctness fixes:

   * FlightOracle current-position tracing;
   * state fleet decode fix;
   * intended-target-preserving action emission;
   * sanitizer wrong-first-hit gate;
   * feature target ownership flags.
5. Deduplicate physics:

   * make `core/geometry.py` the single source;
   * convert `agent/utils.py` to wrappers or remove duplicated implementations;
   * remove geometry copies from `agent/main.py`.
6. Split `main.py`:

   * create `core/policy.py`;
   * create `core/candidates.py`;
   * create `core/action_emitter.py`;
   * wire state, ledger, candidates, features, rule engine, model scorer, and sanitizer.
7. Add minimal layered config:

   * YAML source files;
   * stdlib-safe baked config;
   * env overrides centralized in `core/config.py`.
8. Add or update tests.
9. Run validation commands.
10. Update docs.
11. Final report.

## Acceptance criteria

This task is complete when all are true:

* `agent/main.py` is a thin entrypoint or substantially reduced, with remaining monolith debt documented.
* `core/geometry.py` is the single source for physics/geometry primitives.
* `agent/utils.py`, if present, is a thin wrapper or no longer duplicates physics logic.
* `FlightOracle` supports tracing from current fleet position.
* `core/state.py` decodes in-flight fleets from current fleet position, not by relaunching from source planet.
* Final action emission preserves intended target IDs until sanitizer validation.
* `ActionSanitizer` can block wrong-first-hit / landing-target mismatch when intended targets are provided.
* `core/features.py` distinguishes own/enemy/neutral target ownership correctly.
* `core/rule_engine.py` participates in candidate filter/score flow.
* A `CandidateAction` or equivalent typed object exists.
* `core/policy.py` or equivalent orchestrates the layered data flow.
* YAML config source files exist.
* Online runtime does not require `PyYAML`.
* Environment override handling is centralized or substantially centralized.
* Added/updated tests cover oracle, state fleet decode, features, and policy smoke.
* `python -m py_compile` passes for agent/core code.
* Orbit tests pass, or any failures are clearly documented as pre-existing or blocked.
* A small local arena validation is run if available.
* Documentation is updated to describe the architecture and remaining tasks.
* No Kaggle submit/push/upload is performed.
* No secrets or credential files are read.
* No KCA core or unrelated project files are modified.

## Stop conditions

Stop and report blockers if:

* working tree has unrelated uncommitted changes;
* required Orbit source files are missing;
* refactor would require touching forbidden paths;
* a secret or credential file would need to be read;
* py_compile fails and cannot be fixed safely;
* tests reveal major behavior regressions that cannot be fixed within this task;
* arena validation shows catastrophic regression and rollback/smaller refactor is needed;
* the refactor is too large to complete safely in one pass;
* acceptance criteria are met.

## Final response requirements

Report:

* files created;
* files modified;
* files moved;
* files deleted, with reason;
* architecture changes made;
* duplicated logic removed;
* FlightOracle/state/sanitizer fixes;
* config changes;
* tests added;
* validation commands run and results;
* arena results if run;
* behavior-preservation risks;
* known limitations;
* follow-up tasks created;
* whether acceptance criteria passed.
