---
id: OW-P0-STATE-LEDGER-001
title: Build BattlefieldState, ArrivalLedger, and lightweight RuleEngine
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

# Task: Build BattlefieldState, ArrivalLedger, and lightweight RuleEngine

## Mission

Create a stable real-time battlefield-awareness layer that both rules and models can consume.

This is foundational for strategies/rules, model-based candidate scoring, and hybrid policy.

## Read first

- `competitions/orbit-wars/agent/main.py`
- `competitions/orbit-wars/agent/utils.py`
- `competitions/orbit-wars/core/` if present
- `competitions/orbit-wars/rules.md`
- `competitions/orbit-wars/strategy.md`
- `competitions/orbit-wars/tasks.md`
- `competitions/orbit-wars/tracking.md`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/dataset_schema.yaml`

## Desired modules

Create or update:

```text
competitions/orbit-wars/core/state.py
competitions/orbit-wars/core/ledger.py
competitions/orbit-wars/core/rule_engine.py
competitions/orbit-wars/core/features.py
competitions/orbit-wars/tests_orbit/test_state_ledger.py
competitions/orbit-wars/discussions/YYYY-MM-DD-battlefield-state-schema.md
```

If `core/` was created by FlightOracle task, reuse it. Do not duplicate geometry logic.

## BattlefieldState requirements

Represent:

### PlanetState

Raw:

```text
id, owner, x, y, radius, ships, production, angular_velocity, orbital_radius, linear_velocity
```

Derived:

```text
future_pos[t]
strategic_value_1_100
roi_value
holdability
frontier_score
pressure_score
centrality
nearest_enemy_eta
nearest_friendly_eta
my_inbound[t]
enemy_inbound[t]
projected_owner[t]
projected_ships[t]
is_hub_candidate
is_frontline
is_safe_bank
is_comet
expires_in_if_comet
```

### FleetState

```text
id, owner, x, y, angle, ships, speed, source_planet_id,
decoded_first_hit_id, decoded_target_type, eta,
min_sun_distance, path_safety,
is_attack, is_reinforcement, is_expansion, is_hub_transfer
```

### PlayerState

```text
player_id
planet_count
production_total
ships_on_planets
ships_in_flight
fleet_count
frontier_planets
hub_planets
safe_bank_ships
threatened_planets
attack_pressure
reinforcement_capacity
score_now
score_projected_H
rank_by_score
rank_by_production
leader_gap
elimination_risk
dogpile_risk
```

### GlobalState

```text
step
remaining_steps
player_count
alive_players
phase
my_id
leader_id
nearest_enemy_id
strongest_enemy_id
weakest_enemy_id
```

## Strategic value 1–100

Implement an explainable strategic value function for planets.

It should combine at least:

- production ROI;
- capture cost;
- holdability;
- path risk;
- centrality/hubness;
- frontier leverage;
- reinforcement connectivity;
- enemy pressure;
- endgame score value;
- comet expiration risk;
- 4p dogpile/elimination risk.

It does not need to be perfect, but it must be deterministic, bounded `[1,100]`, and decomposable for debug reports.

## ArrivalLedger / ThreatLedger

For horizon `H` default 80:

```text
planet_id x t -> projected owner / ships
my arrivals
enemy arrivals
neutral/enemy production growth
source defense slack after candidate launch
threat window
reinforcement need
```

Use FlightOracle when available to decode fleet target/ETA. If unavailable, use a clearly documented fallback and add a blocker.

## Lightweight RuleEngine

Implement an ECA-style guardrail engine, not a giant strategy rewrite.

Predicates examples:

```text
TARGET_FIRST_HIT_VALID(candidate)
SUN_SAFE(candidate)
SOURCE_HAS_DEFENSE_SLACK(candidate)
TARGET_ROI_POSITIVE(candidate)
TARGET_HOLDABLE(candidate)
MY_CORE_UNDER_THREAT()
I_AM_4P_LEADER()
I_AM_4P_UNDERDOG()
ENEMY_FIELD_ARMY_COMMITTED()
COMET_PAYBACK_POSITIVE()
ENDGAME_SCORE_POSITIVE()
```

Actions:

```text
block candidate
downweight candidate
upweight candidate
force defense
force reinforcement
switch posture
limit ship fraction
```

Model integration comes later. This task just builds the substrate and maybe wires minimal guardrails.

## Debug instrumentation

Add optional debug dump functions that can write compact summaries during local arena only:

```text
battlefield_state_summary.jsonl
candidate_features_sample.parquet/csv
ledger_debug.md
```

Do not enable heavy debug output online by default.

## Validation commands

Run:

```bash
python -m py_compile competitions/orbit-wars/core/*.py
python -m py_compile competitions/orbit-wars/agent/main.py
python competitions/orbit-wars/arena/validate.py --games 10 --procs 4
```

If tests exist:

```bash
python -m pytest competitions/orbit-wars/tests_orbit -q
```

If pytest is unavailable, run direct smoke scripts.

## Documentation updates

Update:

```text
competitions/orbit-wars/discussions/YYYY-MM-DD-battlefield-state-schema.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/strategy.md
competitions/orbit-wars/insights.md
```

## Acceptance criteria

- `BattlefieldState` builds from representative observations.
- Planet/Fleet/Player/Global states contain required raw and derived fields or documented blockers.
- Strategic value 1–100 exists and is explainable.
- ArrivalLedger/ThreatLedger exists and passes simple fixtures.
- RuleEngine exists with initial guardrail predicates/actions.
- Local agent still runs without regressions or failures.
- Docs explain schema and how models/rules consume it.

## Stop conditions

Stop if:

- observation schema is ambiguous and no fixture can resolve it;
- FlightOracle dependency is missing and ledger cannot be reliable;
- changes would require a full strategy rewrite;
- forbidden paths would be touched.

## Final response requirements

Report:

- state/ledger/rule modules created;
- strategic value formula;
- tests/smokes;
- validation results;
- blockers;
- next integration tasks.
