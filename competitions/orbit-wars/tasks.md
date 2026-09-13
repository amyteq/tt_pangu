# Tasks — Orbit Wars

> Derived from issue #87 TODO/Plan table (T1–T16). Full English tracking in `tracking.md`.

## Now
- **orbit5 ladder cycle (2026-06-16):** under Harry's directive to stop gating on the local arena (it
  under-discriminates our cluster) and test shelved candidates on the REAL ladder, **submitted 2** (only
  >1200-in-reasonable-time keeps a slot; both prior agents replaceable): harry ← `v4_scheduler.tar.gz`
  (keeps kuni05 1079.7 anchor), may ← `v3_forecast.py` (keeps coarr 640.7). v4 = best of our line vs evogen
  (20.0%); `v3_2_supply` NOT submitted (weaker 13.3% + confounded older lineage). **Arena reliability finding:**
  local win% vs evogen separates GROSS tiers (kuni05 90% ≫ ours ≤20% ↔ ladder 1083 ≫ 640–686) but is BLIND
  within our cluster (v3 μ686 and v3.2 μ640 both 16.7%) → fine candidate selection must use the ladder.
  See `submissions.md` orbit5 cycle. **Next action: monitor v4/v3 μ via `ops/live_loop.py --once` (T20).**
- **v4 "Scheduler"** (hub-and-hammer, T9/T13): at parity with v3.2 (49.3% on 150 paired seeds). OVERKILL-revival
  **closed FAILED (2026-06-16), all 4 sub-cuts**: v4a counter-attack window (`OW_V4A`) null −0.3pt; v4f FM3
  best-response (`OW_V4F`) −9pt; v4c cluster hammer (`OW_V4C`) null −0.3pt; v4i Isaiah two-band (`OW_V4I`)
  inert→−1.0pt (games end ~step 152, never reach its endgame phase). All vs evogen @150 seeds, all default-OFF.
  Diagnostics confirm the bottleneck is the strong-tier cliff itself (v4 ~1–2% vs kuni05), not a missing
  concentration lever — next real lever must be integrated, not another bolt-on/knob. See
  `postmortems/2026-06-16-overkill-revival.md`.

## Strong-tier breakthrough phase backlog (task pack `docs/tasks/competition-tracking/orbit-strong-tier/`)
> Target: public ladder **μ ≥ 1200** (secondary: upward early trajectory over first 10/20 episodes; offline:
> no hard execution bugs + positive 2p AND 4p gates). Architecture: hybrid, model-centric, deterministic-execution
> (`obs → BattlefieldState → Arrival/ThreatLedger → CandidateGenerator → Features → Model scorer/value → RuleEngine
> guardrails → FlightOracle + ActionSanitizer → actions`). The model ranks/scores; it does NOT own continuous-angle
> execution — flight/landing/path validity stays deterministic and tested.
- **P0 OW-P0-RESEARCH-001** (prompt `00`): kuni05 source study + matchmaking + identity map — ✅ done (PR #116): rules+flow-diff (not NN); similar-skill matching from game 1; flyingfox=harrysun2006.
- **P0 OW-P0-DOCS-LIVE-001** (prompt `01`): doc/live-loop consistency baseline — this task.
- **P0 OW-P0-FLIGHT-ORACLE-001** (prompt `02`): ✅ **done** — `core/geometry.py` + `core/oracle.py` FlightOracle (`first_hit`/`validate_target`; strict-sun vs near-sun vs OOB vs wrong-first-hit) + **`core/action_sanitizer.py`** (ActionSanitizer: blocks provably-fatal sun/oob always, wrong-first-hit when intent given; debug counters). **Wired into `agent/main.py`** final emission via `_emit_gate` (import-guarded: active when `core/` importable — local/arena/tar.gz-bundled — transparent no-op for the current single-file submission; `OW_NO_SANITIZE=1` / `OW_SANITIZE_LOG=<path>`). Verified ACTIVE (27 turns, emitted_valid 41, **blocked 0** on v3.2 → pure safety net, zero regression); `tests_orbit/test_{flight_oracle,action_sanitizer}.py` 10/10; `arena/validate.py` identical to pre-gate. To activate on the ladder: submit `main.py + core/` as a tar.gz. **Gates all model integration.**
- **P0/P1 OW-P0-STATE-LEDGER-001** (prompt `03`): ✅ **done** — typed `core/{state,ledger,rule_engine,features}.py` (Planet/Fleet/Player/Global/BattlefieldState, strategic value 1–100 decomposable, ArrivalLedger/ThreatLedger, ECA RuleEngine wiring the FlightOracle gate) + `tests_orbit/test_state_ledger.py` (5/5 PASS); `arena/validate.py` clean (no regression). Schema: `discussions/2026-06-16-battlefield-state-schema.md`.
- **P1 OW-P1-DATASET-001** (prompt `04`): ✅ **done** — `datasets/{build_episode_index,build_step_table,build_candidate_dataset,build_quality_report}.py` (+ `_replay.py`, `schema.md`, `README.md`) reusing the FlightOracle for first-hit/safety labels + `core.state` features (anti-BC: supports candidate-scoring/value-modeling, not direct policy). Fixture smoke on ep 80118852: index 1ep/4p/207steps, step_table 21 rows, candidates 255 (decode 90.2%, oracle-valid 54.9%, 24 strict-sun labels), `reports/dataset_quality.md`. Full 20G corpus → snorlax commands documented; raw JSON gitignored. ruff + py_compile clean.
- **P1/P2 OW-P1-MODEL-TRAIN-001 (prompt `05`, loop)**: ✅ **cycle 1 done (plumbing proof-of-life, local data)** — `models/{_featurize,train_candidate_scorer,train_value_model,export_npz,evaluate_offline}.py` + `README.md` + `datasets/gen_local_episodes.py`. No ladder replays were cached, so trained on **20 LOCAL self/cross-play episodes** (kuni05/evogen/v4/v3.2/pub_tactical, seeds 7000–3, 16×2p+4×4p → 144k candidates / 539 teacher-positives). Candidate scorer (MLP 24→128→64→1, BCE): valid **AUC 0.922** (2p 0.936 / 4p 0.903), recall@1/3/5 = 0.28/0.50/0.63. Value head (MSE on Δscore_h50): Pearson **r=0.68** (not exported — data-starved). Exported `scorer.npz` (97KB) runs in **pure numpy** (forward self-check vs torch = `err 0.0`); ladder fallback = rules-only. Card: `models/reports/model_card_20260617-cs-local20.md`; log: `models/reports/training_log.md`. **Decision: infra GO, model needs-more-data — promote ONLY via arena A/B (VALIDATION.md #3), NOT offline AUC (T12 BC: recall 0.387 / arena 0%).** Full ladder-teacher corpus → snorlax. py_compile + `--help` clean. **No Kaggle submit/push.**
- **P2 OW-P2-HYBRID-001 (prompt `06`)**: ✅ **done — integration COMPLETE + safe, model REJECTED (not promotable)**. Real-ladder corpus rebuilt (310 eps, 2.48M candidates → scorer AUC 0.882; `agent/hybrid_weights.json`). Re-ranker wired into `agent/main.py` (`_hybrid_rerank`, `OW_HYBRID`/`OW_HYBRID_BETA`): blends the model's candidate score into the v3.2 greedy commit order; **β=0 byte-identical to v3.2** (provable fallback), pure-Python online (no torch; matches offline 3e-16), p99 44ms. `agent/versions/hybrid_v0.py` = main+OW_HYBRID. **Arena A/B (240g/cell): strong-tier FLAT** — vs evogen1093 13.8%→13.8–14.6%, vs kuni05 0.8%→0.8% (crushed); weak/4p non-regressive; crash-safe (0/3650). **VALIDATION #3 (+7pt) NOT met → reject.** Offline AUC 0.88 did NOT translate (3rd imitation-lesson confirmation). `live/last_eval.json` submit_ready=false; postmortem `2026-06-17-hybrid-v0.md`; card `models/reports/model_card_20260617-cs-ladder310.md`. **No Kaggle submit/push.**
- **P2 FOLLOW-UP (from prompt 06) — strong-tier teacher corpus**: 🟡 **discovery DONE (2026-06-17)**. `ops/discover_strong_corpus.py` BFS-walks the ladder graph (ListEpisodes, read-only) from our subs → strong opponents (μ≥1200) → their strong-vs-strong games. Built `datasets/strong_corpus/manifest.json` = **1272 teacher episodes** (649 2p / 623 4p; 1056 strong subs; 1068 with a winning teacher seat), with per-episode teacher SEAT indices (API agents-list = seat order, verified vs replay rewards on 310 eps). **PENDING** (gated on ListEpisodes 429 cooldown): fetch the teacher replays + add `--seat-manifest` to `build_candidate_dataset.py` (restrict candidates to teacher seats) + retrain + re-run the `OW_HYBRID` A/B. Commands queued in `live/parallel_work_queue.md`. (BFS expansion stopped at 18 subs by the 429; manifest already large enough to start.)
- **P1 OW-ARCH-001 (prompt `08`)**: ✅ **done (2026-06-18) — layered-architecture refactor + correctness hardening.** Split the monolithic `agent/main.py` (now a **62-line thin entrypoint**) → `core/policy.py` (v3.2 Forecast core + orchestration + the documented 8-layer data-flow contract); deduped all physics to `core/geometry.py` (`agent/utils.py` is now a thin re-export wrapper). **P0 fixes:** (a) `FlightOracle.trace_from_position` + `decode_existing_fleet`, and `core/state.py` now decodes in-flight fleets from their CURRENT `(x,y)` (not relaunched from source); (b) intended target IDs preserved through emission via new `core/action_emitter.py` → `core/action_sanitizer.py` (wrong-first-hit gate opt-in `OW_BLOCK_WRONG_HIT`); (c) `core/features.py` ownership split into **own/enemy/neutral** (25-dim now; `owner!=-1`≠enemy). New typed `core/candidates.py::CandidateAction`. `core/rule_engine.py` wired via `_rule_gate` (pass-through default `OW_RULE_ENGINE=0`). **Config layer:** `core/config.py` centralizes all 33 `OW_*` reads (env→baked→literal); YAML source `config/{default,profiles/*}.yaml` baked (PyYAML-free) to `agent/config_baked.py` via `config/bake.py` (`--check` drift guard). **Behavior preserved byte-for-byte** (golden 526-record obs→moves = 0 mismatches; arena `validate.py` 100% vs v2/v1/starter/random). **Caught + fixed B12** (the `__file__`-at-load passive-agent regression — see `bugs.md`). 10 `tests_orbit` files / 43 tests pass; `ruff check .` clean. **No Kaggle ops.** (Note: golden 0-mismatch is vs the **post-B11 baseline** — the already-merged agent at the start of this refactor, PR #117 — not the frozen pre-B11 `agent/versions/v3_2.py`. The current-position fleet-decode fix and the 25-feat ownership split are correct + unit-tested but **dormant on the default move path** — consumed only when layer [5]/[6] is enabled — which is why the default path is byte-identical.) Follow-ups:
  - **OW-ARCH-002 (P2)**: re-train the layer-5 scorer on the **fixed-sim 25-feature** contract (the deployed 24-feat `hybrid_weights.json` now auto-disables → rules-only) and re-run the `OW_HYBRID` suite-gate A/B (corpus `datasets/strong_corpus/` ready). Supersedes the prompt-06 reject.
  - **OW-ARCH-003 (P3)**: evaluate the RuleEngine layer on the ladder/suite (`OW_RULE_ENGINE=1`, currently inert/pass-through) — A/B vs v3.2 before any enable; same +7pt bar.
  - **OW-ARCH-004 (P3)**: extract the inline forward-sim valuation into `core/valuation.py` (deferred — tightly coupled to the v3.2 intercept loop; not split this pass to avoid behavior risk). Migrate the remaining experimental `OW_*` knobs (live only in `agent/versions/*`) into `core.config` if/when any is promoted into `core/policy.py`.
  - **OW-ARCH-005 (chore)**: re-format the 2 pre-existing format-dirty test files `tests_orbit/test_{flight_oracle,state_ledger}.py` (committed unformatted on main; CI's `ruff format --check` is disabled so they don't fail CI — left untouched here to avoid out-of-scope churn).
- **P3 (low) — FlightOracle `first_hit` oob-trace fidelity (B11)**: `first_hit` flags ~11% of real intercept launches "oob" (trace artifact, equal winner/loser, non-causal; sanitizer unaffected). Add an intercept tolerance (planet radius + ε) or require intended target if `first_hit` is used standalone. Does not block the loop. (NOT started.)
- **online loop prompt `07`**: ladder iterate — submit → track first 10/20 episodes → analyze → classify → fix/train → resubmit (NOT run this session).

## Early-stop / promotion policy (toward μ ≥ 1200)
> Matchmaking is similar-skill from the first game (INS-005), so early μ is informative (fair, but noisy on few games).
- **Immediate weak / fix_required:** any hard execution bug — strict sun collision, invalid action, OOB loss, or
  repeated wrong-first-hit-target (detected by `episode_analyze.py` / the FlightOracle counters).
- **After ~10 episodes:** weak if 2p win-rate / μ trend is flat-or-down and not climbing (track via `ops/track_submission.py --once --submission-id <id> --decide-after 10`).
- **After ~20 episodes:** weak if not climbing toward μ ≥ 1200 and below the incumbent/anchor (kuni05 ~1080) — release the active slot.
- **Strong (keep slot):** μ ≥ 1200 or a robust upward trajectory with strong-tier wins.
- Config home (if/when formalized): `configs/early_stop_policy.yaml` (referenced by the task pack; not yet present — `unknown`). `track_submission.py` currently emits a keep/replace recommendation; thresholds above are the documented intent.

## Next
- D2 last-3-days freeze: pick the best 2 versions per account and re-submit (latest-2 scored).
- T1 replay mining of the public episode dataset (top-bot behavior → heuristic params).
- T4 endgame + comet module (turns 450–500 score-positive only; comet payback gate).
- **T15 comet trajectory prediction** (§9-1 gap; chartered 2026-06-14, measure-first). Gap: `project()`
  drops comets (`main.py` "Comets are dropped") and `_path_blocked` ignores them — we neither predict nor
  exploit/dodge their path-based motion. Pre-build gate: quantify comet incidence + games comets decide
  from the episode dataset; build only if material. Scope: model `comets` path → feed `project()` swept
  collision + `_path_blocked`; optional comet-payback timing (merge w/ T4). Env-gated `OW_COMET`; suite-gate
  A/B on comet maps + no-regress on comet-free + 4p avg_rank.
- ~~**T16 sun/planet-avoidance waypoint routing**~~ → **measured → PARK (2026-06-15).** Instrumented
  stock v3.2 (`arena/measure_t16.py` + identity-proven twin) over 80 games; 3-agent adversarial review.
  Dropped value-positive launches are frequent but realistic recoverable value is **6–15% of committed
  ≈ 1.4–2.7pt win-rate, below the +7pt bake bar** (only 35.5% of "recoverable" drops are value-positive;
  41% of dropped targets are captured anyway within 5 turns; same frequent-gap → ladder-null mechanism as
  co-arrival). Measure-first did its job: parked before building. Reopen via a gate-only prototype only if v4 stalls.

## Follow-ups from the fleet-massing discussion (orbit5, 2026-06-16)
> Harry's "少而重 + 内圈旋转中转站" thesis, checked against the engine source + our code + rigorous timing math.
> Engine facts confirmed: inner planets (orbital_r+radius<50) rotate at ω∈[0.025,0.05] rad/step, same ω all;
> outer static (`orbit_wars.py:540-546`). `prod=randint(1,5)`, `radius=1+ln(prod)` (size is log-of-prod, prod is
> primitive), size ⟂ distance-to-sun (`:80-81,:133-138`). Fleet `speed=1+(maxSpeed-1)(ln n/ln1000)^1.5` cap ~6
> (`:577`): 19→2.39, 76→3.48 (+46%). Garrison rides a rotating planet for free (it sits AT the planet pos).

- **T19 — Episode 80118852 = OUR adapted-kuni05's WIN; confirms an early 多而小 / slow-expansion weakness**
  (✅ resolved 2026-06-16). 🔴 **DOC CORRECTION: `flyingfox` is harrysun2006's Kaggle PROFILE name → flyingfox = US.**
  So submission **53582503 = our `submission_kuni.tar.gz` (adapted kuni05, μ~1080)**, NOT an external competitor —
  this also means tracking.md's "flyingfox 205-episode history" 4p-format finding and `episode_discover`'s example
  were analyzing OUR OWN account's history (the 4p finding still stands; only the "external" label was wrong;
  EPISODES.md #3 should be re-labeled). Episode 80118852 (`replays/80118852.json`, gitignored) is a 4p FFA we WON
  (seat 1, rewards [-1,+1,-1,-1]); 36 planets ids 0–35 (no 163/164 — viewer artifact). **Substance CONFIRMED** —
  our seat-1 (kuni05) launch profile BY PHASE: early ≤80 = 74 launches **median 20 ships** (多而小), and we were
  BEHIND (5 planets vs Lucky's 7 at step 40); mid 81–160 = median 36; late >160 = median **238**, max 467. We
  overtook only ~step 100 and ground out the win after rivals imploded. → Even our strongest agent expands with
  many small fleets early and only masses late; vs the strong tier (which doesn't collapse) that loses. **This is
  the empirical basis for T20/T21: mass EARLIER (few-but-heavy from the opening), don't grind.**
- **T20 — EARLY-game massing (the empirically-pinpointed lever) + v4 live test** (🟢 in progress; submitted orbit5).
  Episode 80118852 (T19) shows our own kuni05's gap is SPECIFICALLY the opening: early ≤step80 median launch is
  **20 ships (多而小)** and we fall behind (5 vs 7 planets @ step40); we only mass (median 238) once rivals collapse.
  So the lever is "mass few-but-heavy FROM THE OPENING," not late. (a) v4's hub-and-hammer (default ON,
  `v4.py:813-949`) is the source-side-massing embodiment, now on harry's ladder — monitor μ as the live test;
  v3.2/main.py has NO massing (`main.py:938-947`). (b) Concrete experiment: an early-phase (step<~80) massing/
  bigger-min-launch knob that exploits speed (`+46%` at 19→76) + the strict capture threshold, gated on suite
  (evogen) + 4p. Distinguish carefully from already-refuted `OW_MULTISRC`/`OW_COARRIVAL`/`OW_OPENING` (the prior
  opening-grabber FIRED more but won LESS — the difference must be HEAVY not just MORE). If neither v4 nor an
  early-massing knob moves the ladder, massing is ladder-null at our tier.
  **v4 LIVE RESULT (sub 53730511, first 10 episodes, 2026-06-16 via `ops/track_submission.py`):** μ
  600→peak 842.9→settling **~690–720** (net +90), 2p **4W-3L** + 4p 1×1st/2×2nd. **v4 is our BEST own-agent
  ladder result to date** (> old v3.2 640 / v3 686) — and the LOCAL arena had called it mere "parity with v3.2",
  so this re-confirms the arena under-discriminates and the ladder is the judge. But v4 plateaus well short of
  the >1200 bar (strong-tier cliff intact). **DECISION: KEEP v4 on the ladder (replacing it gains nothing — no
  candidate >1200).** Loop stopped at 10 episodes; data in `live/track_53730511.csv` + `live/version_submissions.md`.
  - **T20(b) early-massing knob `OW_EM` — ❌ REFUTED (2026-06-16).** Implemented opening-only + neutral-only
    capture-and-hold sizing (`OW_EM`/`EM_HOLD`/`EM_SLACK`/`EM_PHASE`/`EM_MIN`, default OFF, byte-identical when
    off) — distinct from `OW_OVERKILL`/`OW_OPENING`. A/B vs fidelity-verified evogen (40 paired seeds): defaults
    **8.8% = −11.2pt**; a 6-config sweep is **monotonic-negative with NO positive region** (HOLD0.3 −7.5, HOLD0.6
    −13.8, MIN25 −11.2, gentlest PHASE40 −1.2≈noise). Heavier opening grabs over-commit and lose the ship race —
    same as `OW_OVERKILL`/`v4f`. 12th refuted single-mechanism massing lever; `OW_EM` left default-OFF for repro.
    The on-target direction is an INTEGRATED opening planner (sequence/target selection), not a sizing knob —
    large/high-risk, deferred. Postmortem: `postmortems/2026-06-16-t20-early-massing.md`. **Do NOT iterate the knob.**
- **T21 — Forward-planet aggregation (pure geometry, measure-first)**. Rigorous timing math: the ONLY regime
  where 2-hop beats 1-hop is launching from an ALREADY-HELD planet that is closer-in-flight-time to T — pure
  geometry, not rotation. Check whether the greedy already picks min-ETA sources; if not, add a "prefer the
  held source with min flight-time + allow an already-held forward planet to aggregate" preference. NEVER ship
  O→I as a deliberate detour (honest 2-hop strictly worse: 35–39 vs 27 turns direct).
- **PARK — Rotation-conveyor / inner-planet staging relay.** Rigorously REFUTED as a distance/speed lever with
  the exact engine swept-collision rule: max inner radial closing speed ≈2.35 u/step < a 19-ship fleet's
  2.39 u/step → flying always beats riding; optimal relaunch delay = 0 in every tested geometry/ω; the orbital
  minimum-distance phase is 170–210 steps out (games end ~150). The real value Harry intuits is the
  MASSING/+speed effect, obtainable at the source (no hop). Same family as PARKed T8/T16/OVERKILL. No build;
  recorded in `insights.md`.
- **T22 — (optional) inner vs outer target valuation** (measure-first). Production ⟂ distance-to-sun and inner
  planets rotate — does holding an inner (rotating) planet differ in defensibility/value (a captured inner
  planet's garrison drifts toward different fronts as it orbits)? Measure in episodes before any build.

## 4p ladder finding (KCT-OW-LIVE-002, 2026-06-15)
- 🔴 **The μ-ladder is ~half 4-player FFA and 4p updates μ** (verified from flyingfox's 205-episode history; ~83% net μ
  from 2p, ~17% from 4p). Prior "1v1 only" assumption was wrong; our line is 2p-tuned. Full analysis: `EPISODES.md` #3.
- ✅ **T17: 4p placement gate** `arena/eval_4p.py` (avg_rank / 1st-rate / elim-by-t50 / planets@t50) — every future
  candidate now gated in BOTH 2p and 4p (Harry's standing directive). Our v3.2/v4 4p avg_rank ≈ 1.8 (not broken, untuned).
- ❌ **Naive 4p-aware mode** (`OW_4P_MODE`: owner-aware `_term` + don't-be-early-aggressor + survival reserve; 2p
  byte-identical, gated): A/B vs 3×v3_2 = 1.719 avg_rank / 28% 1st vs baseline 1.469 / 53% — WORSE (unconditional
  damping cedes advantage when we're dominant). Kept default-OFF. 8th lever to test negative naively.
- 📋 **T18: situational 4p strategy** — damp aggression / raise survival ONLY when outgunned (multiple stronger rivals),
  press when dominant; needs a diverse-strong 4p field to validate (local homogeneous field can't). Framework in place.

## Backlog / background
- T12 RL/distillation (D4): de-prioritized to background after v0/v1/v2 (BC ≠ playing); next would be
  DAgger / value distillation / forward-sim features.

## Blocked
- None hard-blocking; constrained by deadline (06-23), 5/day quota, and the strong-tier cliff.

## Live loop (KCT-OW-LIVE-002)
- **`ops/` bounded live-submission loop built + ran one `--once` cycle (2026-06-15).** Tracks active
  latest-2 slots across both accounts (read-only Kaggle), credential-safe (`ops/kaggle_auth.py`; secrets
  never printed/committed), ingests/analyzes episodes (decode + **sun-collision/hard-bug detection**,
  winner-reason → `live/episodes_index.csv`), classifies agents (`neutral/strong/weak/fix_required/retired/
  unknown`), and performs **gated autonomous submit** via `submit.py` (budget + quota + compliance +
  replacement-plan gates). Commands in `ops/README.md`.
- **Cycle result:** harry [kuni05 μ1086.5, v3.2 μ655.7]; may [v3_2_coarr μ644.0, v3.2 μ630.1]. No queued
  episodes; **NO_SUBMIT** — no validated candidate beats an active slot (v4 = parity), budget/quota preserved.
  `live/account_status.md`, `live/agent_status.md`, `live/submit_plans.md`, `live/push_submit_audit.md`,
  `live/active_agents.yaml` written. No bugs found → no new Tn tasks generated this cycle.

## Done
- T2 suite param optimization → **t14 → v3.2 baked (+7pt over baseline)**, 6/6 VALIDATION gates, submitted.
- T8 co-arrival (real +3pt evogen-layer; default OFF). T10 VALIDATION.md gate. T11 ledger (no-op).
- T6 confirm eval-side torch usable. T7 2p/4p split (rejected — ladder is 1v1).
- v1 → v2 → v2.1 (556) → v3 Forecast (686) → v3.1 → v3.2 (660 current) → v4 Scheduler (parity, iterating).
- Multi-account submit tool (`submit.py`, compliance-gated). Version league (`LEAGUE.md`). Episode pipeline.

## Proposed GitHub issues
> Not created in this task. Issue #87 is the hub. Suggested:
- "orbit-wars: last-3-days final-2 freeze decision + post-deadline archival" (acceptance: record final
  submitted 2 per account; backfill submissions.md with final ladder + private LB; status → archived).
