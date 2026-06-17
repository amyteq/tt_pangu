---
id: OW-P1-DATASET-001
title: Build Orbit Wars replay dataset and candidate-feature pipeline
kind: claude-code-task
status: ready
scope: competition-data-pipeline
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

# Task: Build Orbit Wars replay dataset and candidate-feature pipeline

## Mission

Create a scalable data pipeline for the downloaded top-player replay corpus and new ladder episodes.

The user has already downloaded 4k+ top-player episodes (~20GB). This task should not commit raw JSON. It should build scripts, schemas, small fixtures, indexes, and reports.

## Read first

- `competitions/orbit-wars/arena/distill_prep.py`
- `competitions/orbit-wars/arena/distill_train.py`
- `competitions/orbit-wars/arena/episodes_index.py`
- `competitions/orbit-wars/arena/episodes_prep.py`
- `competitions/orbit-wars/ops/episode_analyze.py`
- `competitions/orbit-wars/ops/episode_discover.py`
- `competitions/orbit-wars/core/` if present
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/dataset_schema.yaml`
- example replay JSON such as `79228928.json` if available

## Design constraints

- Use `FlightOracle` for first-hit/safety labels when available.
- Use `BattlefieldState` and `Ledger` features when available.
- If those foundations are not ready, build index/step parsing now and mark candidate labels as pending.
- Do not duplicate old BC direct-policy mistake; dataset should support candidate scoring / value modeling / safety labels.
- Do not commit 20GB raw replays.

## Suggested modules

Create or update:

```text
competitions/orbit-wars/datasets/README.md
competitions/orbit-wars/datasets/schema.md
competitions/orbit-wars/datasets/build_episode_index.py
competitions/orbit-wars/datasets/build_step_table.py
competitions/orbit-wars/datasets/build_candidate_dataset.py
competitions/orbit-wars/datasets/build_quality_report.py
competitions/orbit-wars/datasets/reports/README.md
competitions/orbit-wars/datasets/reports/dataset_quality.md
competitions/orbit-wars/datasets/fixtures/README.md
```

Update `.gitignore` under `competitions/orbit-wars/` if needed to ignore large generated artifacts:

```text
datasets/artifacts/
datasets/cache/
models/artifacts/
replays/
```

## Inputs

Support configurable input roots:

```bash
--replay-root /path/to/20gb/replay/jsons
--out-root competitions/orbit-wars/datasets/artifacts
--fixture /path/to/79228928.json
```

Do not hardcode snorlax paths. Document example snorlax paths separately.

## Tables

Build or define these tables:

### episode index

```text
episode_id, source_path, player_count, seed, module_version, team_names, rewards, winner_seat, winner_name, top_player_flag
```

### step table

```text
episode_id, step, player_id, phase, planets_owned, production_total, ships_on_planets, ships_in_flight, score_estimate, leader_gap
```

### candidate table

One row per candidate per step:

```text
episode_id, step, player_id, source_planet_id, target_object_id, target_type, ship_bucket,
oracle_valid, oracle_eta, oracle_first_hit_type, oracle_first_hit_id, min_sun_distance,
candidate_features_json, teacher_selected, teacher_ship_fraction,
future_value_delta_h20, future_value_delta_h50, terminal_outcome
```

### action table

```text
episode_id, step, player_id, source_planet_id, angle, ships,
decoded_first_hit_id, decoded_target_type, eta, action_type
```

## Quality report

The quality report must include:

- replay count;
- malformed replay count;
- total steps;
- 2p/4p split;
- top-player distribution if known;
- action decode rate;
- first-hit unknown rate;
- candidate count;
- positive-label rate;
- strict sun collision labels;
- near-sun labels;
- train/valid/test split policy;
- leakage checks;
- runtime throughput.

## Validation commands

Run small fixture/smoke only in this task:

```bash
python -m py_compile competitions/orbit-wars/datasets/*.py
python competitions/orbit-wars/datasets/build_episode_index.py --help
python competitions/orbit-wars/datasets/build_quality_report.py --help
```

If a fixture path is available:

```bash
python competitions/orbit-wars/datasets/build_episode_index.py --replay-root <fixture-dir> --out-root /tmp/orbit_dataset_smoke
python competitions/orbit-wars/datasets/build_quality_report.py --in-root /tmp/orbit_dataset_smoke --out competitions/orbit-wars/datasets/reports/dataset_quality.md
```

Do not process the full 20GB corpus unless running on snorlax or explicitly requested. Provide the snorlax command instead.

## Snorlax command template

Document commands like:

```bash
python competitions/orbit-wars/datasets/build_episode_index.py \
  --replay-root /path/to/top_player_replays \
  --out-root /path/to/orbit_dataset_artifacts

python competitions/orbit-wars/datasets/build_candidate_dataset.py \
  --episode-index /path/to/orbit_dataset_artifacts/episodes.parquet \
  --replay-root /path/to/top_player_replays \
  --out-root /path/to/orbit_dataset_artifacts/candidates \
  --use-flight-oracle
```

## Documentation updates

Update:

```text
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/insights.md
competitions/orbit-wars/datasets/README.md
```

## Acceptance criteria

- Dataset schema is documented.
- Scripts exist for episode index, step/action/candidate data, and quality report.
- Small fixture/smoke runs or blockers are documented.
- Full-corpus snorlax commands are documented.
- Raw 20GB JSONs are not committed.
- Candidate labels use or wait for FlightOracle rather than unreliable duplicate logic.

## Stop conditions

Stop if:

- replay schema cannot be parsed from fixtures;
- FlightOracle absence blocks candidate labels; in that case finish episode index and document blocker;
- processing would require committing large artifacts;
- changes would touch forbidden paths.

## Final response requirements

Report:

- scripts created;
- schema decisions;
- fixture smoke result;
- full-corpus command;
- data quality report path;
- blockers;
- next tasks.
