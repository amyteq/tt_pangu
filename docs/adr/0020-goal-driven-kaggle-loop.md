# ADR-0020: Goal-driven Kaggle loop

## Status

Proposed (M14, 2026-06-10). Subject to confirmation on the M14 proposal issue after the Discovery / Debate Gate transcripts at `docs/evidence/m14/T000/discovery/` have been reviewed, and after the five human decisions in `docs/milestones/m14/loop-prompts.md` §"Human decisions needed before starting M14" are pinned.

Supersedes nothing; builds on ADR-0006 (configurable approval gates) and ADR-0010 (per-job-type model routing). Cross-references ADR-0008 (artifact storage local-first) and ADR-0018 (generalized competition type).

## Context

M0–M10 shipped the platform's single-shot Kaggle path: register a competition, build a baseline notebook, pass the `kernel_push` reviewer gate, push **one** human-approved kernel, watch it to terminal, record the submission. M10's final review (`docs/milestones/m10/final-review.md`) confirmed the loop runs end-to-end but also surfaced its limits: push #1 stalled QUEUED ~66 min and never ran; the watcher used a fixed 60 s cadence; there was no notion of a *target* the loop was working toward, no parallel exploration, no concurrency accounting, and no automatic escalation when progress stalled.

M14 lifts the platform from "one approved push" to a **goal-driven loop**: declare a target up front, fan out candidate experiments locally, screen them by holdout CV, push the survivors to Kaggle under per-competition concurrency limits, poll with adaptive cadence + batched status reads, write LB scores back to the DB, and either iterate to the next batch or escalate to a human when the idea well is dry.

This ADR pins the architectural decisions; the companion [`docs/architecture/goal-driven-kaggle-loop.md`](../architecture/goal-driven-kaggle-loop.md) carries the ASCII data-flow, table layouts, state-machine diagram, and payload shapes the decisions imply. The ten task specs `docs/tasks/m14/M14-T000-*.md` … `M14-T009-*.md` implement it.

Inputs that shape this ADR:

- ADR-0006 (configurable approval gates) — the new per-batch push budget and the `kaggle.exploration_stuck` decision_type follow the same per-project / per-competition / per-job override pattern.
- ADR-0010 (per-job-type model routing) — `propose-next` (T006) reuses `src/worker/routing.py`'s `research` route; no parallel router.
- M10-T004 / M10-T007 — the `kernels output`-size terminal detection fallback, the QUEUED-stall failure mode, and the audit-grep sentinel ("0 lines reach `kaggle kernels push` from any non-approved process") are all preserved, not regressed.
- Discovery / Debate Gate (M9.4) — the three transcripts at `docs/evidence/m14/T000/discovery/` (legacy-archaeologist SKIP-NOTE, requirements-skeptic, design-red-team) informed every decision below. Where the red-team flagged an `open_disagreement`, the resolution is noted inline under the relevant decision.

## Decision

The goal-driven loop ships as an eight-decision package.

### 1. `goal.md` schema — score-primary, rank-secondary, with explicit exit_strategy

A goal is declared per competition. The DB `goals` row is authoritative; `experiments/<comp>/goal.md` is a human-readable mirror for git history. The schema:

```yaml
# experiments/<comp>/goal.md  (front-matter mirror of the goals row)
competition: tpu-getting-started
target_lb_score: 0.85          # primary — absolute, metric-direction aware
target_lb_rank: 30             # secondary — percentile or absolute rank; nullable
target_rank_kind: percentile   # 'percentile' | 'absolute'; only meaningful with target_lb_rank
deadline: 2026-07-01           # nullable; the competition deadline or an earlier self-imposed one
exit_strategy: first_reached   # 'first_reached' | 'all_required' | 'score_only' | 'rank_only'
max_total_pushes: 20           # hard ceiling on real pushes across the whole exercise
stuck_threshold: 3             # N consecutive non-improving submissions before escalation
status: active                 # 'active' | 'reached' | 'closed' | 'abandoned'
```

- **`target_lb_score` is the primary goal type.** Resolving the red-team / skeptic concern that `target_lb_rank` requires a live leaderboard read on every tick: rank is **secondary and best-effort**. The loop's primary stop signal is the absolute score, which is recorded on `submissions.public_lb_score` and evaluable offline. Rank is refreshed only on a terminal LB write (not every poll tick) and may be NULL if the rank read fails — a NULL rank never blocks the loop.
- `exit_strategy` makes the goal-met predicate explicit: `first_reached` (score OR rank, default), `all_required` (score AND rank), `score_only`, `rank_only`. This pins skeptic explicit_unknown on `target_lb_rank` primacy (human decision 1).
- `max_total_pushes` (default 20) is the hard ceiling enforced by T008's loop, independent of the per-day budget.
- `stuck_threshold` (default 3) is the T007 detector's N (human decision 4).

### 2. `goals` table + FKs — new table, FK from `submissions`, no `experiment_runs` schema change in this decision

```
goals
  id                uuid pk
  competition_id    uuid not null  -> competitions(id) on delete cascade
  target_lb_score   numeric(10,6)  nullable
  target_lb_rank    int            nullable
  target_rank_kind  text           check in ('percentile','absolute'); nullable
  deadline          timestamptz    nullable
  exit_strategy     text not null  check in ('first_reached','all_required','score_only','rank_only')
  max_total_pushes  int not null   default 20
  stuck_threshold   int not null   default 3
  status            text not null  check in ('active','reached','closed','abandoned') default 'active'
  created_at        timestamptz    default now()
  closed_at         timestamptz    nullable
  closed_reason     text           nullable
```

- **FK from `submissions`:** add `submissions.goal_id uuid references goals(id) on delete set null` (nullable — M10's existing submissions predate goals and must keep working). This is how a batch of pushes is attributed to the goal it was working toward.
- **One active goal per competition** is enforced by a partial unique index `(competition_id) where status = 'active'`. A second `goal init` on a competition with an active goal refuses unless `--close` was run first.

### 3. `experiment_runs` loop metadata — new nullable `analysis_jsonb` column, NOT a `text→jsonb` cast

The loop needs five keys per run: `exploration_batch_id`, `parent_run_id`, `queue_time_seconds`, `running_time_seconds`, `escalation_id`.

**Resolving the red-team's first open_disagreement and skeptic edge_cases.5 / rollback.1:** `experiment_runs.analysis` is `text` on the live schema (`supabase/migrations/0004_m4_competition_repo.sql:61`) and M10 wrote free-text into it. A forward-only `text → jsonb` cast risks corrupting those rows and is hard to revert. M14 therefore adds a **new nullable `analysis_jsonb jsonb` column** alongside the existing `analysis text`, leaving M10's data untouched. The five loop keys live in `analysis_jsonb`. The existing `metrics jsonb` column keeps holding *metric values* (`holdout_accuracy`, `macro_f1`, `train_seconds`) — the grain split M2/M9 established is preserved (this rejects the red-team's `metrics-jsonb-reuse` alternative, which would overload `metrics`).

`exploration_batch_id` is a UUID minted by `kca explore init`; it lives on `analysis_jsonb`, not in a separate table. The red-team's `separate-exploration-tables` alternative was considered and rejected for M14: the batch lifecycle is light enough (init → fan-out → screen → rank → promote) that a JSONB key plus a filtered query is sufficient, and it avoids a second writer surface for T003/T005 to drift against. If M15 needs cross-competition batch analytics, promoting to a real `exploration_batches` table is a clean follow-up.

### 4. Search-space spec — YAML cross-product, with optional random sub-sample

`kca explore init --search-space <yaml>` reads a declarative axes file:

```yaml
# search-space.yaml
axes:
  backbone:    [mobilenet_v2, efficientnet_b0, resnet50]
  image_size:  [192, 224]
  epochs:      [3, 6]
sample:        full            # 'full' (cross-product) | {random: N, seed: 42}
seed_template: experiments/<comp>/baseline-tl/baseline.py
```

- The default is the **full cross-product** (here 3×2×2 = 12 cells). A `sample: {random: N, seed: S}` draws N cells deterministically so a large axis set does not explode the fan-out.
- Chosen over JSONL because the axes form is human-authorable and diff-reviewable, and the cross-product is mechanical. JSONL would force the human to pre-expand the product (error-prone) and lose the axis-level intent the stuck-detector's "tried strategies" table reads.
- Each generated cell becomes one `experiments/<comp>/<run-id>/` directory with a `baseline.py` templated from `seed_template`, plus a `cell.yaml` recording the axis values. The batch's manifest is `experiments/<comp>/<batch-id>/batch.yaml`.

### 5. Exploration-batch lifecycle — five states, file + DB dual-write

`init → fan-out → screen → rank → promote`:

1. **init** — `kca explore init` mints `exploration_batch_id`, writes `batch.yaml` + per-cell dirs, and creates one `experiment_runs` row per cell with `status='planned'` and `analysis_jsonb.exploration_batch_id` set. **Resolving skeptic side_effects.2 (orphan runs):** planned-but- never-screened runs are GC-able by `exploration_batch_id` + `status`; `kca explore` provides a `--prune` path (T003 scope) and the stuck-detector counts only `status in ('screened','pushed')` rows as "tried strategies", not `planned`.
2. **fan-out** — `kca explore run --batch <id> [--max-concurrent N]` dispatches local screenings via a process pool. N defaults to a GPU-memory-aware value (1 if no GPU; else `free_vram // est_cell_vram` capped at the axis count). On a CPU-only host it runs serially with a logged warning (resolves skeptic hidden_constraints.5).
3. **screen** — each screening writes `holdout_accuracy`, `macro_f1`, `train_seconds` to `experiment_runs.metrics` and flips `status='screened'`.
4. **rank** — `kca explore rank --batch <id> [--json]` lists screened cells sorted by `holdout_accuracy`, marking which **qualify**: a cell qualifies if `holdout_accuracy >= goal_screen_threshold`, where the threshold is a heuristic fraction of `target_lb_score` (default 0.90 × target, configurable). This is a screen, not a guarantee.
5. **promote** — the top-K qualifying cells are eligible for `kca kaggle push` under the T004 concurrency gate. Promotion sets the pushed run's `submissions.goal_id` and `analysis_jsonb.exploration_batch_id`.

**One active batch per goal** at a time (resolves red-team open_disagreement 2 / skeptic edge_cases.3): `kca explore init` refuses if the goal already has a batch in `init`/`fan-out`/`screen`. Sequential batches are the iteration unit; overlapping batches are out of scope for M14.

### 6. Smart-polling state machine — QUEUED Fibonacci ramp, RUNNING stable, size-fallback terminal

`_watch_kernel_until_terminal` (`tools/kca/kg.py:280`) is revised — **not replaced** — into a three-state machine:

| State | Cadence | Detection |
|---|---|---|
| QUEUED | Fibonacci ramp `[60, 90, 150, 240, …]` capped at `⅓ × estimated_queue_time` | `kernels status` == queued/not-started |
| RUNNING | stable 300 s | `kernels status` == running |
| TERMINAL | exit | `kernels status` terminal **OR** `kernels output` size>0 |

- `estimated_queue_time` = median of the last 5 same-accelerator pushes for this competition (from `analysis_jsonb.queue_time_seconds`); default 15 min if no history.
- **Resolving the red-team's dropped-capability flag (kg.py:308-321) and skeptic edge_cases.2:** the size-based terminal oracle (`kernels output` log size > 100 bytes) is **kept as the authoritative terminal check**. `kernels status` is used only to classify QUEUED vs RUNNING for cadence; a 500/503 from `kernels status` is explicitly treated as **non-terminal, no state change** (the M10-observed 500-on-fresh-push bug must not be read as terminal or as an error).
- **QUEUED-stall timeout (resolves skeptic edge_cases.1 / red-team ops_burden):** a kernel that stays QUEUED past `max_poll_minutes` (default 60, matching M10) is declared `stalled`, the watcher exits non-terminal, and the slot is **released** from the concurrency count with a `stalled` marker on the submission so it does not deadlock the loop forever.
- `_watch_many(kernel_refs)` does ONE `kaggle kernels list -m --page-size 100` per tick and parses per-slug; it activates only when **≥ 2 slugs** are tracked. The single-slug auto-watch on `cmd_push` (kg.py:268-275) is preserved verbatim (resolves red-team dropped-capability 2).
- `queue_time_seconds` and `running_time_seconds` are recorded **separately** on `analysis_jsonb` so the estimator has data.

### 7. Concurrency + daily-budget gate — in `cmd_push`/`cmd_submit`, credentials pre-check first

`cmd_push` gains, **in this order, before the approval gate fires** (resolves issue #62 and the red-team's cmd_submit-envelope dropped-capability flag):

1. **Credentials pre-check** — mirror `cmd_submit`'s envelope verbatim (`tools/kca/kg.py:145-162`): refuse with `{"ok": false, "error": "KAGGLE_USERNAME not set; cannot submit"-shaped, "competition": ..., "side_effect": ...}` when `KAGGLE_USERNAME`/`KAGGLE_KEY` is absent.
2. **Concurrency gate** — count active kernel runs KCA owns for this competition (latest version per slug, status != TERMINAL/stalled); refuse cleanly when `competitions.max_concurrent_pushes` is reached; emit the active-runs list in the JSON response.
3. **Daily-budget gate** — count today's submissions for this competition; refuse past `competitions.max_daily_submissions`; back off until the window opens.

- **Submission-window semantics (resolves skeptic hidden_constraints.2):** M14 uses **UTC calendar day** as the budget window, matching CLAUDE.md's KCA "00:00 UTC roll-over" strategy. The T005 loop-prompt's "24h rolling" wording is reconciled to UTC-day here; the M14 proposal issue records this as the pinned choice.
- **Kaggle's real limits are unknown a priori (skeptic hidden_constraints.1):** the columns are KCA's best-effort guess populated by T001's rules ingestion. The gate is a *courtesy* guard; Kaggle's own 429/400 remains the hard authority. If a push the gate permitted is rejected by Kaggle, T004/T008 **halt** per the milestone stop criterion — they do not silently retry.
- The gate stays in `cmd_push`/`cmd_submit` (CLI layer), not `ToolExecutor`. The red-team's `push-gate-in-worker-not-cli` alternative is acknowledged: T004 must verify no worker path reaches `kaggle kernels push` *bypassing* `cmd_push`; if one exists, the gate moves to `ToolExecutor` as a follow-up (open_disagreement 4 → T004 acceptance check).

### 8. Stuck detector + escalation — reuse the reviewer / Approval Inbox surface; new decision_type

- **Reuse, not replace.** The escalation surface is the existing `human_decisions` + Approval Inbox (`services/decision_api/app.py`, `ui/src/pages/ApprovalInbox.tsx`). T007 adds a new `decision_type=kaggle.exploration_stuck` and extends the reviewer's `DEFAULT_TRIGGER_OPS` (`src/worker/reviewer.py:20-34`) — it does not build a new inbox.
- **Detector heuristic:** fires when N (= `goal.stuck_threshold`, default
  3) **consecutive submissions show no monotone LB improvement** AND idea-sourcing (`kca explore propose-next`) returned **0 fresh candidates**. **NULL-score rule (resolves skeptic edge_cases.4 / red-team open_disagreement 3):** a submission with NULL `public_lb_score` (the M10-T004 case) is "no result" — it **does not advance and does not reset** the non-improving counter; only scored submissions move it.
- **Escalation payload shape** (`docs/escalations/<comp>-<ts>.md` + the `human_decisions.payload`): goal vs current; table of tried strategies (axis values + holdout + LB per `screened`/`pushed` run); sources consulted (T006 `source_url` + `trust_label`); ruled-out hypotheses; concrete questions. **Redaction (resolves red-team dropped-capability 4 / skeptic side_effects.4):** the payload passes through a `_redact_tool_input`-style filter (`src/worker/reviewer.py:96-118`) so no DSN / credential / flag is rendered into the committed doc or the audit row.
- **Resume:** a human response (UI form or `kca decisions approve --notes "<direction>"`) becomes the new exploration seed; the loop reads the notes for a structured option or free-text direction and resumes with a fresh batch. Telemetry: escalation count + time-to-resolution per competition.
- **Per-batch push approval (human decision 2):** the `kernel_push` gate fires **once per batch**, not per push. The batch budget (e.g. "up to 5 pushes today toward this goal") is recorded as a single `human_decisions` row, NOT in `goal.md` (resolves skeptic rollback.3 / red-team open_disagreement 5: a revert can invalidate the `human_decisions` grant; a `goal.md` value could not be reliably un-granted). The budget **expires at UTC midnight** and must be re-approved the next day.

## Consequences

- **Positive.** The platform gains a target-tracking loop: declare a goal, fan out, screen, push survivors under a courtesy gate, poll adaptively, and escalate cleanly when stuck. Every step is auditable via `goals` / `submissions.goal_id` / `analysis_jsonb` / `human_decisions`.
- **Positive.** Adding a nullable `analysis_jsonb` column (decision 3) leaves M10's `analysis text` data untouched and is trivially reversible (`DROP COLUMN`), unlike an in-place cast.
- **Positive.** The smart-poller (decision 6) keeps the M10-discovered size-fallback terminal oracle and adds a QUEUED-stall release, fixing the exact 66-min-deadlock M10-T004 hit without regressing 500- resilience.
- **Negative.** The concurrency/daily gate is a best-effort guard, not a guarantee — Kaggle's real limits are not published. A wrong column value can still produce a Kaggle 429/400; mitigated by the halt-on- Kaggle-error stop criterion and by exercising the gate against a fixture before any live push (T004).
- **Negative.** Loop metadata in `analysis_jsonb` (decision 3) means `kca explore rank` and the stuck-detector query a JSONB key rather than a typed column; a future cross-competition batch analytics need would warrant promoting to a real `exploration_batches` table (M15+).
- **Negative.** Per-batch (not per-push) approval (decision 8) means one human grant authorises multiple real pushes; mitigated by the UTC-midnight expiry, the `max_total_pushes` ceiling, and the per-push audit row.
- **Deferred.** Cross-account quota pooling (issue #21), the `approved_by_user_id` FK hardening (issue #60), dataset/model uploads, and a competition portfolio beyond `tpu-getting-started` are all M15+.

## Known gaps / follow-ups (surfaced by the T008 live run)

The single sanctioned live multi-push series (M14-T008, evidence `docs/evidence/m14/T008/live-run.md`) surfaced two gaps that are **documented here but deliberately not redesigned in M14**:

- **Kernel push ≠ leaderboard submission (architectural gap).** The goal loop pushes a kernel (`kaggle kernels push`) and the smart-poller watches it to a terminal state, but a kernel *run* does not by itself create a competition leaderboard submission. In T008 both pushed kernels reached terminal status yet `kca kaggle score` returned `match_count: 0`, so no new `public_lb_score` was recorded and the goal could not advance on real LB signal. The loop needs an explicit **submit step** — either `kaggle competitions submit` of the kernel's output CSV, or the kernel's "Submit to Competition" action — between push-terminal and `kca kaggle score`. This is an M15 deliverable; tracked as a follow-up issue (see Cross-references). Until then, a goal driven purely by kernel pushes will read its best-known LB from prior direct submissions only.
- **`kca competition refresh-rules` version dependency.** The rules auto-ingest path calls `kaggle.api.competition_view`, which was **removed in kaggle CLI 2.0.x** (2.0.1 raises `'KaggleApi' object has no attribute 'competition_view'`). As of M14-T009 the path degrades cleanly: it raises a typed `KaggleApiUnsupported` and the CLI emits a `{"ok": false, "error_code": "KAGGLE_API_UNSUPPORTED", "degraded": true}` envelope (no traceback), so an operator falls back to setting `max_daily_submissions` / `max_concurrent_pushes` manually. Porting the rules fetch to the current Kaggle API surface is an M15 follow-up.

## Cross-references

- [`docs/architecture/goal-driven-kaggle-loop.md`](../architecture/goal-driven-kaggle-loop.md) — ASCII data-flow, table layouts, state-machine diagram, escalation payload schema, audit-grep sentinel inheritance.
- [`docs/evidence/m14/T000/discovery/SKIP-NOTE.md`](../evidence/m14/T000/discovery/SKIP-NOTE.md) (legacy-archaeologist skip — greenfield).
- [`docs/evidence/m14/T000/discovery/requirements-skeptic.md`](../evidence/m14/T000/discovery/requirements-skeptic.md)
- [`docs/evidence/m14/T000/discovery/design-red-team.md`](../evidence/m14/T000/discovery/design-red-team.md)
- ADR-0006 (configurable approval gates) — per-batch push budget + `kaggle.exploration_stuck` reuse the gate plumbing.
- ADR-0010 (per-job-type model routing) — `propose-next` reuses the `research` route; no parallel router.
- `docs/milestones/m10/final-review.md` — the single-push baseline + the QUEUED-stall and `kernels status` 500 history this ADR designs around.
- `docs/architecture/discovery-debate-gate.md` — the gate this task exercises.
- `docs/tasks/m14/M14-T000-goal-loop-architecture.md` … `M14-T009-*.md` — the specs this ADR fulfils.
