# Tracking — Orbit Wars

> English consolidation of GitHub issue **#87** ("[Orbit Wars] 长期跟踪与策略讨论"). Original Chinese tables
> preserved verbatim in [`tracking_zh.md`](./tracking_zh.md). Future status updates live here, not in issue #87.
> **Authority (ADR-0022 §3):** this file is rank 3 — narrative, reasoning, experiment history.
> `state` / `status` / `best` live in `competition.yaml` (rank 1); if this file disagrees with
> it, this file is stale. "Status updates live here" means the *narrative* left the issue.
> `unknown` = not in available evidence.

## Current snapshot
- **$50,000 Featured, μ-ladder, deadline 2026-06-23** (final eval ~2 weeks after); id 138420; 5/day, latest-2 scored.
- 🔴 **Format correction (2026-06-15, KCT-OW-LIVE-002, verified from our own kuni05 submission's 205-episode history — `flyingfox` = harrysun2006's profile name = US, sub 53582503, not an external competitor — via `ListEpisodes` API):**
  the ladder runs **BOTH 2p AND 4p FFA** episodes and **both update μ** — ~half the games are 4p (net μ ~83% 2p / ~17% 4p).
  The prior "1v1 only / 4p robustness-only" assumption (T7) was WRONG; our whole line was tuned 2p-only.
  4p gate now exists (`arena/eval_4p.py`); naive 4p-aware mode (`OW_4P_MODE`) tested NEGATIVE → default OFF; situational 4p = T18.
  See `EPISODES.md` analysis #3.
- Direction **D1 = C** (low-cost continue). Incremental path largely exhausted (7 single-mechanism levers failed);
  strong tier wins as integrated systems.
- **Ladder (refreshed 2026-06-14, read-only Kaggle):**
  - harrysun2006 latest-2: adapted-kuni05 (attributed) **1085.4** + v3.2 **660.0**
  - firefly2006 (may) latest-2: v3_2_coarr **648.8** + v3.2 **636.7**
  - retired peaks: adapted-kuni05 **1151.0**, Forecast v3 686.1, v2.1 555.8
- 🟢 **orbit5 cycle 2026-06-16:** stopped gating on local arena (Harry: it under-discriminates our cluster →
  test shelved candidates on the REAL ladder; only >1200-in-reasonable-time keeps a slot). **Submitted 2**:
  harry ← `v4_scheduler.tar.gz` (keeps kuni05 1079.7 anchor), may ← `v3_forecast.py` (keeps coarr 640.7). Active
  slots (refreshed 2026-06-16, COMPLETE): harry [**v4 703.9**, kuni05 **1069.9**], may [**v3 678.1**, coarr **644.4**]
  — v4/v3 settled ≈ predicted (~700/~686), both < the >1200 bar; kuni05 our best (drifting 1085→1070). **Arena reliability (calibrated):** local
  win% vs evogen separates GROSS tiers (kuni05 90% ≫ ours ≤20% ↔ ladder 1083 ≫ 640–686) but is BLIND within our
  cluster (v3 μ686 & v3.2 μ640 both 16.7%; v4 best 20.0%). Fleet-massing discussion → T19–T22 + rotation-relay
  PARK (`tasks.md`); relay rigorously refuted (riding ≤2.35 < flying 2.39 u/step). **DOC FIX: `flyingfox` =
  harrysun2006's profile name = US** (so sub 53582503 = our adapted-kuni05; the "flyingfox 205-episode" 4p finding
  was our OWN history, label only). Episode 80118852 = our kuni05's 4p WIN, and it CONFIRMS an early 多而小 weakness:
  early (≤step80) median launch **20 ships**, behind at step40 (5 vs 7 planets), massing only mid/late (median
  238 late). Mass-earlier is the real lever (T20/T21). Monitor μ via `ops/live_loop.py --once`.
- 🟢 **Strong-tier foundation (2026-06-16, prompts 01/03):** built the deterministic execution +
  battlefield-awareness substrate `core/` (geometry + FlightOracle + ArrivalLedger + typed
  BattlefieldState + ECA RuleEngine) the hybrid/model plan sits on — `tests_orbit` 11/11 pass,
  `arena/validate.py` clean (no agent regression). Schema: `discussions/2026-06-16-battlefield-state-schema.md`.
  Plus the replay **dataset pipeline** `datasets/` (prompt 04): episode index + step + candidate
  tables with FlightOracle safety/first-hit labels (fixture smoke OK; 20G corpus → snorlax).
  ✅ FlightOracle gate now WIRED into `agent/main.py` emission (prompt 02 — `core/action_sanitizer.py`
  + `_emit_gate`, import-guarded; verified active, 0 false-positives on v3.2, no regression; activate on
  ladder via `main.py+core/` tar.gz). Next: model training (05) → hybrid (06) → ladder loop (07) toward μ≥1200.
- 🟡 **Model training + hybrid (2026-06-17, prompts 05/06) — infra GO, model REJECTED.** Rebuilt the corpus
  from **310 REAL ladder episodes** (subs 53582503/53730511, fetched read-only; 2.48M candidates) and trained the
  candidate scorer (MLP, valid **AUC 0.882**; `agent/hybrid_weights.json`, pure-Python online, p99 44ms). Wired as
  an additive re-ranker in `agent/main.py` (`OW_HYBRID`; β=0 byte-identical to v3.2; `agent/versions/hybrid_v0.py`).
  **Arena A/B (240g/cell): strong-tier FLAT** — vs evogen1093 13.8%→13.8–14.6%, vs kuni05 0.8%→0.8% (crushed,
  avg 17 vs 2315); weak/4p non-regressive; crash-safe. **VALIDATION #3 (+7pt) NOT met → not submitted**
  (`live/last_eval.json` submit_ready=false). 3rd confirmation that offline AUC ≠ ladder strength (INS-003); the
  cliff is candidate-GENERATION/strategy, not ranking (INS-008). Compute: local HARRY-ARCH (snorlax off + GPU-useless
  for a CPU MLP). Postmortem `2026-06-17-hybrid-v0.md`; card `models/reports/model_card_20260617-cs-ladder310.md`.
  Next: strong-tier-teacher corpus (μ>1240 episodes) and/or past-imitation generation.
- 🟢 **Ladder loop cycle 2026-06-17 (prompt 07, OW-LADDER-LOOP-001) — NO_SUBMIT; corpus built.**
  Bounded cycle: (a) **execution-safety audit** over 60 cached real-ladder replays (10,648 of our
  launches via FlightOracle) — **0 strict-sun, no fix_required**; the ~11% `first_hit` "oob" is a
  trace artifact (winner 11.0% ≈ loser 10.8%, non-causal; sanitizer blocks 0 → B11). (b) **early-stop:**
  kuni05 (53582503, μ~1077) = keep anchor; v4 (53730511, ~700) / v3 / coarr = weak-but-retained (no
  validated >1200 replacement; hybrid_v0 rejected). (c) **NO_SUBMIT** — no candidate beats the strong
  tier; budget/quota untouched. (d) **idle task = built the strong-tier-teacher corpus manifest**
  (`datasets/strong_corpus/`, 1272 strong-vs-strong episodes μ≥1200) via `ops/discover_strong_corpus.py`;
  fetch/build/train queued (`live/parallel_work_queue.md`). (e) fresh ListEpisodes refresh **blocked by
  HTTP 429** (added backoff to `ops/episode_discover.py`); μ from this session's earlier queries.
  Distance to target: **kuni05 ~1077, ≈123 below μ1200**.
- 🟢 **Submit override (2026-06-17, Harry-directed): hybrid_v0 ladder-probe ×2.** Harry: *"any agents
  <1200 can be replaced; submit to both accounts to collect more episodes."* So the cycle's NO_SUBMIT was
  superseded: built + validated the `hybrid_v0_submission.tar.gz` (v3.2 + model re-ranker, OW_HYBRID baked,
  core/+weights bundled; clean-extract validated: hybrid active, crash-free, p99 59 ms) and submitted it as
  a **ladder-probe** (failed local +7pt gate but qualifies for the exception) to **harry `53767016`**
  (latest-2 [hybrid_v0, v4]; kuni05 evicted) + **may `53767026`** (latest-2 [hybrid_v0, v3]; coarr evicted).
  Both `neutral`, awaiting episodes — the goal is real-ladder data on the model-integrated agent (orbit5
  thesis: local under-discriminates). Next: after 10/20 eps, track 53767016/53767026 → early-stop; in
  parallel, fetch the strong-corpus → retrain a stronger scorer.
- 🟢🔑 **CRITICAL BUG FIX (2026-06-17, user-reported): planet-rotation off-by-one (B11).** Harry flagged a
  fleet flying into the sun (ep 80276901, sub 53767016, ~step 20). Traced to a 1-tick phase error: the
  engine observes orbiting planets at `rotate(init, ang_vel*max(0,step-1))` but ALL our predictors used
  `ang_vel*step` (one tick ahead). This mis-aimed every intercept (~1.6u, into the sun for sun-line
  targets) AND made `FlightOracle.first_hit` phantom-hit planets, masking sun/OOB so the sanitizer
  didn't block. **Fixed** in `core/geometry.planet_pos` + `agent/main.py._planet_pos`/`._predict_pos`
  (`_predict_pos(t-1)==obs(t)` verified). **Impact: fixed-v3.2 beats buggy-v3.2 95% (200g); vs evogen
  13.8%→45.0% (+31pt); sun launches 0%, oob 0.5% (was ~9%); 4p avg_rank 1.72.** tests 4/4. **The
  evogen cliff was largely THIS BUG, not strategy** (INS-009; revises the 13-levers-refuted narrative).
  kuni05 still ~1% (separate gap). Fixed tarball `v3_2_rotfix_submission.tar.gz` built + validated;
  **submit to ladder PENDING Harry's go-ahead** (the live probes 53767016/53767026 carry the bug).
- 🟢 **Layered-architecture refactor (2026-06-18, prompt 08, OW-ARCH-001).** Split the monolithic
  `agent/main.py` (now a 62-line thin entrypoint) → `core/policy.py` (v3.2 core + the documented
  8-layer data-flow); deduped all physics to `core/geometry.py` (`agent/utils.py` → thin wrapper).
  P0 correctness: in-flight fleets decoded from current `(x,y)` (`FlightOracle.trace_from_position`/
  `decode_existing_fleet` + `core/state.py`); intended target IDs preserved through `core/action_emitter.py`
  → `core/action_sanitizer.py` (wrong-first-hit gate opt-in); features split own/enemy/neutral (25-dim).
  New `core/candidates.py::CandidateAction`; `core/rule_engine.py` wired (pass-through default). **Config
  layer:** `core/config.py` centralizes all 33 `OW_*` (env→baked→literal); YAML `config/*` baked PyYAML-free
  to `agent/config_baked.py` (`config/bake.py --check`). **Behavior byte-identical** (golden 526-record
  obs→moves = 0 mismatches; arena `validate.py` **100% vs v2/v1/starter/random**; mirror vs frozen pre-B11
  v3_2 = 91.7%, i.e. the B11 fix). **Caught + fixed B12** — the refactor's thin shim referenced `__file__`
  at load, which kaggle's `exec(code, {})` leaves undefined → agent went silently passive (lost to random
  in the first arena run); fixed via a `sys.path`-scanning `_locate_core()` + a permanent regression test.
  10 `tests_orbit` files / 43 tests pass; `ruff check .` clean. No Kaggle ops. Follow-ups OW-ARCH-002..005 in
  `tasks.md` (chief: re-train the layer-5 scorer on the **25-feat** contract — the 24-feat weights now auto-disable).
- **Leaderboard top ~1746** (was ~1713 in the issue snapshot). **Cliff:** ~100% vs weak, **0–15% vs strong tier**
  (evogen 1093 / multifocus / kuni05 1240).

## Preserved issue tracking tables (translated → English)

### Open Discussions (all confirmed 2026-06-12)
| ID | Topic | Decision |
|---|---|---|
| D1 | Overall direction | ✅ **C** — low-cost continue (replay mining + suite param optimization) |
| D2 | Submission-slot strategy | ✅ submit locally-validated improvements; freeze + re-submit best-2 in the last 3 days |
| D3 | Compute | ✅ snorlax (RTX 4090, 24-core) for large sweeps; SSH verified (PR #89) |
| D4 | RL/distillation route | ✅ try on snorlax; submit only if it beats incumbent via the T10 gate → T12 |
| D5 | Comment-marking permission | ✅ allowed (inline marks) |

### TODO / Plan (T1–T16)
| ID | Task | Status | Evidence |
|---|---|---|---|
| T1 | Replay mining (public episode dataset → heuristic params) | 📋 queued | issue #87 |
| T2 | Suite systematic param optimization (`OW_*`) | ✅ **R2 positive → t14 baked as v3.2 (+7pt)**; 6/6 VALIDATION | issue #87; `sweep_opt.py` |
| T4 | Endgame + Comet module | 📋 queued | issue #87 |
| T5 | Ladder monitoring + status-table upkeep | 🟢 ongoing | issue #87 |
| T6 | Confirm eval-side torch usable | ✅ done (kuni05 torch ~1137/1151) | issue #87 |
| T7 | 2p/4p split strategy | ❌ rejected (ladder is 1v1; 4p = robustness only) | issue #87 |
| T8 | True co-arrival (synchronized arrival) | ✅ real but +3pt (evogen layer only; 0 vs strong tier) → default OFF (`OW_COARRIVAL`) | issue #87 |
| T9 | §7 architecture → v4 "Scheduler" (hub-and-hammer; merges T13) | 🟢 platform built; **parity with v3.2 (49.3%)**, iterating | issue #87; PR #92 |
| T10 | Local validation checklist (`VALIDATION.md`) | 🟢 ongoing (must pass arena gates before submit) | `VALIDATION.md` |
| T11 | Dynamic defense reserve (ledger constraint) | ❌ no-op (constraint never triggers) | issue #87 |
| T12 | RL/distillation (BC kuni05/top-6 → policy net) | 🟢 background — v0/v1/v2: high imitation, ~0% arena (BC shift) | issue #87 |
| T13 | Dynamic strategy ID & counter | 🟢 merged into v4 (posture v1 ❌; counter-attack window → v4) | issue #87 |
| T14 | Short-hop supply chain | ❌ no gain (mechanical forwarding) | issue #87 |
| T15 | Comet trajectory prediction (model `comets` path → feed `project()` swept-collision + `_path_blocked`; close §9-1 gap) | 📋 chartered — **measure-first**: comet incidence + decided-games in episode dataset gates the build; env-gated `OW_COMET` | issue #87 |
| T16 | Sun/planet-avoidance waypoint routing (blocked direct path → tangent re-aim / 1-hop relay; §9-1 gap) | ◻︎ **measured → PARK** (2026-06-15). Instrumented twin `forecast_measure.py` (8/8 identity-proven) over 80 games: value-positive launches dropped by `_path_blocked` are frequent (107/game starter, 639 mirror) but the recoverable value is **loose-optimistic 17–26% → realistic 6–15% of committed** after 3-agent adversarial review (only 35.5% of "recoverable" drops are value-positive; **41% of dropped targets are captured anyway within 5 turns**; re-aim haircut). **≈1.4–2.7pt win-rate < +7pt bake bar**, same frequent-gap-→-ladder-null mechanism as T8 co-arrival. Reopen only via a gate-only prototype if v4 stalls. | issue #87; `arena/measure_t16.py` |

### §9 priority completion (ChatGPT framework)
| Item | Completion | Gap |
|---|---|---|
| 1. Exact geometry + ETA | ~85% | sun-avoidance waypoint routing → **T16**; comet trajectory → **T15** (both chartered 2026-06-14, measure-first) |
| 2. Dynamic defense reserve | ~70% | unified ThreatLedger timeline → v4 |
| 3. ROI expansion | ~90% | opening-sequence (salvo failed) |
| 4. Synchronized attack | ~80% (done) | replay correction: single-strike scale > sync form |
| 5. 2p/4p split | N/A | ladder is 1v1 only |
| 6. Large-sample local validation | ~80% | tactical event logging; 500+/config routine |
| 7. Lightweight fast online code | ~95% | basically none (single-file, ~4 ms/turn) |

### Levers (suite-gated results)
| Lever | Status | Result |
|---|---|---|
| Forward-sim differential value (v3) | ✅ kept | only big gain (556→686) |
| Phase-scaled in-flight cap (v2.1) | ◻︎ neutral | ~tie (harmless) |
| Defense reinforcement (v3.1) | ◻︎ self-play only | 0 suite gain |
| Consolidation / safe_drain / multi-source salvo / opening planner / PROJ_H scan / OW_* random | ❌ rejected | no gain or regression |
| OVERKILL multiplier | ❌ | monotonic negative |
| co-arrival (T8) | ◻︎ OFF | +3pt evogen layer only; on-ladder +~12 (may) |

## Agent / idea progress
- **Done & scored:** v1 → v2 → v2.1 (556) → v3 Forecast (686) → v3.1 → **v3.2 (660 current)** → v4 Scheduler (parity).
- **Two-track:** attributed adapted-kuni05 (1151 peak / 1085 current) as competitive entry + own Forecast line.
- **Closed routes:** 7 single-mechanism levers; BC distillation (high imitation, 0% arena).

## Local arena / evaluation status
- Parallel arena (`arena/pool.py`, ~30–40×, deterministic, 2p+4p); paired-seed A/B; **ladder-predictive suite gate**.
- Protocol: ≥150 paired seeds (±3.5pt) + ±7pt bake gate; `VALIDATION.md` 6 gates (crash 0 / weak-tier pass /
  4p avg_rank 1.01 / p99 8.3 ms / single-file). v3.2 passed 6/6.

## Kernel push / submission status
- Submission mode = **agent file** (no Kaggle kernel for this competition). All listed submissions `COMPLETE`.
- ⚠ **Refreshed 2026-06-14** via read-only Kaggle API (`kaggle competitions submissions`, both accounts). See `submissions.md`.

## Leaderboard / ladder status
- harrysun2006 latest-2: kuni05 **1085.4**, v3.2 **660.0**. firefly2006 latest-2: v3_2_coarr **648.8**, v3.2 **636.7**.
- Leaderboard top **~1746** (Isaiah @ Tufa Labs 1745.9, Jake Will 1740.8). Private LB `unknown` (not released).

## Version map
| Ladder μ | Version | Summary |
|---:|---|---|
| 279.0 / 385.3 | Value-targeting | first agents |
| 538.3 | Interceptor v2 | orbital lead + threat reserve |
| 555.8 | v2.1 | intercept economist + phase-scaled cap + frontier garrison |
| 686.1 | **v3 Forecast** | bit-exact forward sim + terminal differential net-ship value (was the own peak until v4 settled at 703.9) |
| ≈v3 | v3.1 | + sim-driven defense (self-play only) |
| 660.0 | **v3.2** | t14-tuned (H26/FF5/FD20/CE3.2/CL1.3); +7pt vs evogen; 6/6 gates (current own entry) |
| 648.8 | v3_2_coarr | v3.2 + co-arrival ON (may account; on-ladder +~12 vs v3.2) |
| **703.9** | **v4 Scheduler** | hub-and-hammer integrated rewrite; *local-arena* parity with v3.2 but the **best own-agent ladder μ we measured** (sub `53730511`, settled at the 2026-06-16 refresh) — the local gate could not see the gap (INS: arena is blind inside our cluster). Historical, later evicted; rank 1's final eligible `best.public_lb` is unknown |
| 1151.0 / 1085.4 | adapted-kuni05 | attributed public agent; competitive entry (peak / current) |

## Live loop (KCT-OW-LIVE-002, 2026-06-15)
- Bounded live-submission loop under `ops/` (credential-safe two-account status, episode ingest/analyze with
  sun-collision detection, slot classification, gated autonomous submit). Commands in `ops/README.md`; state
  in `live/`. Run one cycle: `python competitions/orbit-wars/ops/live_loop.py --once`.
- Cycle 2026-06-15 (read-only Kaggle): harry [kuni05 **1086.5**, v3.2 **655.7**]; may [v3_2_coarr **644.0**,
  v3.2 **630.1**]. **NO_SUBMIT** (no candidate beats an active slot; v4 = parity; budget/quota preserved).

## Evidence links
- GitHub issue #87 (body + 15 comments) — original hub. `tracking_zh.md` — original Chinese verbatim.
- `README.md` (detailed log), `EPISODES.md`, `LEAGUE.md`, `VALIDATION.md`; `worklogs/orbit.md`, `worklogs/orbit2.md`.
- `work/00.orbit.md` (A1/A2 analysis); `notes_zh.md` (EN digest). PRs #80 / #89 / #92.
