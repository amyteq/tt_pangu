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
- **P0 OW-P0-FLIGHT-ORACLE-001** (prompt `02`): 🟡 **core built** — `core/geometry.py` (engine-verified primitives) + `core/oracle.py` FlightOracle (`first_hit`/`validate_target`; strict-sun vs near-sun vs OOB vs wrong-first-hit) + `tests_orbit/test_flight_oracle.py` (6/6 PASS). **Remaining:** `core/action_sanitizer.py` + wire the `candidate → FlightOracle → ActionSanitizer → emit/block` gate + debug counters into `agent/main.py` (the live-emission integration). **Gates all model integration.**
- **P0/P1 OW-P0-STATE-LEDGER-001** (prompt `03`): ✅ **done** — typed `core/{state,ledger,rule_engine,features}.py` (Planet/Fleet/Player/Global/BattlefieldState, strategic value 1–100 decomposable, ArrivalLedger/ThreatLedger, ECA RuleEngine wiring the FlightOracle gate) + `tests_orbit/test_state_ledger.py` (5/5 PASS); `arena/validate.py` clean (no regression). Schema: `discussions/2026-06-16-battlefield-state-schema.md`.
- **P1 OW-…-DATASET-001** (prompt `04`): replay episode index + candidate/action-label tables over the 20G corpus; FlightOracle for safety/first-hit labels; data-quality report; no large raw replays committed.
- **P1/P2 prompt `05` (loop)**: snorlax candidate-scorer / value-model training (NOT run this session).
- **P2 prompt `06`**: hybrid policy integration (model score + rule filters + FlightOracle gate + rules-only fallback) (NOT run this session).
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
