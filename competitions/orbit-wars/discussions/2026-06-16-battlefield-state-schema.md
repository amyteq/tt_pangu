# BattlefieldState / Ledger / RuleEngine schema (OW-P0-STATE-LEDGER-001)

> 2026-06-16. The deterministic battlefield-awareness substrate that rules **and** future
> models consume. Built on the engine-verified `core/geometry.py` + `core/oracle.py`
> (FlightOracle). All fields are deterministic; the strategic value is decomposable.

## Module map (`competitions/orbit-wars/core/`)
| module | role |
|---|---|
| `geometry.py` | engine-verified primitives (copied from `agent/utils.py`, 0-error vs engine): `fleet_speed`, `planet_pos`, `swept_hit`, `seg_point_dist`, `resolve_combat`, `solve_intercept`, `project`, `replay_planet` |
| `oracle.py` | `FlightOracle` — `first_hit(obs, src, angle, ships, horizon)` / `validate_target(obs, src, tgt, ships, horizon)` → `FlightResult` (target/friendly/enemy/neutral/comet/sun/oob/none; strict-sun vs near-sun; min_sun_distance) |
| `ledger.py` | `ArrivalLedger` (build via `build_ledger(obs, H)`) — projected owner/ships over H, my/enemy inbound, threat window, reinforcement need, defense slack |
| `state.py` | `build_battlefield_state(obs, H)` → `BattlefieldState{planets, fleets, players, glob, ledger}` typed dataclasses |
| `features.py` | `candidate_features(state, candidate, obs)` → flat feature dict (state + FlightOracle path verdict) |
| `rule_engine.py` | ECA `RuleEngine.evaluate(state, feat)` → `RuleVerdict{decision, weight, reasons}` |

## Pipeline
```
obs → build_battlefield_state → (PlanetState/FleetState/PlayerState/GlobalState + ArrivalLedger)
candidate {source,target,ships} → candidate_features (+FlightOracle) → RuleEngine.evaluate
   → block (hard safety: SUN_SAFE, TARGET_FIRST_HIT_VALID) | allow×weight (tactical)
```
The two **load-bearing guardrails** wire the deterministic FlightOracle gate: a candidate is
**blocked** unless its first hit is the intended target and it has no strict sun collision.
Model scoring slots in later as an additional weight signal (Phase 4/6); the substrate is
agnostic to it.

## Strategic value (1–100, explainable)
`state._strategic_value` blends normalized components — `prod_roi` (0.34), `holdability`
(0.24), `frontier_leverage` (0.18), `centrality_hubness` (0.14), minus `enemy_pressure`
(0.10) — clamped to [1,100]. Each planet exposes `value_components` for debug dumps. It is
deterministic and bounded; tuning the weights is a Phase-2+ follow-up, not correctness.

## Fields & approximations (acceptance: required fields OR documented blockers)
Implemented per the task schema for Planet/Fleet/Player/Global. Documented approximations:
- `PlanetState.nearest_enemy_eta/nearest_friendly_eta` — distance/`fleet_speed` of a token
  fleet from the nearest source (cheap proxy; exact intercept ETA available via
  `geometry.solve_intercept` when a specific size is chosen).
- `PlanetState.expires_in_if_comet` = None — **blocker**: comet path/expiry is not modelled
  (engine comets move on a path; `project` drops them). Conservative until T15/T4 comet work.
- `FleetState.is_hub_transfer` = False — staging/relay is not modelled here (rotation-relay
  was PARKed; set by a higher layer if/when hub staging is built).
- `PlayerState.score_projected_H` — sum of projected terminal ships on planets that player
  is projected to own at H (do-nothing projection; ignores both sides' future launches).
- 4p `dogpile_risk`/`elimination_risk` — heuristic (leader-in-FFA / threatened-planet share),
  refine with the 4p situational work (T18).

## How models/rules consume it
- **Rules** (now): `RuleEngine` reads `BattlefieldState` + `candidate_features`; hard-blocks
  unsafe launches (FlightOracle) and re-weights tactically (defense slack, holdability, ROI,
  4p posture, core-under-threat).
- **Models** (later): `candidate_features` is the feature contract for `candidate_scorer_v0` /
  `value_model_v0`; the model's score becomes another multiplicative weight, never raw
  continuous-angle control — angle/landing stays deterministic via the FlightOracle.

## Tests
`tests_orbit/test_flight_oracle.py` (6/6) + `tests_orbit/test_state_ledger.py` (5/5) pass via
the direct runners (pytest not installed in the venv). Regression: `arena/validate.py
--games 10` runs the live agent clean (100% vs baselines) — adding `core/` did not touch
`agent/main.py`, so no behavior change.
