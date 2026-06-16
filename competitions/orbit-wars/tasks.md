# Tasks — Orbit Wars

> Derived from issue #87 TODO/Plan table (T1–T16). Full English tracking in `tracking.md`.

## Now
- **v4 "Scheduler"** (hub-and-hammer, T9/T13): at parity with v3.2 (49.3% on 150 paired seeds). OVERKILL-revival
  **closed FAILED (2026-06-16), all 4 sub-cuts**: v4a counter-attack window (`OW_V4A`) null −0.3pt; v4f FM3
  best-response (`OW_V4F`) −9pt; v4c cluster hammer (`OW_V4C`) null −0.3pt; v4i Isaiah two-band (`OW_V4I`)
  inert→−1.0pt (games end ~step 152, never reach its endgame phase). All vs evogen @150 seeds, all default-OFF.
  Diagnostics confirm the bottleneck is the strong-tier cliff itself (v4 ~1–2% vs kuni05), not a missing
  concentration lever — next real lever must be integrated, not another bolt-on/knob. See
  `postmortems/2026-06-16-overkill-revival.md`.

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
