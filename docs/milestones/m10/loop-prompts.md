# M10 — Loop Prompts

_Live end-to-end Kaggle regression test on
[Petals to the Metal — Flower Classification on TPU](https://www.kaggle.com/competitions/tpu-getting-started)._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M9 exit confirmed (live LB recorded, dry-run e2e green; see `docs/milestones/m9/final-review.md`)._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md` (sequencing, no real Kaggle/Anthropic outside designated approval paths, DB DSN + sandbox bypass, **per-milestone worktree by default**, secret denylist)._

---

## M10 at a glance

M10 is the **second end-to-end live Kaggle regression** for this platform, and
the first to exercise the **notebook-submission / kernel-push** path.
M9 validated the CSV-submission path (`kca kaggle submit` →
`kaggle competitions submit`) on Spaceship Titanic. M10 validates the
notebook-submission path (`kca kaggle push` → `kaggle kernels push` →
kernel run → public LB) on Petals to the Metal — Flower Classification on TPU
(`tpu-getting-started`).

Petals to the Metal is "Getting Started" tier: multi-class image
classification over 104 flower species, public leaderboard, no cash prize,
safe for repeated dry-run iteration and a single real kernel push under
explicit human approval. TPU is optional — Kaggle accepts GPU-backed
notebooks for this competition too — so the baseline can run locally
and only the kernel runner needs Kaggle's hardware.

M10 is **not** a leaderboard-chasing milestone. The acceptance criterion is
that the kernel-push loop *runs end-to-end correctly under the approval
gates*, not that the LB score is high. The CV / holdout thresholds in
`docs/milestones/README.md` §M10 are sanity guards, not targets.

Direct entry into M10 is blocked until **all** are true:

- M9 is merged on main (`docs/milestones/m9/final-review.md` exists and reports PASS).
- Issue #11 (dotenv-leak / Kaggle leaderboard pollution) is merged on main —
  hard pre-req for **M10-T007** so the new dry-run e2e test cannot leak
  into the `tpu-getting-started` leaderboard the same way M9 leaked into
  Spaceship Titanic. M10-T000 through M10-T006 may proceed in parallel
  with #11 work; only T007 is gated on it.
- The local Supabase container is running and the M9 DB rows (M9-T002 /
  M9-T004 / M9-T005) are reachable (M10-T006 references the M9 baseline
  for cross-milestone regression sanity).

### What's in scope

| Capability | Owned by | M10 touches |
|---|---|---|
| Kaggle credentials handling | `env.example`, `.env`, `KAGGLE_USERNAME`/`KAGGLE_KEY` | T000 — verifies env without printing secrets; gates push on presence |
| Competition register + workspace | `tools/kca/competition.py` (`register`, `clone`, `list`, `info`) | T000 / T001 |
| Data discovery for non-CSV competitions | `tools/kca/kg.py` (existing `cmd_download` / `cmd_verify` if extended) + a new manifest shape | T001 — notebook competitions read TFRecord-style data from Kaggle-hosted GCS at kernel runtime; the local manifest records `kaggle competitions files` output, not file checksums |
| Notebook authoring + percent-format round-trip | `kg-nb` skill (`tools/kca/notebook.py` or equivalent) | T002 / T007 |
| Worker loop (research → baseline → local CV → notebook artifact) | `src/worker/` + `tools/kca/run.py` + skills | T002 |
| Reviewer gate before kernel push | `src/worker/reviewer.py` + `services/decision_api/` + UI Approval Inbox (under `target_op="kernel_push"`) | T003 |
| Real Kaggle kernel push (under approval) | `tools/kca/kg.py::cmd_push` + `kaggle kernels push` + kernel-run polling | T004 — single real call |
| Second experiment (alt backbone / augmentation) | same worker, second run | T005 |
| Regression assertions | `tests/test_m10_e2e.py` + `runs` table + `submissions` table | T006 / T007 |
| GitHub issue / label workflow | `.github/labels.yml`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `policy:approval-required` | every task — work order issue per task; issue #12 is the canonical M10 proposal |
| Final review | `milestone-final-review` skill + `worktree-milestone-pr` skill | T008 |

### What's NOT in scope

- Running Kaggle submit / kernel push / dataset upload / model upload outside
  T004's single approved kernel-push call.
- Changing production Supabase.
- Implementing M9 follow-ups A, C, D, E (tracked as issues #14, #15, #16, #17).
  They run in parallel; if M10 surfaces blockers, file follow-up issues —
  don't expand scope. Issue #11 is the only hard pre-req (see entry gates).
- Adding new CLI subcommands beyond what `cmd_push` already provides. M10
  uses the existing `kca` surface (`competition`, `kaggle`, `run`,
  `research`, `review`, `decisions`, `skill`) without inventing new ones.
  Internal helpers (e.g. kernel-run polling) may be added under
  `tools/kca/kg.py` as private functions if `cmd_push` doesn't already
  cover them, but no new top-level subcommand surface.
- Auto-selecting between CSV-submit and kernel-push paths based on
  competition metadata. That is the scope of issues #7 / #8 (submission-
  format awareness / competition-rules ingestion) and is a co-traveller
  for M10, not a deliverable.
- TPU runtime tuning. The baseline notebook may declare a TPU strategy
  for Kaggle's kernel runner, but local training is GPU/CPU; M10 does
  not own TPU-specific performance work.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the local
`supabase-db` container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`)
needs `dangerouslyDisableSandbox=true`. The real Kaggle CLI call inside
M10-T004 also needs sandbox bypass (network out to `kaggle.com`).

---

## M10 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M10-T000 | Kaggle credentials + competition registration for `tpu-getting-started` (no real push, no secret print) | Prompt 0 |
| M10-T001 | Discover Petals to the Metal data via `kaggle competitions files`; record a `manifest.json` for the non-CSV shape | Prompt 1 |
| M10-T002 | Worker loop produces baseline image-classification notebook + local CV / holdout score via the existing skills + `kg-nb` round-trip | Prompt 2 |
| M10-T003 | Reviewer gate fires for `target_op="kernel_push"`; push request lands in decision_api / Approval Inbox | Prompt 3 |
| M10-T004 | **One** real `kca kaggle push` under explicit human approval; wait for the kernel run; record public LB score | Prompt 4 |
| M10-T005 | Second experiment (alt backbone or augmentation) — local-only, no second push | Prompt 5 |
| M10-T006 | Regression assertions: local CV ≥ TBD, LB recorded, kernel-run linked to a `runs` / `submissions` row | Prompt 6 |
| M10-T007 | `tests/test_m10_e2e.py` (dry-run path, no credentials). Hard pre-req: issue #11 merged. | Prompt 7 |
| M10-T008 | M10 exit criteria validation + `docs/milestones/m10/final-review.md` | Prompt 8 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m10/M10-T00N-*.md` spec.

---

## Loop Prompt 0 — M10-T000 Kaggle credentials + competition registration

```
/goal Execute M10-T000 Kaggle credentials + competition registration for tpu-getting-started until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T000-kaggle-credentials.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md §M10
- docs/milestones/m9/handoff.md
- docs/engineering-practice.md
- env.example
- tools/kca/competition.py
- tools/kca/kg.py (kaggle list / fetch — READ_ONLY only at this stage)
- docs/milestones/m9/final-review.md (M9-T000 deviation: AC #1 satisfied via
  kaggle.api.config_values rather than literal python-dotenv check)

Mission (full version in task spec):
Confirm Kaggle credentials are loadable WITHOUT reading or printing them;
verify the agent can list/fetch competition metadata in READ_ONLY mode;
register `tpu-getting-started` (Petals to the Metal) in the local control
plane. Do NOT call `kaggle competitions submit`, `kaggle kernels push`,
`kaggle datasets create`, or any other SUBMISSION / REMOTE_WRITE op.
```

---

## Loop Prompt 1 — M10-T001 Data discovery + non-CSV manifest

```
/goal Execute M10-T001 Petals to the Metal data discovery + manifest until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T001-data-discovery-manifest.md

Read also (background context):
- M10-T000 closeout
- tools/kca/kg.py::cmd_download, ::cmd_verify (existing CSV manifest path)
- docs/tasks/m9/M9-T001-data-download.md (the CSV-shape precedent)
- supabase/migrations/0004_m4_competition_repo.sql (competitions.data_path / artifacts table)

Mission (full version in task spec):
Discover Petals to the Metal's data via `kaggle competitions files
-c tpu-getting-started` (READ_ONLY) and record a `manifest.json` that
documents the dataset shape the kernel will read at runtime. Kaggle
serves the TFRecord data from a GCS path; the local workspace does NOT
download the raw TFRecords (~5+ GB). Commit ONLY the small
`manifest.json`. Raw data under data/tpu-getting-started/ stays
gitignored even if a developer chooses to download a slice for local
inspection.
```

---

## Loop Prompt 2 — M10-T002 Baseline notebook → local CV / holdout

```
/goal Execute M10-T002 Petals to the Metal baseline notebook (transfer learning → local CV/holdout → notebook artifact) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T002-baseline-notebook.md

Read also (background context):
- M10-T000, M10-T001 closeouts
- src/worker/worker.py, src/worker/budget.py, src/worker/tools.py
- tools/kca/run.py
- tools/kca/skill.py
- .kca/skills/kaggle-experiment-loop/ (skill body) — note that during M9
  this skill was unreachable from the loader; .claude/skills/kaggle-
  experiment-loop/ was used instead. Same path applies here unless
  M9-T002's "skill-loader" follow-up has landed.
- The kg-nb skill (notebook ↔ percent-format Python round-trip)
- docs/tasks/m9/M9-T002-baseline-loop.md (the CSV-baseline precedent)

Mission (full version in task spec):
Drive the AgentWorker through one baseline image-classification
experiment for Petals to the Metal. Use a small pretrained ImageNet
backbone (e.g. MobileNetV2 / EfficientNetB0) plus standard
preprocessing. Output: a runnable notebook at runs/tpu-getting-started/
baseline-tl/baseline.ipynb (or the percent-format .py the kg-nb skill
round-trips from), a local CV/holdout score recorded in
experiment_runs, and a kernel-runnable kernel-metadata.json suitable
for `kca kaggle push` in M10-T004. No real Kaggle push. No real
submission.
```

---

## Loop Prompt 3 — M10-T003 Reviewer gate for kernel_push + approval inbox

```
/goal Execute M10-T003 reviewer gate firing before kernel_push until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md

Read also (background context):
- M10-T002 closeout
- src/worker/reviewer.py
- services/decision_api/app.py
- tools/kca/decisions.py
- supabase/migrations/0006_m6_reviews_spans.sql
- ui/src/pages/ApprovalInbox.tsx, DecisionGate.tsx
- docs/tasks/m9/M9-T003-reviewer-approval-gate.md (the kaggle_submit precedent)
- Issue #15 (decision_api: no GET /decisions endpoint — work around as
  M9-T003 did; do NOT block M10-T003 on closing #15).
- Issue #16 (reviewer_decision event_type wording drift — use whatever
  literals the worker actually emits today; do NOT block on closing #16).

Mission (full version in task spec):
The worker reaches `kernel_push` and the reviewer-gate writes an
agent_reviews row + a human_decisions row (target_op="kernel_push").
The decision_api exposes the pending decision to the UI Approval
Inbox. Approve via `kca decisions approve` (NOT via real Kaggle
kernel push). The next step (real push) is gated to T004 and requires
explicit human-typed approval recorded on the closing issue.
```

---

## Loop Prompt 4 — M10-T004 ONE real Kaggle kernel push under approval

```
/goal Execute M10-T004 one approved live Kaggle kernel push for Petals to the Metal until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T004-real-kernel-push.md

Override note: this is the ONLY Loop Prompt in the milestone that runs
a real `kaggle kernels push` (and waits for the resulting kernel run).
Pre-conditions before running:
  - M10-T003 closeout shows a `decision:confirmed` human decision on
    the closing issue.
  - `KAGGLE_USERNAME` and `KAGGLE_KEY` are present in .env (or in
    `~/.kaggle/kaggle.json`; either is sufficient — see M9-T000
    deviation in `docs/milestones/m9/final-review.md`).
  - The baseline notebook from M10-T002 still passes local CV/holdout
    sanity (T002 acceptance).
  - The closing issue has `policy:approval-required` AND a human comment
    explicitly approving the push (this milestone's only such record).

Read also (background context):
- M10-T002, M10-T003 closeouts
- tools/kca/kg.py::cmd_push
- .claude/settings.json (`Bash(kaggle kernels push*)` is on ask)
- supabase/migrations/0001_init.sql (submissions table)
- docs/tasks/m9/M9-T004-real-submission.md (the CSV-submit precedent)

Mission (full version in task spec):
Run exactly ONE real `kca kaggle push --competition tpu-getting-started
--notebook <path> --message <msg>`. Wait for the kernel run to complete
(poll `kaggle kernels status` until non-running, capped at the spec's
timeout). Record the public LB score in the runs / submissions table.
Do NOT iterate beyond this one push inside this Loop Prompt.
```

---

## Loop Prompt 5 — M10-T005 Second experiment (alt backbone / augmentation)

```
/goal Execute M10-T005 Petals to the Metal second experiment (alt backbone or augmentation) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T005-second-experiment.md

Read also (background context):
- M10-T002 (baseline)
- M10-T004 (LB recorded)
- tools/kca/run.py, src/worker/
- docs/tasks/m9/M9-T005-second-experiment.md (the HGB+FE precedent)

Mission (full version in task spec):
Run a second local experiment using a different backbone (e.g. swap
MobileNetV2 → EfficientNetB0, or add Mixup / RandAugment to the
baseline pipeline). Same CV/holdout harness as M10-T002. Local only —
no second real kernel push. The improvement is measured by local
CV/holdout delta, not LB.
```

---

## Loop Prompt 6 — M10-T006 Regression assertions

```
/goal Execute M10-T006 regression assertions for Petals to the Metal CV + LB until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T006-regression-assertions.md

Read also (background context):
- M10-T002, M10-T004, M10-T005 closeouts
- existing tests/test_m9_smoke.py pattern
- M9 baseline rows in experiment_runs / submissions (for cross-
  milestone sanity: M9's LB row is still queryable)

Mission (full version in task spec):
Assert: baseline local CV ≥ TBD; alt-backbone local CV ≥ baseline; LB
score recorded in the runs / submissions table for the M10-T004 kernel
push; kernel-run id captured. Failures here block M10 exit but do NOT
trigger another real Kaggle kernel push.
```

---

## Loop Prompt 7 — M10-T007 E2E smoke (dry-run, no credentials)

```
/goal Execute M10-T007 tests/test_m10_e2e.py dry-run path until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T007-e2e-dryrun-test.md

Hard pre-req: issue #11 (dotenv-leak / Kaggle leaderboard pollution)
must be merged on main BEFORE this Loop Prompt runs. Verify with
`gh issue view 11 --json state` returns `"CLOSED"` (issue closes on
PR merge per the engineering-practice routing rules). If #11 is not
yet closed, halt here and ask for confirmation; do not write a test
that would leak the same way M9 leaked.

Read also (background context):
- tests/test_m9_e2e.py (the closest pattern)
- tests/test_m9_smoke.py (DB-gated assertion pattern)
- src/worker/worker.py (dry_run path)
- tools/kca/kg.py::cmd_push (gating without KAGGLE_USERNAME/KEY)
- Issue #11 (the leak that this test must NOT repeat)

Mission (full version in task spec):
Add `tests/test_m10_e2e.py` that runs research → baseline notebook →
local CV/holdout → kg-nb round-trip → reviewer-gate (kernel_push) →
decision approve → kca kaggle push credentials-gate refusal, all in
dry-run mode, WITHOUT real Kaggle credentials and WITHOUT any real
Kaggle network call. CI must pick this up under the existing `no-db`
and `live-db` jobs. Audit-grep the test run: assert 0 lines that begin
with `kaggle kernels push` reached the kaggle CLI.
```

---

## Loop Prompt 8 — M10-T008 Exit criteria + final review

```
/goal Execute M10-T008 M10 exit criteria validation + final review until docs/milestones/m10/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m10/M10-T008-m10-exit-criteria.md

Read also (background context):
- all M10 closeouts (T000–T007)
- docs/milestones/m9/final-review.md (layout precedent)
- docs/milestones/m8_5/final-review.md (layout precedent)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix, then call milestone-final-review
to write docs/milestones/m10/final-review.md mirroring the M9 / M8.5 layout. After
final review is written, milestone-closeout commits per-loop-prompt
(or one squash), pushes the worktree branch, and opens the final M10 PR
against main.

Override note: this is the only Loop Prompt in M10 that calls
worktree-milestone-pr.
```

---

## GitHub issue / label workflow for M10

Each M10 task is filed as a GitHub issue using the `feature-work.yml` form,
labelled per task type. Issue #12 is the canonical M10 proposal /
decision-confirmation record; individual task issues link back to it.

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M10-T000 | `type:feature`, `ai:triage`, `area:kaggle`, `area:config`, `area:security` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M10-T001 | `type:feature`, `ai:triage`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M10-T002 | `type:feature`, `ai:triage`, `area:worker`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M10-T003 | `type:feature`, `ai:triage`, `area:worker`, `area:supabase`, `area:ui` | `ai:ready` | `ai:implementing` → close |
| M10-T004 | `type:feature`, `ai:blocked`, `policy:approval-required`, `decision:needed`, `area:kaggle`, `priority:P0` | `decision:confirmed` + `ai:ready` only after human comment "approved to push" | `ai:implementing` → close |
| M10-T005 | `type:feature`, `ai:triage`, `area:worker`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M10-T006 | `type:test-gap`, `ai:triage`, `area:testing` | `ai:ready` | `ai:implementing` → close |
| M10-T007 | `type:test-gap`, `ai:triage`, `area:testing`, `area:ci` | `ai:ready` only after issue #11 is closed | `ai:implementing` → close |
| M10-T008 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T007 closed | `ai:implementing` → close |

T004 is the only task that starts `ai:blocked` and requires a
`decision:confirmed` comment with an explicit "approved to push" record
before triage may promote it to `ai:ready`. This is enforced by the
`github-issue-triage` agent rules in `.claude/skills/github-issue-triage/`.

T007 is the only task gated on closing a separate issue (#11). The
triage agent should refuse to promote T007 to `ai:ready` while
`gh issue view 11 --json state` returns `"OPEN"`.

The PR for each task uses `.github/pull_request_template.md`. The
"Remote side effects" section is load-bearing: T004's PR is the ONLY
M10 PR that may check the "Live Kaggle call" box, and must link the
approval comment from the closing issue.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `kernel_push` | Worker stages a notebook + kernel-metadata.json and calls into `tools/kca/kg.py::cmd_push` | `human_decisions` row + comment on the closing GitHub issue | Project owner / reviewer named on the issue |
| `kaggle_submit` | Not used in M10 (would be a second-submission path; out of scope) | n/a | n/a |
| `dataset_upload` | Not used in M10 | n/a | n/a |
| `model_upload` | Not used in M10 | n/a | n/a |

The Kaggle approval flow inside M10 is:

```
worker stages notebook + kernel-metadata.json
  → reviewer-gate writes agent_reviews row + agent_job_events
    (target_op="kernel_push")
  → decision_api surfaces pending decision (POST /decisions queued; UI
    reads via supabase-js until issue #15 lands GET /decisions)
  → UI Approval Inbox renders pending decision
  → human approves via UI (POST /decisions/<id>/approve) OR
    `kca decisions approve --id <id>`
  → human comments "approved to push" on the closing issue
  → triage agent promotes issue to `decision:confirmed` + `ai:ready`
  → M10-T004 Loop Prompt runs ONE `kca kaggle push`
  → poll kaggle kernels status until non-running
  → LB score recorded; submissions row written with kernel-run linkage
  → PR opens with the approval comment linked
```

A second real Kaggle push inside M10 is **out of scope**. If a
follow-up experiment in M10-T005 turns out to need its own LB score,
file it as a new M11+ issue and gate it the same way.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m10_e2e.py` (M10-T007) passing in
  dry-run.
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui install --frozen-lockfile`, `pnpm -C ui lint`,
  `pnpm -C ui typecheck`, `pnpm -C ui build`, `pnpm -C ui run test --run`
  — all clean. (May SKIP in the agent's local sandbox if pnpm is not on
  PATH, same posture as M9 — CI is authoritative.)
- `kca run list` shows the M10 baseline + alt-backbone runs with
  recorded local CV/holdout scores and (after T004) a recorded LB
  score for the baseline.
- `manifest.json` for Petals to the Metal is committed; raw TFRecord
  data is not (`data/tpu-getting-started/` stays gitignored).
- M10-T004 closing issue links to the approval comment AND the
  resulting `submissions` row id AND the kernel-run id from Kaggle.
- `docs/milestones/m10/final-review.md` exists and follows the M9 / M8.5 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- A real Kaggle kernel push returns an error from Kaggle (rate limit,
  bad notebook metadata, rules violation). The fix path is local:
  regenerate the notebook + kernel metadata and re-request approval;
  do NOT silently retry.
- The reviewer gate (M10-T003) fails to fire when it should, or fires
  when it shouldn't.
- Any `policy:approval-required` issue advances without the corresponding
  `decision:confirmed` label and comment.
- Any test in the validation suite regresses from green to red.
- The DSN, credentials, or `.env*` are accidentally printed in any log,
  audit row, or PR. Stop and rotate the credential immediately.
- Local CV / holdout scores diverge from the M10-T006 thresholds in a
  way that suggests a leakage bug (e.g. holdout near 1.0). Investigate
  before pushing.
- Issue #11 is reopened mid-milestone with evidence that the leak
  re-emerged. Halt T007 work until #11 is green again.

If M10 needs a new architectural decision (e.g. submission-format
auto-selection, a new artifact-storage shape for notebook payloads, a
TPU-specific resource model), **pause and ask** — those are M11+ /
issue #7 / issue #8 decisions, not M10 expansion. Open an ADR draft in
`docs/adr/` and stop the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# Kaggle credentials — populate .env from env.example and Kaggle profile,
# THEN verify with `kca kaggle list --json` (READ_ONLY). Never `cat .env`.

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M10-T000 from docs/milestones/m10/loop-prompts.md."
# ...repeat for M10-T001 … M10-T008.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M10 — write docs/milestones/m10/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca` subcommand
that reaches Supabase) need `dangerouslyDisableSandbox=true`. The real
Kaggle CLI call inside M10-T004 also needs sandbox bypass (network out
to `kaggle.com`).

---

## Human decisions needed before starting M10

These were confirmed on issue #12 on 2026-05-24 and are recorded here for
the milestone-loop-runner's read list:

1. **Submission policy for Petals to the Metal.** Confirmed: one real
   kernel push is acceptable; no second push; no kernel-version bump;
   second experiment stays local.
2. **Kaggle credential source.** `.env` (local-only) vs Kaggle profile
   `~/.kaggle/kaggle.json`. The hook + sandbox already block direct
   reads of `kaggle.json`; either path works because the kaggle CLI
   resolves both. The M9-T000 deviation (`kaggle.api.config_values` as
   equivalent evidence for the literal python-dotenv check) carries
   forward to M10-T000.
3. **Public LB acceptance threshold (if any).** The local CV / holdout
   thresholds in §M10 are sanity checks; the LB score is recorded but
   no LB floor is asserted. Confirmed.
4. **Failure handling.** If T004 returns an error, do we re-push (no:
   single-push policy) or fail the milestone and open a follow-up
   issue (yes — preferred). Confirmed.
5. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed.

Issue #12 is the canonical record of these decisions and is
`decision:confirmed` + `ai:ready`.
