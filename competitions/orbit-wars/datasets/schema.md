# Orbit Wars dataset schema (OW-P1-DATASET-001)

Stdlib formats: episode index = `episodes.jsonl` + `episodes.csv`; step table = `step_table.csv`;
candidates = `candidates.jsonl` (nested feature dict); report = markdown. (Parquet is an optional
later optimization; columns below are format-agnostic.)

## episode index (`episodes.{jsonl,csv}` + `episode_index_summary.json`)
| column | meaning |
|---|---|
| episode_id | Kaggle EpisodeId (from replay `info.EpisodeId`) |
| source_path | replay file path (not committed) |
| player_count | 2 or 4 |
| seed | episode seed |
| module_version | engine module version |
| team_names | `info.TeamNames` (profile/display names; e.g. flyingfox=harrysun2006) |
| rewards | final seat-ordered rewards |
| winner_seat / winner_name | max-reward seat + its team name |
| num_steps | episode length |
| top_player_flag | team_names intersect the `--top-players` list |

## step table (`step_table.csv`) — one row per (episode, step, player)
`episode_id, step, player_id, phase, planets_owned, production_total, ships_on_planets,
ships_in_flight, score_estimate, leader_gap` — computed via `core.state.PlayerState`.

## candidate table (`candidates.jsonl`) — one row per candidate launch
`episode_id, step, player_id, source_planet_id, target_object_id, target_type, ship_bucket,
oracle_valid, oracle_eta, oracle_first_hit_type, oracle_first_hit_id, min_sun_distance,
candidate_features_json, teacher_selected, teacher_ship_fraction, future_value_delta_h20,
future_value_delta_h50, terminal_outcome`.
- `oracle_*` / `min_sun_distance`: from `core.oracle.FlightOracle.validate_target` (deterministic).
- `candidate_features_json`: `core.features.candidate_features` (state + path verdict).
- `teacher_selected`: 1 iff the real player's action that step first-hits this (source,target).
- `teacher_ship_fraction`: launched ships / source ships (teacher's sizing).
- `future_value_delta_h20/h50`: player's `score_now` at step+20/+50 minus now (value-model target).
- `terminal_outcome`: final reward for the player.

## action table (`actions` — defined; emitted by `build_candidate_dataset` teacher decode)
`episode_id, step, player_id, source_planet_id, angle, ships, decoded_first_hit_id,
decoded_target_type, eta, action_type` — the teacher's real launches decoded via the FlightOracle
(action_type ∈ attack/reinforcement/expansion by decoded target owner). (Currently captured inside
the candidate builder's teacher decode; a standalone `actions.csv` emitter is a thin follow-up.)

## split / leakage
Split **by episode_id** (~80/10/10), stratified by `player_count` + `top_player_flag`. Leakage
guards: disjoint episode_id sets across splits; `future_value_delta_*` reads only steps t' > t of
the SAME episode. No episode appears in two splits.
