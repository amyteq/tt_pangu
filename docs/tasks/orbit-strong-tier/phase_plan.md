# Orbit Wars strong-tier breakthrough phase plan

## Goal

Reach a version of an Orbit Wars agent that can break the strong-tier cliff:

```text
Primary online target: public ladder μ >= 1200
Secondary online target: upward early trajectory over first 10/20 episodes
Offline target: no known hard execution bugs + positive 2p/4p gates vs incumbent/anchors
```

## Strategic direction

Use **hybrid, model-centric, deterministic-execution architecture**:

```text
obs
  -> BattlefieldState
  -> ArrivalLedger / ThreatLedger
  -> CandidateGenerator
  -> FeatureBuilder
  -> Model scorer / value model / posture model
  -> RuleEngine guardrails
  -> FlightOracle + ActionSanitizer
  -> action list
```

The model may score or rank candidates, estimate value, classify posture, and detect opportunities. The model should not own raw continuous-angle execution. Flight/landing/path validity must be deterministic and tested.

## Phase 0 — Research and live-loop reality check

**Purpose:** avoid building on false assumptions.

Tasks:

- Pull or inspect public `kuni05` / kuni05-class source if available.
- Preserve attribution and license notes.
- Determine whether Kaggle opponents are assigned by similar skill rating, weak-to-strong curriculum, random, or empirically mixed.
- Determine reliable mapping between Kaggle username, profile/display name, team name, submission id, and replay `TeamNames`.
- Verify current active slots and early-stop mechanics in existing `ops/track_submission.py`.

Deliverables:

```text
competitions/orbit-wars/references.md
competitions/orbit-wars/discussions/YYYY-MM-DD-kuni05-system-study.md
competitions/orbit-wars/discussions/YYYY-MM-DD-matchmaking-and-identity.md
competitions/orbit-wars/live/player_identity_map.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
```

## Phase 1 — Execution foundation zero-bug

**Purpose:** make landing target/path execution reliable before model training.

Tasks:

- Implement `FlightOracle` with engine-equivalent swept collision.
- Decode first-hit target for our proposed actions and replayed actions.
- Distinguish strict sun collision from near-sun warning.
- Validate non-target first-hit, out-of-bounds, comet first-hit, and invalid-action cases.
- Replace final action emission with `FlightOracle` gate.

Deliverables:

```text
competitions/orbit-wars/core/geometry.py
competitions/orbit-wars/core/oracle.py
competitions/orbit-wars/core/action_sanitizer.py
competitions/orbit-wars/tests_orbit/test_flight_oracle.py
competitions/orbit-wars/tests_orbit/fixtures/79228928.json or compact fixture reference
competitions/orbit-wars/bugs.md
competitions/orbit-wars/VALIDATION.md
```

Gate:

```text
No candidate action is emitted unless first_hit == intended target or a documented safe exception applies.
No strict sun collision is allowed in generated actions.
Replay decode smoke passes on 79228928 and sampled replays.
```

## Phase 2 — BattlefieldState, ledger, and lightweight rule engine

**Purpose:** create reliable real-time battlefield awareness for both rules and models.

Tasks:

- Implement typed `PlanetState`, `FleetState`, `PlayerState`, `BattlefieldState`, and `GlobalState`.
- Compute per-planet strategic value 1–100.
- Implement ArrivalLedger / ThreatLedger for projected owner/ships over horizon.
- Implement lightweight rule engine predicates/actions as guardrails and tactical overrides.

Deliverables:

```text
competitions/orbit-wars/core/state.py
competitions/orbit-wars/core/ledger.py
competitions/orbit-wars/core/rule_engine.py
competitions/orbit-wars/core/features.py
competitions/orbit-wars/discussions/YYYY-MM-DD-battlefield-state-schema.md
competitions/orbit-wars/tests_orbit/test_state_ledger.py
```

Gate:

```text
State builds from any observation without exceptions.
Ledger agrees with replay/simple hand fixtures.
Strategic value is stable, explainable, and visible in debug dumps.
```

## Phase 3 — Replay dataset and feature pipeline

**Purpose:** turn 4k+ top-player replay JSONs into clean training data.

Tasks:

- Build episode index over downloaded 20G replay corpus.
- Parse 2p/4p, player names, rewards, submission ids if present, steps, actions.
- Generate step-level, candidate-level, and action-label tables.
- Use FlightOracle for safety labels and first-hit target labels.
- Produce data quality reports.

Deliverables:

```text
competitions/orbit-wars/datasets/schema.md
competitions/orbit-wars/datasets/build_episode_index.py
competitions/orbit-wars/datasets/build_candidate_dataset.py
competitions/orbit-wars/datasets/reports/dataset_quality.md
competitions/orbit-wars/datasets/README.md
```

Gate:

```text
Teacher action decode rate reported.
Top-player / non-top-player split documented.
2p/4p balance documented.
No large raw replay files committed.
Parquet/CSV artifacts are external/gitignored unless small summaries.
```

## Phase 4 — Model training on snorlax

**Purpose:** train a model that helps ranking candidates or estimating value, not direct continuous control.

First model:

```text
candidate_scorer_v0:
  input = candidate features + battlefield summaries + short history
  output = candidate score, optional ship bucket/fraction adjustment, posture hint
```

Second model:

```text
value_model_v0:
  input = state + candidate/action set features
  output = Δvalue / placement or win probability / collapse risk
```

Deliverables:

```text
competitions/orbit-wars/models/train_candidate_scorer.py
competitions/orbit-wars/models/train_value_model.py
competitions/orbit-wars/models/export_npz.py
competitions/orbit-wars/models/reports/model_card_<run>.md
competitions/orbit-wars/models/artifacts/<run>/   # gitignored unless tiny
```

Gate:

```text
Offline validation beats heuristic candidate ordering on held-out replays.
No episode leakage across train/val/test.
Exported model can run in pure Python or explicitly passes Kaggle runtime smoke.
```

## Phase 5 — Hybrid policy integration

**Purpose:** connect model scorer/value model into the agent without compromising safety.

Tasks:

- Keep rule/search candidate generator.
- Add model score as ranking signal.
- Add rule engine filters/downweights/upweights.
- Validate all final actions with FlightOracle.
- Implement runtime fallback to rules-only if model fails.

Deliverables:

```text
competitions/orbit-wars/agent/main.py
competitions/orbit-wars/agent/hybrid_weights.py or model weights embedding
competitions/orbit-wars/agent/versions/hybrid_v0.py
competitions/orbit-wars/postmortems/YYYY-MM-DD-hybrid-v0.md
```

Gate:

```text
py_compile passes.
validate.py passes.
suite_gate.py passes or explains intentional ladder-probe exception.
2p/4p robustness not materially worse.
Runtime p99 within actTimeout margin.
```

## Phase 6 — Long-running ladder iteration loop

**Purpose:** submit validated versions, analyze episodes, early-stop weak versions, and iterate until strong-tier breakthrough or no tasks remain.

Loop:

```text
submit version -> mark neutral -> track first 10/20 episodes -> analyze episodes -> classify version -> fix/train/enhance -> resubmit plan -> submit next version
```

Early stop:

```text
Immediate weak/fix_required: strict hard bug, sun collision, invalid action, repeated first-hit-wrong-target.
After 10 episodes: weak if win rate/μ trend fails early policy.
After 20 episodes: weak if not climbing toward 1200 or below incumbent/anchor threshold.
Strong: μ >= 1200 or robust positive trajectory with strong-tier wins.
```

Parallelism:

```text
Ladder loop analyzes submissions while snorlax model training runs.
Replay dataset expansion can continue while live-loop monitors new episodes.
Foundation tasks gate model integration but not pure data indexing.
```
