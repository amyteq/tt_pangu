# M9 — Loop Prompts

_Live end-to-end Kaggle regression test on
[Spaceship Titanic](https://www.kaggle.com/competitions/spaceship-titanic/overview)._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M8.5 exit confirmed (CI green + GitHub Issues/PR/labels interface in place; see `docs/milestones/m8_5/final-review.md`)._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md` (sequencing, no real Kaggle/Anthropic outside designated approval paths, DB DSN + sandbox bypass, worktree commit/push/PR at milestone end, secret denylist)._

---

## M9 at a glance

M9 is the **first end-to-end live Kaggle regression** for this platform. It
exercises the M3 worker, M5 research path, M6 reviewer + telemetry, the M7
permission policy, and the M8 decision_api + UI shell against a real Kaggle
competition. The competition is Spaceship Titanic — binary classification,
public leaderboard, no cash prize, safe for repeated dry-run iteration and a
single real submission under an explicit human-approval gate.

M9 is **not** a leaderboard-chasing milestone. The acceptance criterion is
that the loop *runs end-to-end correctly under the approval gates*, not that
the LB score is high. The CV thresholds in `docs/milestones/README.md` §M9 are
sanity guards, not targets.

Direct entry into M9 is blocked until **all** are true:

- M8.5-T001 (CI repair) is merged on main.
- M8.5-T002 (engineering practice + GitHub interface) is merged on main and
  `.github/labels.yml` has been synced to `origin` (33 labels visible via
  `gh label list`).
- `scripts/sync_labels.py --dry-run` reports `0 update`.
- `docs/milestones/m8_5/final-review.md` exists and reports PASS.

### What's in scope

| Capability | Owned by | M9 touches |
|---|---|---|
| Kaggle credentials handling | `env.example`, `.env`, `KAGGLE_USERNAME`/`KAGGLE_KEY` | T000 — verifies env without printing secrets; gates submit on presence |
| Competition register + workspace | `tools/kca/competition.py` (`register`, `clone`, `list`, `info`) | T000 / T001 |
| Data download + checksum | `tools/kca/kg.py::cmd_download`, `cmd_verify` (sha256 manifest already implemented in M5) | T001 |
| Worker loop (research → baseline → CV → submission file) | `src/worker/` + `tools/kca/run.py` + skills | T002 |
| Reviewer gate before submit | `src/worker/reviewer.py` + `services/decision_api/` + UI Approval Inbox | T003 |
| Real Kaggle submit (under approval) | `tools/kca/kg.py::cmd_submit` + `kaggle competitions submit` | T004 — single real call |
| Second experiment (HGB / feature engineering) | same worker, second run | T005 |
| Regression assertions | `tests/test_m9_e2e.py` + `runs` table | T006 / T007 |
| GitHub issue / label workflow | `.github/labels.yml`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `policy:approval-required` | every task — work order issue per task |
| Final review | `milestone-final-review` skill + `worktree-milestone-pr` skill | T008 |

### What's NOT in scope

- Running Kaggle submit / kernel push / dataset upload / model upload outside
  T004's single approved call.
- Changing production Supabase.
- Implementing M9 follow-ups from M8 (multi-user auth, artifact preview via
  signed URLs, live-DB CI on fork PRs, OTEL collector wiring). Those are
  separate milestones; if M9 surfaces blockers for them, file follow-up
  issues — don't expand scope.
- Adding new CLI subcommands. M9 uses the existing `kca` surface
  (`competition`, `kaggle`, `run`, `research`, `review`, `decisions`,
  `skill`) without inventing new ones.
- Runtime submission-format detection. KCA's `kca kaggle submit` is
  format-agnostic: it passes `--file` straight to `kaggle competitions
  submit`, and Kaggle validates server-side. **M9 assumes
  `submission.csv` because Spaceship Titanic is a CSV competition.** Other
  competition shapes (code-competition notebooks → `kca kaggle push`;
  `submission.zip`; JSON; etc.) need different paths that KCA does not
  yet auto-select. Tracked as a separate `area:kaggle` / `type:feature`
  follow-up — see M9-T002's "Submission-format note" for context.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the local
`supabase-db` container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`)
needs `dangerouslyDisableSandbox=true`.

---

## M9 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M9-T000 | Kaggle credentials + competition registration (no real submit, no secret print) | Prompt 0 |
| M9-T001 | Download Spaceship Titanic data, verify sha256 manifest, commit `manifest.json` | Prompt 1 |
| M9-T002 | Worker loop produces baseline LR `submission.csv` + CV score via existing skills | Prompt 2 |
| M9-T003 | Reviewer gate fires; submit request lands in decision_api / Approval Inbox | Prompt 3 |
| M9-T004 | **One** real Kaggle submission under explicit human approval; record LB score | Prompt 4 |
| M9-T005 | Second experiment (HGB + feature engineering) — local-only, no submit | Prompt 5 |
| M9-T006 | Regression assertions: CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB recorded | Prompt 6 |
| M9-T007 | `tests/test_m9_e2e.py` (dry-run path, no credentials) | Prompt 7 |
| M9-T008 | M9 exit criteria validation + `docs/milestones/m9/final-review.md` | Prompt 8 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m9/M9-T00N-*.md` spec.

---

## Loop Prompt 0 — M9-T000 Kaggle credentials + competition registration

```
/goal Execute M9-T000 Kaggle credentials + competition registration until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T000-kaggle-credentials.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md §M9
- docs/milestones/m8/handoff.md
- docs/engineering-practice.md
- env.example
- tools/kca/competition.py
- tools/kca/kg.py (kaggle list / fetch — READ_ONLY only at this stage)

Mission (full version in task spec):
Confirm Kaggle credentials are loadable from .env WITHOUT reading or
printing them; verify the agent can list/fetch competition metadata in
READ_ONLY mode; register Spaceship Titanic in the local control plane.
Do NOT call `kaggle competitions submit`, `kaggle kernels push`,
`kaggle datasets create`, or any other SUBMISSION / REMOTE_WRITE op.
```

---

## Loop Prompt 1 — M9-T001 Download data + verify manifest

```
/goal Execute M9-T001 Spaceship Titanic data download + manifest verification until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T001-data-download.md

Read also (background context):
- M9-T000 closeout
- tools/kca/kg.py::cmd_download, ::cmd_verify
- supabase/migrations/0004_m4_competition_repo.sql (data table)
- data/ (any prior workspace layout)

Mission (full version in task spec):
Download Spaceship Titanic data via `kca kaggle download --competition
spaceship-titanic` (LOCAL_WRITE only), verify sha256 manifest, and commit
ONLY the small `manifest.json` (not the raw data). Data lives under
data/spaceship-titanic/ and is gitignored.
```

---

## Loop Prompt 2 — M9-T002 Worker baseline loop → submission.csv

```
/goal Execute M9-T002 Spaceship Titanic baseline LR loop (research → baseline → CV → submission.csv) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T002-baseline-loop.md

Read also (background context):
- M9-T000, M9-T001 closeouts
- src/worker/worker.py, src/worker/budget.py, src/worker/tools.py
- tools/kca/run.py
- tools/kca/skill.py
- .kca/skills/kaggle-experiment-loop/ (skill body)
- supabase/migrations/0005_m5_research_citations.sql

Mission (full version in task spec):
Drive the AgentWorker through one baseline experiment for Spaceship
Titanic. Output: a valid `submission.csv` and a CV score recorded in
runs. No real Kaggle submission. No kernel push.
```

---

## Loop Prompt 3 — M9-T003 Reviewer gate + approval inbox

```
/goal Execute M9-T003 reviewer gate firing before kaggle_submit until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T003-reviewer-approval-gate.md

Read also (background context):
- M9-T002 closeout
- src/worker/reviewer.py
- services/decision_api/app.py
- tools/kca/decisions.py
- supabase/migrations/0006_m6_reviews_spans.sql
- ui/src/pages/ApprovalInbox.tsx, DecisionGate.tsx

Mission (full version in task spec):
The worker reaches `kaggle_submit` and the reviewer-gate writes an
agent_reviews row + a human_decisions row. The decision_api exposes the
pending decision to the UI Approval Inbox. Approve via
`kca decisions approve` (NOT via real Kaggle submit). The next step
(real submit) is gated to T004 and requires explicit human-typed
approval recorded on the closing issue.
```

---

## Loop Prompt 4 — M9-T004 ONE real Kaggle submission under approval

```
/goal Execute M9-T004 one approved live Kaggle submission for Spaceship Titanic until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T004-real-submission.md

Override note: this is the ONLY Loop Prompt in the milestone that runs
a real `kaggle competitions submit`. Pre-conditions before running:
  - M9-T003 closeout shows a `decision:confirmed` human decision on
    the closing issue.
  - `KAGGLE_USERNAME` and `KAGGLE_KEY` are present in .env.
  - `submission.csv` from M9-T002 still validates (T002 acceptance).
  - The closing issue has `policy:approval-required` AND a human comment
    explicitly approving the submit (this milestone's only such record).

Read also (background context):
- M9-T002, M9-T003 closeouts
- tools/kca/kg.py::cmd_submit
- .claude/settings.json (`Bash(kaggle competitions submit*)` is on ask)
- supabase/migrations/0001_init.sql (submissions table)

Mission (full version in task spec):
Run exactly ONE real `kca kaggle submit --competition spaceship-titanic
--file <submission.csv> --message <msg>`. Record the public LB score in
the runs / submissions table. Do NOT iterate beyond this one submission
inside this Loop Prompt.
```

---

## Loop Prompt 5 — M9-T005 Second experiment (HGB / feature engineering)

```
/goal Execute M9-T005 Spaceship Titanic second experiment (HGB + feature engineering) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T005-second-experiment.md

Read also (background context):
- M9-T002 (baseline)
- M9-T004 (LB recorded)
- tools/kca/run.py, src/worker/

Mission (full version in task spec):
Run a second local experiment using HistGradientBoostingClassifier and
basic feature engineering, with the same CV harness as M9-T002. Local
only — no second real submission. The improvement is measured by CV
delta, not LB.
```

---

## Loop Prompt 6 — M9-T006 Regression assertions

```
/goal Execute M9-T006 regression assertions for Spaceship Titanic CV + LB until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T006-regression-assertions.md

Read also (background context):
- M9-T002, M9-T004, M9-T005 closeouts
- existing tests/test_m*_smoke.py patterns

Mission (full version in task spec):
Assert: LR CV ≥ 0.78; HGB CV ≥ 0.80; HGB CV > LR CV; LB score recorded
in the runs / submissions table for the M9-T004 submission. Failures
here block M9 exit but do NOT trigger another real Kaggle submission.
```

---

## Loop Prompt 7 — M9-T007 E2E smoke (dry-run, no credentials)

```
/goal Execute M9-T007 tests/test_m9_e2e.py dry-run path until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T007-e2e-dryrun-test.md

Read also (background context):
- tests/test_m8_smoke.py, tests/test_m8_worker_wiring.py (pattern)
- src/worker/worker.py (dry_run path)
- tools/kca/kg.py (cmd_submit gating without KAGGLE_USERNAME/KEY)

Mission (full version in task spec):
Add `tests/test_m9_e2e.py` that runs research → baseline → CV →
submission.csv → reviewer-gate → decision approve, all in dry-run mode,
WITHOUT real Kaggle credentials. CI must pick this up under the
existing `no-db` and `live-db` jobs.
```

---

## Loop Prompt 8 — M9-T008 Exit criteria + final review

```
/goal Execute M9-T008 M9 exit criteria validation + final review until docs/milestones/m9/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9/M9-T008-m9-exit-criteria.md

Read also (background context):
- all M9 closeouts (T000–T007)
- docs/milestones/m8/final-review.md (layout precedent)
- docs/milestones/m8_5/final-review.md (layout precedent)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix, then call milestone-final-review
to write docs/milestones/m9/final-review.md mirroring the M8 / M8.5 layout. After
final review is written, milestone-closeout commits per-loop-prompt
(or one squash), pushes the worktree branch, and opens the final M9 PR
against main.

Override note: this is the only Loop Prompt in M9 that calls
worktree-milestone-pr.
```

---

## GitHub issue / label workflow for M9

Each M9 task is filed as a GitHub issue using the `feature-work.yml` form,
labelled per task type:

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M9-T000 | `type:feature`, `ai:triage`, `area:kaggle`, `area:config`, `area:security` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M9-T001 | `type:feature`, `ai:triage`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M9-T002 | `type:feature`, `ai:triage`, `area:worker`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M9-T003 | `type:feature`, `ai:triage`, `area:worker`, `area:supabase`, `area:ui` | `ai:ready` | `ai:implementing` → close |
| M9-T004 | `type:feature`, `ai:blocked`, `policy:approval-required`, `decision:needed`, `area:kaggle`, `priority:P0` | `decision:confirmed` + `ai:ready` only after human comment "approved to submit" | `ai:implementing` → close |
| M9-T005 | `type:feature`, `ai:triage`, `area:worker`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M9-T006 | `type:test-gap`, `ai:triage`, `area:testing` | `ai:ready` | `ai:implementing` → close |
| M9-T007 | `type:test-gap`, `ai:triage`, `area:testing`, `area:ci` | `ai:ready` | `ai:implementing` → close |
| M9-T008 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T007 closed | `ai:implementing` → close |

T004 is the only task that starts `ai:blocked` and requires a
`decision:confirmed` comment with an explicit "approved to submit" record
before triage may promote it to `ai:ready`. This is enforced by the
`github-issue-triage` agent rules in `.claude/skills/github-issue-triage/`.

The PR for each task uses `.github/pull_request_template.md`. The
"Remote side effects" section is load-bearing: T004's PR is the ONLY
M9 PR that may check the "Live Kaggle call" box, and must link the
approval comment from the closing issue.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `kaggle_submit` | Worker stages a submission file and calls into `tools/kca/kg.py::cmd_submit` | `human_decisions` row + comment on the closing GitHub issue | Project owner / reviewer named on the issue |
| `kernel_push` | Not used in M9 | n/a (out of scope) | n/a |
| `dataset_upload` | Not used in M9 | n/a (out of scope) | n/a |
| `model_upload` | Not used in M9 | n/a (out of scope) | n/a |

The Kaggle approval flow inside M9 is:

```
worker stages submission.csv
  → reviewer-gate writes agent_reviews row + agent_job_events
  → decision_api surfaces pending decision (POST /decisions queued)
  → UI Approval Inbox renders pending decision
  → human approves via UI (POST /decisions/<id>/approve) OR
    `kca decisions approve --id <id>`
  → human comments "approved to submit" on the closing issue
  → triage agent promotes issue to `decision:confirmed` + `ai:ready`
  → M9-T004 Loop Prompt runs ONE `kca kaggle submit`
  → LB score recorded; submissions row written
  → PR opens with the approval comment linked
```

A second real Kaggle submission inside M9 is **out of scope**. If a
follow-up experiment in M9-T005 turns out to need its own LB score,
file it as a new M10+ issue and gate it the same way.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m9_e2e.py` (M9-T007) passing in dry-run.
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui install --frozen-lockfile`, `pnpm -C ui lint`,
  `pnpm -C ui typecheck`, `pnpm -C ui build`, `pnpm -C ui run test --run`
  — all clean.
- `kca run list` shows the M9 run with a recorded CV score and
  (after T004) a recorded LB score.
- `manifest.json` for the Spaceship Titanic data is committed; raw data
  files are not.
- M9-T004 closing issue links to the approval comment AND the
  resulting `submissions` row id.
- `docs/milestones/m9/final-review.md` exists and follows the M8 / M8.5 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- A real Kaggle submit returns an error from Kaggle (rate limit, bad CSV,
  rules violation). The fix path is local: regenerate the submission and
  re-request approval; do NOT silently retry.
- The reviewer gate (M9-T003) fails to fire when it should, or fires
  when it shouldn't.
- Any `policy:approval-required` issue advances without the corresponding
  `decision:confirmed` label and comment.
- Any test in the validation suite regresses from green to red.
- The DSN, credentials, or `.env*` are accidentally printed in any log,
  audit row, or PR. Stop and rotate the credential immediately.
- CV scores diverge from the M9-T006 thresholds in a way that suggests a
  leakage bug (e.g. CV near 1.0). Investigate before submitting.

If M9 needs a new architectural decision (e.g. multi-user auth, a new
queue, or a new artifact storage shape), **pause and ask** — those are
M10+ decisions, not M9 expansion. Open an ADR draft in `docs/adr/` and
stop the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# Kaggle credentials — populate .env from env.example and Kaggle profile,
# THEN verify with `kca kaggle list --json` (READ_ONLY). Never `cat .env`.

# Per-prompt invocation:
claude "Use the milestone-loop-runner agent to execute M9-T000 from docs/milestones/m9/loop-prompts.md."
# ...repeat for M9-T001 … M9-T008.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M9 — write docs/milestones/m9/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca` subcommand
that reaches Supabase) need `dangerouslyDisableSandbox=true`. The real
Kaggle CLI call inside M9-T004 also needs sandbox bypass (network out
to `kaggle.com`).

---

## Human decisions needed before starting M9

These decisions block M9-T000 / M9-T004 specifically. Each should be
recorded as a `type:decision` issue with `decision:confirmed` BEFORE the
corresponding task is promoted to `ai:ready`:

1. **Submission policy for Spaceship Titanic.** Confirm: one real
   submission is acceptable; no kernel push; no dataset upload; second
   experiment stays local.
2. **Kaggle credential source.** `.env` (local-only) vs Kaggle profile
   `~/.kaggle/kaggle.json`. The hook + sandbox already block direct
   reads of `kaggle.json`; the recommended source is the project `.env`
   loaded via `python-dotenv`.
3. **Public LB acceptance threshold (if any).** The CV thresholds in
   §M9 are sanity checks; the LB score is recorded but no LB floor is
   asserted. Confirm.
4. **Failure handling.** If T004 returns an error, do we re-submit (no:
   single-submission policy) or fail the milestone and open a follow-up
   issue (yes — preferred)?
