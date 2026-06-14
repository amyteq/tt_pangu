# M14 — Loop Prompts

_Goal-driven Kaggle workflow: turn the platform from "one approved push" into
"set a goal, explore in parallel, push within Kaggle's rules, poll smartly,
escalate when stuck."_
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M10 exit confirmed (notebook-submission path validated;
see `docs/milestones/m10/final-review.md`). M11 (CTF), M12 (Devpost), M13 (eval
suite) are NOT prerequisites._
_Shared rules: every Loop Prompt below MUST follow
`docs/milestone-loop-protocol.md` (sequencing, no real Kaggle / Anthropic
outside designated paths, DB DSN + sandbox bypass, per-milestone worktree
by default, secret denylist, Discovery / Debate Gate on `arch:` tasks)._

---

## M14 at a glance

M14 lifts the platform from M10's single-shot, human-approved push to a
**goal-driven Kaggle loop**: declare a target up front, fan out candidate
experiments locally, screen them by holdout CV, push the survivors to Kaggle
under per-competition concurrency limits, poll their kernel runs with adaptive
cadence + batched status reads, write LB scores back to the DB, and either
(a) iterate to the next batch when below goal, or (b) escalate to a human when
the idea well is dry.

The five user-surfaced bullets from PR #44 each become a numbered task in this
milestone, tracked by an `ai:triage` GitHub issue:

| Bullet / topic | Issue | M14 task |
|---|---|---|
| Goal setting at start of competition | #51 | T002 |
| Parallel exploration with local GPU screening | #52 | T003 |
| Multi-push concurrency within Kaggle rules | #53 | T004 |
| Smart polling: backoff + batched status reads | #54 | T005 |
| Human-in-the-loop escalation when stuck | #55 | T007 |
| Competition-rules ingestion (quota / accelerators / internet / deadlines / format) | #8 (parent), #7 (submission-format sub-task) | T001 |
| `cmd_push` missing `KAGGLE_USERNAME`/`KAGGLE_KEY` pre-check (M13 deviation) | #62 | T004 |
| Gate PRs on eval score-delta (per `docs/milestones/m13/final-review.md` follow-up 3) | #63 | T009 |

Related but **not** in M14's deliverable surface (cross-referenced from
the relevant Loop Prompt read-lists for context, no work scheduled):

- #21 — per-account quota pool. M14 ships the **single-account** primitive
  (T004); the multi-account variant is M15+.
- #60 — `approved_by_user_id` FK on `human_decisions`. M14-T007 inserts
  new rows of this type; the FK hardening is a separate audit task.

Direct entry into M14 is blocked until **all** are true:

- M10 is merged on `main` (`docs/milestones/m10/final-review.md` exists and reports PASS).
- Cloud Supabase is the active DB (M10 follow-up PR #44 merged on `main`),
  with M10's `submissions` / `experiment_runs` / `competitions` rows reachable.
  M14's new tables sit alongside them.
- The `kca kaggle push --watch` auto-poll feature (M10 follow-up) is on `main`.
  M14-T005 replaces its naive cadence with the smart-polling logic but reuses
  the same watcher entry point.
- Issues #51 #52 #53 #54 #55 have been triaged to `ai:ready` (each starts
  `ai:triage`; promotion requires explicit acceptance criteria sign-off).

### What's in scope

| Capability | Owned by | M14 touches |
|---|---|---|
| Goal-driven loop architecture + ADR | `docs/adr/0020-goal-driven-kaggle-loop.md` + `docs/architecture/goal-driven-kaggle-loop.md` | T000 |
| `goals` table + `competitions.max_*` columns + `experiment_runs.analysis.exploration_batch_id` | `supabase/migrations/0011_m14_goal_loop.sql` + `tools/kca/db.py` | T001 |
| `kca goal {init, show, update}` + `goal.md` workspace artefact | `tools/kca/goal.py` + new subcommand registration | T002 (issue #51) |
| `kca explore {init, run, rank}` + search-space YAML + local screening | `tools/kca/explore.py` + `src/worker/` integration | T003 (issue #52) |
| Per-competition concurrency enforcement in `cmd_push` | `tools/kca/kg.py` + `competitions.max_concurrent_pushes` | T004 (issue #53) |
| Smart polling (Fibonacci backoff while QUEUED, stable while RUNNING, batched status reads) | `tools/kca/kg.py::_watch_kernel_until_terminal` + `_watch_many` | T005 (issue #54) |
| Idea-sourcing reader (forum / public kernels / arxiv) → `next_candidates.yaml` | `tools/kca/research.py` extension + new `kca explore propose-next` | T006 |
| Stuck detector + human escalation via Approval Inbox | `src/worker/reviewer.py` + `decision_api` + UI surface | T007 (issue #55) |
| Live end-to-end on a fresh Kaggle competition | new fixtures + one approved push series | T008 |
| Regression tests + exit criteria + final review | `tests/test_m14_*.py` + `docs/milestones/m14/final-review.md` | T009 |

### What's NOT in scope

- **A new ML breakthrough.** M14 is a workflow milestone; the only modelling
  asks are "use the existing M10 baseline + alt-backbone as the seed search
  space." Improvements to the model itself (Mixup, RandAugment, larger
  backbones) are *outputs* of the loop, not deliverables of M14.
- **Production Supabase.** Cloud (Supabase pooler) only.
- **Kaggle datasets / model uploads.** Out of scope — kernel pushes only.
  M14's concurrency + polling logic generalises to `dataset_upload` later but
  that work is M15+.
- **Cross-account quota pooling.** Issue #21 is the multi-account variant.
  M14 ships the single-account primitive issue #21 will build on.
- **A new Kaggle competition register beyond `tpu-getting-started`.** T008 may
  pick a small open Getting Started competition to validate end-to-end, but
  M14 does not commit to maintaining a competition portfolio. That is M15+.
- **CTF / Devpost / eval-suite integration.** M11 / M12 / M13 own those
  surfaces; M14's goal/exploration/escalation primitives may be reused there
  but the wiring is deferred.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the cloud
Supabase pooler (`postgresql://postgres.<ref>:<pw>@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres`,
from `.vscode/.env`) needs `dangerouslyDisableSandbox=true`. T008's live
Kaggle push also needs sandbox bypass (network out to `kaggle.com`).

---

## M14 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M14-T000 | `arch:` Goal-driven loop architecture + ADR-0020 + Discovery / Debate Gate transcripts | Prompt 0 |
| M14-T001 | Migration 0011 (`goals` + `competitions.max_*` + `experiment_runs.analysis.exploration_batch_id`) + DB helpers | Prompt 1 |
| M14-T002 | `kca goal {init, show, update}` + `goal.md` schema (issue #51) | Prompt 2 |
| M14-T003 | `kca explore {init, run, rank}` + local-screening fan-out (issue #52) | Prompt 3 |
| M14-T004 | Per-competition concurrency enforcement in `cmd_push` + daily-budget gate (issue #53) | Prompt 4 |
| M14-T005 | Smart polling: Fibonacci backoff QUEUED, stable RUNNING, batched `kernels list` reads (issue #54) | Prompt 5 |
| M14-T006 | Idea-sourcing reader + `kca explore propose-next` (forum / public kernels / arxiv → candidate YAML) | Prompt 6 |
| M14-T007 | Stuck detector + human escalation surface (issue #55) | Prompt 7 |
| M14-T008 | Live end-to-end exercise on Kaggle: goal set, explore, push (≤ daily budget), poll, record LB, iterate or escalate | Prompt 8 |
| M14-T009 | Regression tests + exit criteria validation + `docs/milestones/m14/final-review.md` | Prompt 9 |

Each task's full scope, acceptance criteria, allowed / forbidden paths, and
closeout format will be written into the matching `docs/tasks/m14/M14-T00N-*.md`
spec during T000 (the architecture phase). Until then, the loop prompts below
are the authoritative scope.

---

## Loop Prompt 0 — M14-T000 Goal-driven loop architecture + ADR-0020 (arch:)

```
/goal Execute M14-T000 goal-driven loop architecture + ADR-0020 + Discovery / Debate Gate transcripts until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md (note §7 — Discovery / Debate Gate is MANDATORY for this `arch:` task)
Task spec: docs/tasks/m14/M14-T000-goal-loop-architecture.md  (to be written in this prompt)

Read also (background context):
- docs/milestones/README.md §M14
- docs/architecture/discovery-debate-gate.md
- .claude/agents/requirements-skeptic.md
- .claude/agents/legacy-archaeologist.md (skippable — greenfield; document the skip)
- .claude/agents/design-red-team.md
- docs/milestones/m10/final-review.md (M10 single-push baseline)
- PR #44 (M10 follow-up: cloud Supabase, kca kaggle score, kca kaggle push --watch)
- Issues #51 #52 #53 #54 #55 (per-bullet tracking)
- docs/adr/0006-approval-gates.md (existing gate model)
- docs/adr/0010-model-routing.md (route routing precedent)

Mission:
Write `docs/adr/0020-goal-driven-kaggle-loop.md` and the companion
`docs/architecture/goal-driven-kaggle-loop.md`. Decide:
  - `goal.md` schema (target_lb_rank vs target_lb_score; deadline; exit_strategy)
  - `goals` table shape + FK from `submissions` + `experiment_runs.analysis`
  - search-space spec format (YAML cross-product? jsonl?)
  - exploration-batch lifecycle (init → fan-out → screen → rank → promote)
  - smart-polling state machine (QUEUED/RUNNING/TERMINAL × cadence)
  - stuck-detector heuristic + escalation payload shape
  - re-use vs replace of existing reviewer / Approval Inbox surfaces
Run the Discovery / Debate Gate (skip `legacy-archaeologist` only with
an explicit greenfield note — M14 builds on existing primitives, no
legacy artefact). Attach all three transcripts under
`docs/evidence/m14/T000/discovery/`. Write the 10 task specs
`docs/tasks/m14/M14-T001-*.md` through `M14-T009-*.md` as the design output.
No code, no migration, no CLI changes in this Loop Prompt — design only.
```

---

## Loop Prompt 1 — M14-T001 Migration 0011 + DB helpers

```
/goal Execute M14-T001 migration 0011 (goals + competitions.max_* + experiment_runs.analysis.exploration_batch_id) + DB helpers until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T001-migration-and-helpers.md

Read also (background context):
- M14-T000 closeout (ADR-0020 + architecture doc)
- supabase/migrations/0010_m13_eval.sql (most recent migration on main, from M13-T001)
- tools/kca/db.py (existing helpers: ensure_competition, create_experiment_m2, update_submission)
- docs/architecture/goal-driven-kaggle-loop.md
- Issue #8 (competition-rules ingestion — parent issue this task absorbs)
- Issue #7 (submission-format awareness — #8's sub-task, also absorbed here)

Mission:
Write `supabase/migrations/0011_m14_goal_loop.sql` (next free number — M11/M12/M13 occupy 0008/0009/0010 on main) with:
  - `goals` table (id, competition_id FK, target_lb_score, target_lb_rank,
    deadline, exit_strategy, status, created_at, closed_at, closed_reason)
  - `competitions` columns: `max_daily_submissions`, `max_concurrent_pushes`,
    `rules_summary_url`, `last_rules_fetch_at`, `submission_format`
    (per #7: jsonb with `kind` ∈ `csv|notebook|kernel-output|zip` + format-specific keys),
    `accelerators_allowed` (text[]), `internet_allowed` (boolean), `deadline_at`
  - `experiment_runs.analysis` keys (no schema change — these are JSONB
    fields documented in ADR-0020): `exploration_batch_id`, `parent_run_id`,
    `queue_time_seconds`, `running_time_seconds`, `escalation_id`
  - `goals.id` FK on `submissions.goal_id` (nullable)
Add matching helpers in `tools/kca/db.py`: `create_goal`, `update_goal`,
`get_active_goal`, `count_active_pushes`, `count_today_submissions`,
`refresh_competition_rules` (calls `kaggle.api.competition_view` + parses the
public rules page best-effort, writes to the new columns).
Extend `tools/kca/competition.py::cmd_register` to populate the new columns
at register time (per #8) and add `kca competition refresh-rules --slug ...`
for on-demand refresh.
No `kca goal` / `kca explore` CLI surface yet; that is T002+. Migration must
apply cleanly against the cloud Supabase pooler.
```

---

## Loop Prompt 2 — M14-T002 `kca goal` CLI + `goal.md` schema (issue #51)

```
/goal Execute M14-T002 kca goal CLI + goal.md workspace artefact (issue #51) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T002-kca-goal-cli.md

Read also (background context):
- M14-T000 / M14-T001 closeouts
- Issue #51 (acceptance criteria — pin to the issue body)
- tools/kca/competition.py (existing register / info pattern)
- tools/kca/COMMANDS.md (subcommand documentation pattern)

Mission:
Implement `kca goal init --competition <slug> --target-lb-score <f> [--target-lb-rank <int>] [--deadline <yyyy-mm-dd>]`,
`kca goal show --competition <slug> [--json]`,
`kca goal update --competition <slug> [...] [--close --reason <text>]`.
Write a `goal.md` file under `experiments/<comp>/` capturing the same
fields in human-readable form. The DB `goals` row is authoritative;
goal.md is for humans + git history. Reviewer gate (kernel_push) now
surfaces `goal_remaining_delta` in the approval prompt.
```

---

## Loop Prompt 3 — M14-T003 `kca explore` + local screening (issue #52)

```
/goal Execute M14-T003 kca explore + local-screening fan-out (issue #52) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T003-kca-explore.md

Read also (background context):
- M14-T000 / M14-T001 / M14-T002 closeouts
- Issue #52 (acceptance criteria)
- experiments/tpu-getting-started/baseline-tl/baseline.py (the seed)
- scripts/m10_t002_local_train.py, scripts/m10_t005_local_train.py (local-train pattern)
- src/worker/worker.py (worker harness for fan-out)

Mission:
Implement `kca explore init --competition <slug> --search-space <yaml>` that
mechanically generates one `experiments/<comp>/<run-id>/` per cell (or random
sample) of the search-space cross-product, each with a baseline.py templated
from the seed.
Implement `kca explore run --batch <id> [--max-concurrent N]` that fans out
local screenings (process pool + GPU memory check) and writes
`holdout_accuracy`, `macro_f1`, `train_seconds` to experiment_runs.
Implement `kca explore rank --batch <id> [--json]` that lists candidates
sorted by holdout, marking which qualify (CV >= heuristic threshold relative
to goal).
No Kaggle push here.
```

---

## Loop Prompt 4 — M14-T004 Multi-push concurrency enforcement (issue #53)

```
/goal Execute M14-T004 multi-push concurrency + daily-budget enforcement (issue #53) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T004-multi-push-concurrency.md

Read also (background context):
- M14-T000 / M14-T001 closeouts
- Issue #53 (acceptance criteria)
- tools/kca/kg.py::cmd_push (M10 single-push path)
- tools/kca/kg.py::cmd_score (auto-watch loop entry)
- kaggle.api.competition_view (per-competition limits)
- Issue #21 (per-account-pool variant — out of scope here; M15+)
- Issue #62 (cmd_push missing KAGGLE_USERNAME/KAGGLE_KEY pre-check — bundled
  into this task since the pre-flight gating shape is what's being touched
  anyway; mirrors cmd_submit's existing check at tools/kca/kg.py:145-162)

Mission:
The new competition rules columns are already populated by T001 (per #8).
In `cmd_push`: add a `KAGGLE_USERNAME` / `KAGGLE_KEY` pre-check that
short-circuits with the same error envelope shape `cmd_submit` uses, BEFORE
the approval gate fires (per #62). Then count current active kernel runs
for this competition that KCA owns (latest version per slug, status !=
TERMINAL); refuse cleanly when the limit is reached; emit the active-runs
list in the JSON response.
In `cmd_push` and `cmd_submit`: count today's submissions for this comp;
refuse past `max_daily_submissions`; back off until the 24h rolling window
opens.
No real Kaggle push in this Loop Prompt — exercise the enforcement against
a fixture / fake competition row.
```

---

## Loop Prompt 5 — M14-T005 Smart polling: backoff + batched status (issue #54)

```
/goal Execute M14-T005 smart polling — Fibonacci backoff QUEUED, stable RUNNING, batched kernels list reads (issue #54) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T005-smart-polling.md

Read also (background context):
- M14-T000 / M14-T001 / M14-T004 closeouts
- Issue #54 (acceptance criteria)
- tools/kca/kg.py::_watch_kernel_until_terminal (M10 fixed-cadence baseline)
- M10-T004 closeout (status API 500 history; output API fallback discovery)

Mission:
Replace the fixed 60s cadence in `_watch_kernel_until_terminal` with a state
machine:
  - QUEUED  → Fibonacci ramp [60, 90, 150, 240, ..., cap = ⅓ × estimated_queue_time]
              (estimated_queue_time = median of last 5 same-accelerator pushes
               for this comp; default 15min if no history)
  - RUNNING → stable 300s cadence
  - TERMINAL → exit
State detection: parse `kaggle kernels status` when it returns 200; fall
back to `kaggle kernels output` size>0 for terminal; explicitly ignore
500/503 errors as non-terminal.
Add `_watch_many(kernel_refs)` that does ONE `kaggle kernels list -m
--page-size 100` per tick and parses per-slug — used when >= 2 slugs are
tracked. Record `experiment_runs.analysis.queue_time_seconds` and
`running_time_seconds` separately so the queue-time estimator has data.
```

---

## Loop Prompt 6 — M14-T006 Idea-sourcing reader + propose-next

```
/goal Execute M14-T006 idea-sourcing reader (Kaggle forum / public kernels / arxiv) + kca explore propose-next until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T006-idea-sourcing.md

Read also (background context):
- M14-T002 / M14-T003 closeouts
- tools/kca/research.py (existing research-brief skill output)
- .claude/skills/research-brief/ (cited-source, trust-labelled extraction)
- Kaggle forum API (kaggle.api.kernels_list / kernel comments — READ_ONLY)

Mission:
Implement `kca explore propose-next --competition <slug> [--budget-search-queries N]`
that reads the competition's top public kernels (`kaggle kernels list -c
<slug> --sort-by hotness`), forum threads (best-effort scrape under the
research-brief trust model), and recent papers (arxiv search on competition
keywords) — and writes `experiments/<comp>/next_candidates.yaml` proposing
3–5 new search-space cells the agent has not yet tried. The proposal must
cite sources (`source_url`, `trust_label`) and pass through the
research-brief untrusted-data filter (no source can inject instructions).
Human approval optional but recommended via a default `--dry-run` mode that
writes the YAML without scheduling a batch.
```

---

## Loop Prompt 7 — M14-T007 Stuck detector + human escalation (issue #55)

```
/goal Execute M14-T007 stuck detector + human escalation via Approval Inbox (issue #55) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T007-stuck-escalation.md

Read also (background context):
- M14-T000 / M14-T002 / M14-T006 closeouts
- Issue #55 (acceptance criteria)
- src/worker/reviewer.py (existing gate model)
- services/decision_api/app.py (Approval Inbox surface)
- ui/src/pages/ApprovalInbox.tsx
- docs/tasks/m9/M9-T003 / M10-T003 (the kaggle_submit / kernel_push escalation precedents)
- Issue #60 (`approved_by_user_id` FK on `human_decisions`) — T007 inserts
  new rows of this type; the FK hardening is tracked separately but the new
  rows here should be FK-ready (write the column if present, ignore otherwise).

Mission:
Implement the stuck detector — fires when N consecutive submissions show no
monotone LB improvement AND idea-sourcing returned 0 fresh candidates. N
defaults to 3, configurable via `goal.md::stuck_threshold`.
On stuck, write `docs/escalations/<comp>-<ts>.md` (goal vs current; table
of tried strategies; sources consulted; ruled-out hypotheses; concrete
questions). Insert a `human_decisions` row with
`decision_type=kaggle.exploration_stuck`. Surface in the Approval Inbox.
A human response (UI form or `kca decisions approve --notes "<direction>"`)
becomes the new exploration seed and the loop resumes; loop reads notes for
a structured option or free-text direction. Telemetry: count escalations +
time-to-resolution per competition.
```

---

## Loop Prompt 8 — M14-T008 Live end-to-end Kaggle exercise

```
/goal Execute M14-T008 live end-to-end goal-driven loop on a Kaggle competition until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T008-live-e2e.md

Override note: this Loop Prompt runs REAL Kaggle kernel pushes — typically
3 to 5 across one or two batches — under the per-competition concurrency
gate from T004. The total number of pushes is bounded by
`competitions.max_daily_submissions` (today's budget) and by `goal.md`'s
`max_total_pushes` (default 20 across the whole M14 exercise).

Pre-conditions:
  - T002–T007 closed.
  - `KAGGLE_USERNAME` / `KAGGLE_KEY` present.
  - A small open Getting Started competition picked (default:
    `tpu-getting-started` — re-using the M10 surface — with a goal of
    "top-30% LB rank or score >= 0.85", whichever is reached first).
  - The closing issue has `policy:approval-required` AND a human comment
    explicitly approving the multi-push series.

Mission:
1. `kca goal init` with the agreed goal.
2. `kca explore init` with a search-space (3–5 backbones × 2 image sizes ×
   2 epoch counts).
3. `kca explore run` local screening; rank.
4. `kca kaggle push` the top K under the concurrency gate (T004). All
   pushes are auto-watched (T005's smart-polling logic).
5. `kca kaggle score --update-db` per terminal kernel.
6. If LB < goal: `kca explore propose-next` (T006), iterate.
7. If stuck (T007 detector fires): write escalation, pause, await human
   decision, resume.
8. End when goal is reached OR `max_total_pushes` reached OR human says stop.
Closeout: record final LB, distance to goal, total pushes used, total
escalations, total queue/running time.
```

---

## Loop Prompt 9 — M14-T009 Regression tests + exit criteria + final review

```
/goal Execute M14-T009 regression tests + exit criteria validation + docs/milestones/m14/final-review.md until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m14/M14-T009-m14-exit-criteria.md

Read also (background context):
- all M14 closeouts (T000–T008)
- docs/milestones/m10/final-review.md (layout precedent)
- docs/milestones/m8_5/final-review.md (layout precedent)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill
- Issue #63 (gate PRs on eval score-delta — absorbed by this task per
  docs/milestones/m13/final-review.md M14+ follow-up 3)
- docs/adr/0019-eval-regression-suite.md (the M13 suite definitions this
  task adds CI gating on top of)
- runs/m13-eval/<ts>/report.json (the diffable artefact produced by
  `kca eval report`)

Mission:
Add `tests/test_m14_*.py` covering:
  - kca goal {init, show, update} happy + failure paths
  - kca explore init / run / rank against a fake search space (dry-run; no
    real training)
  - cmd_push concurrency refusal when limit reached (fixture-driven)
  - cmd_push credentials pre-check refusal (matches cmd_submit's envelope
    shape; per #62 + T004)
  - _watch_kernel_until_terminal state machine: QUEUED → RUNNING → TERMINAL
    cadence (mocked clock)
  - stuck detector triggers when 3 non-improving submissions land
  - escalation row + escalation doc written

Eval-suite CI gating (per #63):
  - Define per-suite `failure_threshold` in `docs/adr/0019-eval-regression-suite.md`
    (absolute for shape-checks, relative for metric deltas).
  - Add a GitHub Actions step `eval-delta-check` that runs `kca eval run`
    against the baselined snapshot and fails the PR if any suite regresses
    past its threshold. Reuses the existing M13 nightly job's runner.
  - Document the bypass: a `eval:waive-delta` PR label (human-only) skips
    the gate with a mandatory rationale comment, recorded in
    `agent_tool_audit`.

Run the milestone validation matrix, then `milestone-final-review` writes
`docs/milestones/m14/final-review.md` mirroring the M10 / M8.5 layout. Update
PROJECT_STATE / README / milestones / handoffs per the protocol §5 source
of truth rule. `worktree-milestone-pr` commits per-loop-prompt, pushes the
worktree branch, and opens the final M14 PR against `main`.
```

---

## GitHub issue / label workflow for M14

| Task | Issue | Labels at file time |
|---|---|---|
| M14-T000 | (new — `arch:`) | `type:feature ai:triage area:agent-sdk area:kaggle priority:P1` |
| M14-T001 | #8 (parent) + #7 (sub-task) | `type:feature ai:triage area:supabase area:agent-sdk priority:P1` |
| M14-T002 | #51 | `type:feature ai:triage area:kaggle area:agent-sdk priority:P1` |
| M14-T003 | #52 | `type:feature ai:triage area:worker area:kaggle priority:P1` |
| M14-T004 | #53 + #62 | `type:feature ai:triage area:kaggle priority:P1` |
| M14-T005 | #54 | `type:feature ai:triage area:kaggle priority:P1` |
| M14-T006 | (new — paired with #51/#52) | `type:feature ai:triage area:kaggle area:agent-sdk priority:P2` |
| M14-T007 | #55 | `type:feature ai:triage area:agent-sdk area:ui priority:P1` |
| M14-T008 | (new — `policy:approval-required`) | `type:feature ai:blocked policy:approval-required decision:needed area:kaggle priority:P0` |
| M14-T009 | #63 + (new test-gap issue) | `type:test-gap ai:triage area:testing area:release area:docs area:eval priority:P1` |

T008 is the only task that starts `ai:blocked` and requires a
`decision:confirmed` comment with an explicit "approved to run multi-push
series" record before triage may promote it to `ai:ready`.

---

## Approval gates (summary)

| Gate | When it fires | Where approval is recorded |
|---|---|---|
| `kernel_push` (per push) | Each Kaggle push in T008's series | reviewer gate writes `agent_reviews` + `human_decisions`; the M14 batch may carry a pre-approved budget so the gate fires once per batch, not per push (decision in T000) |
| `kaggle_submit` | If T008 uses code-competition `competition_submit_code` for an LB write | per-batch approval, same as above |
| `kaggle.exploration_stuck` (NEW) | T007 stuck detector fires | `human_decisions` row + Approval Inbox UI; resolution unblocks the loop |

The new `exploration_stuck` decision_type is the visible new approval surface
this milestone introduces.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m14_*.py`.
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui ...` — clean (CI authoritative if pnpm not on local PATH).
- `kca goal show --competition <slug> --json` works against the live cloud
  Supabase row.
- `kca explore rank --batch <id> --json` lists the local-screening cohort.
- `kca kaggle push` refuses cleanly when concurrency limit is reached
  (asserted via fixture in T004 tests).
- `_watch_kernel_until_terminal` records `queue_time_seconds` +
  `running_time_seconds` separately on a synthetic kernel (T005 tests).
- T008's closing issue links the approval comment, the `goals.id` row, all
  `submissions.id` rows from the batch, and the final LB delta.
- `docs/milestones/m14/final-review.md` exists and follows the M10 / M8.5 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- The Discovery / Debate Gate (T000) flags a load-bearing requirement the
  ADR does not address. Fix the ADR; do not skip.
- A real Kaggle kernel push in T008 returns an error from Kaggle (rate
  limit, bad notebook metadata, rules violation). Fix path is local;
  re-request approval; do NOT silently retry.
- Concurrency / daily-budget enforcement permits a push that violates
  Kaggle's actual limit (caught by Kaggle 429 / 400). Halt T004 and fix
  the enforcement before any further push.
- Stuck-detector fires repeatedly without escalation being acknowledged
  (≥ 24h with no human response). Halt T008 and ask for direction
  out-of-band.
- The DSN, credentials, or `.env*` are accidentally printed in any log,
  audit row, PR, or escalation doc. Stop and rotate the credential.

If M14 needs a new architectural decision (e.g. cross-account quota
pooling — issue #21 — or a new artefact storage shape for the
exploration cohort), **pause and ask** — those are M15+ decisions, not
M14 expansion. Open an ADR draft and stop the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN comes from .vscode/.env auto-load (cloud Supabase pooler); no need
# to export SUPABASE_DB_URL manually.

# Kaggle credentials — already in .vscode/.env.harry (single-user dev) or
# in ~/.kaggle/kaggle.json. Verify with kca kaggle list --json before T008.

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M14-T000 from docs/milestones/m14/loop-prompts.md."
# ...repeat for M14-T001 … M14-T009.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M14 — write docs/milestones/m14/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls and the live Kaggle CLI calls in T008 need
`dangerouslyDisableSandbox=true` (cloud Supabase pooler + `kaggle.com`).

---

## Human decisions needed before starting M14

These should be confirmed on the canonical M14 proposal issue (TBD —
opened during T000) before any implementation begins:

1. **Goal type per competition.** `target_lb_rank` (percentile) vs
   `target_lb_score` (absolute) vs both. T002's `goal init` prompt
   should accept either; T000 ADR decides the primary.
2. **Per-batch push approval vs per-push.** Asking for human approval
   before each individual push in T008 would be operationally heavy;
   pre-approving a batch budget (e.g. "up to 5 pushes today targeting
   this goal") is more practical. T000 ADR decides.
3. **Idea-sourcing trust model.** T006 reads competition forum posts /
   public kernels / arxiv. Should the agent be allowed to silently
   incorporate ideas, or must each fresh candidate be human-approved
   before scheduling? Default proposed: human-approved (write-only the
   `next_candidates.yaml`, agent does not auto-schedule).
4. **Stuck threshold default.** N = 3 consecutive non-improving
   submissions before escalation. Configurable per `goal.md`. T000 ADR
   confirms the default.
5. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed by precedent.

A canonical M14 proposal issue (paralleling #12 for M10) should be
filed at the start of T000, link to issues #51 #52 #53 #54 #55, and
collect human confirmation for the five points above before T000
finishes.
