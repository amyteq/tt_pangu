# M12 — Loop Prompts

_Live end-to-end hackathon regression on a Devpost-style event picked
in M12-T000._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M9 exit confirmed (live LB recorded; see `docs/milestones/m9/final-review.md`).
M10 may be in flight in parallel; M12 does NOT depend on M10 completing._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md`
(sequencing, secret denylist, sandbox/DB DSN, **per-milestone worktree by default**)._

---

## M12 at a glance

M12 is the **third live external-submission regression** for this platform,
and the first to exercise a **non-Kaggle hackathon-submission path**.

- M9 validated the **CSV-submission** path (`kca kaggle submit` →
  `kaggle competitions submit`) on Spaceship Titanic.
- M10 validates the **notebook / kernel-push** path
  (`kca kaggle push` → `kaggle kernels push`) on Petals to the Metal.
- M12 validates the **hackathon-submission** path on a Devpost-style
  event picked in M12-T000.

The product goal stated in `docs/milestones/README.md` §M12 is to **generalize
the competition-policy layer beyond Kaggle and CTF**. M12 owns that
generalization end-to-end:

- New `competition_type` enum on `competitions` (default `kaggle`;
  M11 will reuse the same enum for `ctf` values).
- Minimal `teams` + `team_memberships` tables so the hackathon flow
  can scope ideas + submissions by team without a full role / invite
  surface.
- New `tools/kca/devpost.py` adapter (READ_ONLY in T003; real submit
  gated behind the `devpost_submit` reviewer gate in T007).
- New `hackathon-experiment-loop` skill + `hackathon-runner`
  permission profile, mirroring `kaggle-experiment-loop` /
  `competition-runner.yaml`.
- Two new UI pages (deadline / phase view; submission checklist).
- One real Devpost submission, under explicit human approval, in T007.

M12 is **not** a hackathon-winning milestone. The acceptance criterion is
that the hackathon-submission loop *runs end-to-end correctly under the
approval gates*, not that the submission is competitive.

### Discovery / Debate Gate

M12-T001 is **`arch:`-tagged** and MUST run the Discovery / Debate Gate
per `docs/milestone-loop-protocol.md` §7:

- `legacy-archaeologist` reads the Kaggle-specific surfaces being
  generalized (`competitions` schema in `supabase/migrations/0004_*.sql`
  + ADR-0006 + `tools/kca/competition.py` + `.kca/permissions/*.yaml` +
  the kaggle-experiment-loop skill).
- `requirements-skeptic` asks ≥5 questions across ≥3 categories
  (hidden constraints, personas/teams, side effects, deadline /
  rate-limit semantics, rollback).
- `design-red-team` produces ≥3 alternative designs (e.g. "fold
  hackathon into existing `competitions` table" vs "new
  `hackathon_competitions` table" vs "denormalised `competition_policy`
  jsonb"), names ≥1 dropped capability with file:line evidence, and
  scores them on the four cost axes.

Output deliverable: **ADR-0018** defining the `competition_type` enum
shape, the policy resolver, and the team-scoped operation rules.
Evidence: `docs/evidence/m12/t001/discovery/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`.

### Entry gates

Direct entry into M12 is blocked until **all** are true:

- M9 is merged on main (`docs/milestones/m9/final-review.md` exists and reports PASS).
- The closing GitHub issue for M12 carries `decision:confirmed` +
  `ai:ready` AND records the four user decisions from the M12 plan
  conversation (shape = full regression; M11 reuses schema; minimal
  teams; two new UI pages; full real submit under approval).
- The local Supabase container is running and Migration 0007 (M8 audit
  table) is applied (T002 builds on the post-M8 schema).

T000 (survey) may run before the issue is `decision:confirmed`; T001 and
later are blocked on the human pick from T000 being recorded.

### What's in scope

| Capability | Owned by | M12 touches |
|---|---|---|
| Hackathon survey + target pick | new `docs/evidence/m12/t000-candidates.md` | T000 |
| Competition-policy generalization | new ADR-0018 + refactor of `JobPolicy` / `permission_policy.py` | T001 / T002 |
| Schema for type / teams / deadline | `supabase/migrations/0009_m12_competition_type_teams.sql` | T002 |
| Devpost adapter (READ_ONLY) | new `tools/kca/devpost.py`; new `devpost` subcommands in `tools/kca/kca.py` | T003 |
| Hackathon skill + permissions | new `.kca/skills/hackathon-experiment-loop/SKILL.md` + new `.kca/permissions/hackathon-runner.yaml` + new `submission_checklist` tool | T004 |
| UI deadline + checklist pages | new `ui/src/pages/HackathonDeadline.tsx` + `ui/src/pages/SubmissionChecklist.tsx`; routes; vitest + Playwright | T005 |
| Local end-to-end worker run | `src/worker/` + `tools/kca/run.py` + the new skill; `runs/<slug>/<run_id>/submission_pack/` | T006 |
| Reviewer gate before Devpost submit | `src/worker/reviewer.py` + `services/decision_api/` + UI Approval Inbox (`target_op="devpost_submit"`) | T007 |
| Real Devpost submit (under approval) | `tools/kca/devpost.py::cmd_submit` (new in T007 only) | T007 — single real call |
| Regression assertions | `tests/test_m12_e2e.py` + `tests/test_m12_smoke.py` | T008 |
| GitHub issue / label workflow | `.github/labels.yml`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `policy:approval-required` | every task — issue per task; the closing issue is the canonical M12 record |
| Final review | `milestone-final-review` skill + `worktree-milestone-pr` skill | T009 |

### What's NOT in scope

- Running real Devpost submit / draft / upload outside T007's single
  approved call.
- Other hackathon platforms (HackerEarth, MLH, Devfolio). M12
  generalizes the policy layer so they can plug in, but does not
  implement them.
- CTF wiring against `competition_type='ctf'`. The enum value ships in
  T002 so M11 can plug in without a second migration, but no CTF code
  paths are added in M12.
- Full team-invite / role-based permission flow. M12 ships read-only
  team membership only (the agent / human can be a single team's sole
  member for the regression).
- Auto-generated demo video / readme from agent run logs.
- Multi-submission flows. The reviewer gate fires once; one real
  external write per milestone.
- Renaming any of the existing Kaggle-specific surfaces. The
  generalization is additive — `kaggle_submit` / `kernel_push` keep
  their names; `devpost_submit` is new.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the local
`supabase-db` container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`)
needs `dangerouslyDisableSandbox=true`. The real Devpost call inside
M12-T007 also needs sandbox bypass (network out to `devpost.com`).

---

## M12 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M12-T000 | Survey 2–3 candidate Devpost / hackathon events; human picks target slug (READ_ONLY; no DB writes) | Prompt 0 |
| M12-T001 | `arch:` Discovery / Debate Gate on competition-policy generalization; produce ADR-0018 | Prompt 1 |
| M12-T002 | Migration 0009 — `competition_type` enum, `teams`, `team_memberships`, `deadline`, `submission_format`; policy resolver refactor | Prompt 2 |
| M12-T003 | `tools/kca/devpost.py` adapter + `kca devpost register/fetch/info` (READ_ONLY only) | Prompt 3 |
| M12-T004 | `hackathon-experiment-loop` skill + `hackathon-runner.yaml` permission profile + `submission_checklist` tool | Prompt 4 |
| M12-T005 | UI: `HackathonDeadline.tsx` + `SubmissionChecklist.tsx` + routes + vitest + Playwright smoke | Prompt 5 |
| M12-T006 | Worker runs hackathon flow end-to-end locally; produces `runs/<slug>/<run_id>/submission_pack/` | Prompt 6 |
| M12-T007 | Reviewer gate for `devpost_submit` + human approval + ONE real Devpost submit + record `submissions` row | Prompt 7 |
| M12-T008 | `tests/test_m12_e2e.py` (dry-run, no creds) + `tests/test_m12_smoke.py` (DB-gated) | Prompt 8 |
| M12-T009 | M12 exit criteria + `docs/milestones/m12/final-review.md` + closeout | Prompt 9 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m12/M12-T00N-*.md` spec.

---

## Loop Prompt 0 — M12-T000 Hackathon survey + target pick

```
/goal Execute M12-T000 hackathon candidate survey + human pick for the M12 regression until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T000-survey-and-pick-target.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md §M12
- docs/milestones/m9/handoff.md
- docs/engineering-practice.md
- docs/architecture/discovery-debate-gate.md (T001 will use this; T000 only stages the human pick)
- env.example
- tools/kca/research_fetch.py (template for the READ_ONLY HTTP path; do NOT add devpost code yet)

Mission (full version in task spec):
Survey current Devpost (or Devpost-equivalent) hackathon events and
produce docs/evidence/m12/t000-candidates.md listing 2–3 candidates
with deadline, scope, prize policy, submission format, and a "why this
is safe for an AI-assisted regression" line. Do NOT register anything
in the DB; do NOT write tools/kca/devpost.py; do NOT call any submit /
upload / write op. After the file is written, post a single comment on
the closing GitHub issue with the candidate list; human picks via reply.
Close T000 by recording the picked slug in the issue body.
```

---

## Loop Prompt 1 — M12-T001 Discovery / Debate Gate on competition-policy generalization

```
/goal Execute M12-T001 Discovery / Debate Gate on competition-policy generalization until ADR-0018 is written and all three discovery acceptance lines pass, or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md (§7 Discovery / Debate Gate is mandatory for this task).
Task spec: docs/tasks/m12/M12-T001-discovery-debate-gate.md

Tag: arch:

Read also (background context):
- M12-T000 closeout (target slug picked)
- docs/architecture/discovery-debate-gate.md
- docs/adr/0006-configurable-approval-gates.md
- docs/adr/0009-competition-repo-strategy.md
- docs/adr/0015-memory-promotion-model.md (recent ADR shape)
- supabase/migrations/0004_m4_competition_repo.sql (competitions / experiments / submissions today)
- tools/kca/competition.py (existing register/clone/list/info)
- .kca/permissions/default.yaml, .kca/permissions/competition-runner.yaml
- .kca/skills/kaggle-experiment-loop/SKILL.md

Mission (full version in task spec):
Invoke (in this exact order) legacy-archaeologist, requirements-skeptic,
design-red-team subagents from .claude/agents/. Attach their reports
to docs/evidence/m12/t001/discovery/. Verify each agent's canonical
acceptance line byte-for-byte against the report. Then synthesise the
findings into docs/adr/0018-generalized-competition-type.md: the
`competition_type` enum (kaggle / devpost / hackathon_devpost / ctf /
generic — CTF-friendly values required so M11 can reuse), the policy
resolver shape (route on type, fall back to default), and the
team-scoped operation rules (which gates can a non-owner team member
trigger). Backwards compatibility: existing rows default to 'kaggle'.
```

---

## Loop Prompt 2 — M12-T002 Schema migration + policy resolver refactor

```
/goal Execute M12-T002 migration 0009 (competition_type / teams / deadline) + policy resolver refactor until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T002-schema-and-policy.md

Read also (background context):
- M12-T001 closeout (ADR-0018)
- supabase/migrations/0004_m4_competition_repo.sql, 0006_m6_reviews_spans.sql, 0007_m8_agent_tool_audit.sql (migration shape)
- src/worker/_types.py::JobPolicy
- tools/kca/agent/permission_policy.py
- src/worker/tools.py (gate resolution path)
- tests/test_m4_smoke.py, tests/test_m7_smoke.py (DB-gated patterns)

Mission (full version in task spec):
Author supabase/migrations/0009_m12_competition_type_teams.sql:
  - CREATE TYPE competition_type_enum AS ENUM ('kaggle','devpost',
    'hackathon_devpost','ctf','generic');
  - ALTER TABLE competitions ADD COLUMN competition_type
    competition_type_enum NOT NULL DEFAULT 'kaggle';
  - ALTER TABLE competitions ADD COLUMN deadline timestamptz NULL;
  - ALTER TABLE competitions ADD COLUMN submission_format jsonb NULL;
  - CREATE TABLE teams (...);
  - CREATE TABLE team_memberships (... UNIQUE(team_id, user_id));
Refactor `JobPolicy` and `permission_policy.py` so the gate resolver
routes on competition.competition_type. Existing Kaggle rows resolve
identically (regression). Add db helpers for team CRUD (read + insert
only; no delete in M12). Apply the migration locally; commit the .sql.
```

---

## Loop Prompt 3 — M12-T003 Devpost adapter (READ_ONLY)

```
/goal Execute M12-T003 Devpost adapter + READ_ONLY register/fetch/info subcommands until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T003-devpost-adapter.md

Read also (background context):
- M12-T002 closeout (schema)
- tools/kca/research_fetch.py (lightweight HTTP + readability + optional Playwright pattern)
- tools/kca/competition.py (register / fetch / info shape on Kaggle side)
- tools/kca/kca.py (subcommand registration)
- docs/adr/0018-generalized-competition-type.md (T001 output)

Mission (full version in task spec):
Add tools/kca/devpost.py with:
  - cmd_register(slug, name): inserts a competitions row with
    competition_type='devpost' (or 'hackathon_devpost' if T001 picked
    that value), captures deadline + submission_format from the
    fetched Devpost page.
  - cmd_fetch(slug): READ_ONLY HTTP fetch of the public Devpost
    challenge page; extract title, deadline, prize policy, submission
    format requirements. Playwright fallback is allowed but defaults
    to off (same opt-in pattern as research_fetch.py).
  - cmd_info(slug): prints the local row.
NO cmd_submit / cmd_draft / cmd_upload in this task. The submit path
lives in T007 only.
Wire into tools/kca/kca.py as `kca devpost {register,fetch,info}`.
```

---

## Loop Prompt 4 — M12-T004 Hackathon skill + permission profile

```
/goal Execute M12-T004 hackathon-experiment-loop skill + hackathon-runner permission profile + submission_checklist tool until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T004-hackathon-skill.md

Read also (background context):
- M12-T002, M12-T003 closeouts
- .kca/skills/kaggle-experiment-loop/SKILL.md (skill body precedent)
- .kca/permissions/default.yaml, competition-runner.yaml (profile shape)
- tools/kca/agent/tool_executor.py + src/worker/tools.py (tool registry shape)
- docs/architecture/kca-cli-architecture.md (four-layer model)

Mission (full version in task spec):
Create .kca/skills/hackathon-experiment-loop/SKILL.md mirroring the
kaggle-experiment-loop skill but driving the hackathon flow:
research → idea → prototype → submission pack. Create
.kca/permissions/hackathon-runner.yaml with devpost_submit=ask,
demo_upload=ask, team_invite=deny, plus inheritance from default.yaml.
Add a new tool `submission_checklist` (input: competition_id, run_id;
output: structured checklist + file refs based on
competitions.submission_format jsonb). Register the tool in the tools.yaml
or equivalent registry. No DB schema changes (T002 already shipped them).
```

---

## Loop Prompt 5 — M12-T005 UI deadline + submission checklist pages

```
/goal Execute M12-T005 ui/src/pages HackathonDeadline + SubmissionChecklist pages + routes + tests until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T005-ui-pages.md

Read also (background context):
- M12-T002 closeout (schema: competitions.deadline, submission_format, teams)
- ui/src/pages/ApprovalInbox.tsx (reuse for devpost_submit gate)
- ui/src/pages/DecisionGate.tsx, ui/src/pages/Dashboard.tsx
- ui/src/pages/Research.tsx (reuse for idea / discussion read)
- ui/src/lib/supabase.ts (typed read client)
- ui/playwright.config.ts + existing playwright smoke tests
- docs/adr/0014-ui-stack.md

Mission (full version in task spec):
Add two new pages and routes:
  - HackathonDeadline.tsx — countdown + phase indicator + team
    roster (read-only). Reads competitions.deadline +
    team_memberships.
  - SubmissionChecklist.tsx — templated checklist driven by
    competitions.submission_format jsonb; per-item status (todo /
    done / blocked). No mutation in M12; status is read-only,
    inferred from submission_pack file presence.
Wire routes. Add one vitest test per page (smoke: renders without
crashing + correct read shape) + one playwright smoke per page.
Existing ApprovalInbox handles the devpost_submit gate — do NOT add a
new approval page.
```

---

## Loop Prompt 6 — M12-T006 Local end-to-end hackathon flow

```
/goal Execute M12-T006 hackathon-experiment-loop end-to-end local run for the picked hackathon until submission pack assembles or stop after 100 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T006-end-to-end-local.md

Read also (background context):
- M12-T002, M12-T003, M12-T004, M12-T005 closeouts
- src/worker/worker.py, src/worker/budget.py
- tools/kca/run.py (kg-run skill backend)
- docs/tasks/m9/M9-T002-baseline-loop.md (CSV-baseline precedent)
- docs/tasks/m10/M10-T002-baseline-notebook.md (notebook-flow precedent)

Mission (full version in task spec):
Drive AgentWorker through hackathon-experiment-loop for the picked
hackathon. Produce runs/<slug>/<run_id>/submission_pack/ containing:
  - README.md (problem + idea + how-to-run)
  - demo-plan.md (what the demo will show)
  - source/ (link or copy of the prototype code path)
  - submission-checklist.json (output of the new submission_checklist
    tool)
NO external write. Local CV-analog metric: "checklist completion %"
recorded in experiment_runs.metric_name='checklist_completion'. Stop
short of the devpost_submit gate (that is T007).
```

---

## Loop Prompt 7 — M12-T007 ONE real Devpost submit under approval

```
/goal Execute M12-T007 one approved live Devpost submission for the picked hackathon until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T007-real-submit.md

Override note: this is the ONLY Loop Prompt in M12 that runs a real
Devpost submit. Pre-conditions before running:
  - M12-T006 closeout shows a complete submission_pack at
    runs/<slug>/<run_id>/submission_pack/.
  - The closing issue has `policy:approval-required` AND a human comment
    explicitly approving the submission (this milestone's only such
    record).
  - DEVPOST credentials (or a stored session cookie / API token per
    whichever path T003 picked) are present in .env; the closing
    issue records which auth shape was used. Never print the
    credential.

Read also (background context):
- M12-T003, M12-T006 closeouts
- src/worker/reviewer.py
- services/decision_api/app.py
- tools/kca/decisions.py
- supabase/migrations/0006_m6_reviews_spans.sql (agent_reviews table)
- docs/tasks/m9/M9-T004-real-submission.md (Kaggle submit precedent)
- docs/tasks/m10/M10-T004-real-kernel-push.md (kernel push precedent)

Mission (full version in task spec):
Worker reaches devpost_submit. Reviewer-gate writes agent_reviews +
human_decisions rows (target_op="devpost_submit"). decision_api
surfaces the pending decision to the UI Approval Inbox. Human approves
via `kca decisions approve --id <id>`. Add tools/kca/devpost.py::cmd_submit
(new in this task ONLY). Run exactly ONE real submission. Record the
result in submissions (platform='devpost', external_submission_id,
submission_url). Capture the Devpost submission URL in the closeout.
Do NOT iterate beyond this one submission inside this Loop Prompt.
```

---

## Loop Prompt 8 — M12-T008 E2E + smoke tests

```
/goal Execute M12-T008 tests/test_m12_e2e.py + tests/test_m12_smoke.py until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T008-regression-tests.md

Read also (background context):
- tests/test_m9_e2e.py (dry-run pattern, no creds)
- tests/test_m9_smoke.py (DB-gated pattern)
- tests/test_m10_e2e.py (if present; latest dry-run pattern)
- src/worker/worker.py (dry_run path)
- tools/kca/devpost.py (T003 + T007 surface)
- services/decision_api/app.py (approval round-trip)

Mission (full version in task spec):
Add tests/test_m12_e2e.py (dry-run, no creds):
  - submission_pack templater idempotency
  - submission_checklist tool: deterministic output for a fixed
    submission_format jsonb
  - devpost_submit refusal without DEVPOST_* env vars present
  - decision_api approval round-trip for target_op="devpost_submit"
  - audit-grep: 0 lines from the run reach the real devpost HTTP
    endpoint (the test must NOT hit devpost.com)
Add tests/test_m12_smoke.py (DB-gated, runs only when SUPABASE_DB_URL
is set):
  - competitions row for the picked hackathon has
    competition_type='devpost' (or 'hackathon_devpost')
  - teams + team_memberships rows present
  - experiment_runs row recorded with metric_name='checklist_completion'
  - submissions row recorded with platform='devpost' and a non-empty
    external_submission_id
  - agent_reviews + human_decisions rows recorded for
    target_op="devpost_submit"
CI must pick up both files under the existing no-db + live-db jobs.
```

---

## Loop Prompt 9 — M12-T009 Exit criteria + final review

```
/goal Execute M12-T009 M12 exit criteria validation + final review until docs/milestones/m12/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m12/M12-T009-final-review.md

Read also (background context):
- all M12 closeouts (T000–T008)
- docs/milestones/m9/final-review.md, docs/milestones/m10/final-review.md (if present),
  docs/milestones/m9_4/final-review.md (layout precedents)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix; call milestone-final-review to
write docs/milestones/m12/final-review.md mirroring the M9 / M9.4 layout
(validation matrix, PASS / SKIP / FAIL, exit-criteria roll-up). Update
PROJECT_STATE.md (current milestone = M13), README.md, docs/milestones/README.md
(mark M12 done with shipped summary), docs/milestones/m12/handoff.md
(per-milestone handoff template). After final review is written,
worktree-milestone-pr commits per-Loop-Prompt (one commit per task),
pushes the worktree branch, and opens the final M12 PR against main.

Override note: this is the only Loop Prompt in M12 that calls
worktree-milestone-pr.
```

---

## GitHub issue / label workflow for M12

Each M12 task is filed as a GitHub issue using the `feature-work.yml` form,
labelled per task type. The closing issue for M12 is the canonical
proposal / decision-confirmation record; individual task issues link
back to it.

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M12-T000 | `type:feature`, `ai:triage`, `area:research`, `area:docs` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M12-T001 | `type:arch`, `ai:triage`, `area:supabase`, `area:worker`, `area:policy`, `priority:P0` | `ai:ready` (after T000 picks slug) | `ai:implementing` → close |
| M12-T002 | `type:feature`, `ai:triage`, `area:supabase`, `area:worker`, `area:policy` | `ai:ready` (after ADR-0018 merged) | `ai:implementing` → close |
| M12-T003 | `type:feature`, `ai:triage`, `area:tools` | `ai:ready` | `ai:implementing` → close |
| M12-T004 | `type:feature`, `ai:triage`, `area:skill`, `area:policy` | `ai:ready` | `ai:implementing` → close |
| M12-T005 | `type:feature`, `ai:triage`, `area:ui` | `ai:ready` | `ai:implementing` → close |
| M12-T006 | `type:feature`, `ai:triage`, `area:worker`, `area:tools` | `ai:ready` | `ai:implementing` → close |
| M12-T007 | `type:feature`, `ai:blocked`, `policy:approval-required`, `decision:needed`, `area:tools`, `priority:P0` | `decision:confirmed` + `ai:ready` only after human comment "approved to submit" | `ai:implementing` → close |
| M12-T008 | `type:test-gap`, `ai:triage`, `area:testing`, `area:ci` | `ai:ready` | `ai:implementing` → close |
| M12-T009 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T008 closed | `ai:implementing` → close |

T007 is the only task that starts `ai:blocked` and requires a
`decision:confirmed` comment with an explicit "approved to submit"
record before triage may promote it to `ai:ready`. This is enforced
by the `github-issue-triage` agent rules in
`.claude/skills/github-issue-triage/`.

T001 carries `type:arch` so the Discovery / Debate Gate fires
unambiguously; the triage agent should refuse to promote T001 to
`ai:ready` until the closing issue records the four user decisions
from the M12 plan conversation (shape, M11 coupling, teams scope,
UI scope) verbatim.

The PR for each task uses `.github/pull_request_template.md`. The
"Remote side effects" section is load-bearing: T007's PR is the ONLY
M12 PR that may check the "Live external submission" box, and must
link the approval comment from the closing issue.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `devpost_submit` | Worker stages a complete submission pack and calls into `tools/kca/devpost.py::cmd_submit` | `human_decisions` row + comment on the closing GitHub issue | Project owner / reviewer named on the issue |
| `demo_upload` | Not used in M12 (a follow-up: video / demo upload from the agent runtime) | n/a | n/a |
| `team_invite` | Not used in M12 (deny by default; full invite flow is a follow-up) | n/a | n/a |
| `kaggle_submit` / `kernel_push` | Not used in M12 (covered by M9 / M10) | n/a | n/a |

The Devpost approval flow inside M12 is:

```
worker stages submission_pack (README, demo plan, source link)
  → reviewer-gate writes agent_reviews row + agent_job_events
    (target_op="devpost_submit")
  → decision_api surfaces pending decision (POST /decisions queued; UI
    reads via supabase-js until issue #15 lands GET /decisions)
  → UI Approval Inbox renders pending decision
  → human approves via UI (POST /decisions/<id>/approve) OR
    `kca decisions approve --id <id>`
  → human comments "approved to submit" on the closing issue
  → triage agent promotes issue to `decision:confirmed` + `ai:ready`
  → M12-T007 Loop Prompt runs ONE `kca devpost submit`
  → submission URL captured; submissions row written with
    platform='devpost'
  → PR opens with the approval comment linked
```

A second real Devpost submission inside M12 is **out of scope**. If a
follow-up experiment in T006/T008 turns out to need its own submission,
file it as a new M12.x issue and gate it the same way.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m12_e2e.py` (M12-T008) passing in
  dry-run + new `tests/test_m12_smoke.py` passing when
  `SUPABASE_DB_URL` is set.
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui install --frozen-lockfile`, `pnpm -C ui lint`,
  `pnpm -C ui typecheck`, `pnpm -C ui build`, `pnpm -C ui run test --run`
  — all clean. May SKIP in the agent's local sandbox if pnpm is not on
  PATH (CI is authoritative).
- `kca run list --json` shows the M12 hackathon run with recorded
  `checklist_completion` metric and (after T007) a recorded
  `submissions` row referencing the same run.
- `docs/evidence/m12/t000-candidates.md` exists and lists 2–3
  candidates; closing issue body records the human-picked slug.
- `docs/evidence/m12/t001/discovery/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`
  exist; each carries its canonical acceptance line verbatim.
- `docs/adr/0018-generalized-competition-type.md` exists and is
  referenced from `docs/milestones/README.md` §M12.
- `supabase/migrations/0009_m12_competition_type_teams.sql` applied
  locally; the M9 / M10 baseline rows still resolve their policy
  correctly with `competition_type='kaggle'`.
- M12-T007 closing issue links to the approval comment AND the
  resulting `submissions` row id AND the Devpost submission URL.
- `docs/milestones/m12/final-review.md` exists and follows the M9 / M9.4 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- A real Devpost submission returns an error (rate limit, rules
  violation, missing field). The fix path is local: regenerate the
  submission pack and re-request approval; do NOT silently retry.
- The reviewer gate (M12-T007) fails to fire when it should, or fires
  when it shouldn't.
- Any `policy:approval-required` issue advances without the corresponding
  `decision:confirmed` label and comment.
- Any test in the validation suite regresses from green to red.
- Migration 0009 breaks a Kaggle row's policy resolution (regression
  against M9 / M10 baseline rows).
- DEVPOST credentials, the DSN, or `.env*` are accidentally printed in
  any log, audit row, or PR. Stop and rotate the credential immediately.
- A Discovery / Debate Gate report is missing its canonical
  acceptance line. Re-run the agent; do not patch the report by hand.

If M12 surfaces a new architectural decision (e.g. a different
team-scoped permission model than what ADR-0018 settled on, a new
artifact-storage shape for submission packs, a richer hackathon-rules
ingestion schema), **pause and ask** — those are M12.x / M13 decisions,
not M12 expansion. Open an ADR draft in `docs/adr/` and stop the
milestone there.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# Devpost credentials — populate .env from env.example after T003 lands
# the documented env-var names. Never `cat .env`.

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M12-T000 from docs/milestones/m12/loop-prompts.md."
# ...repeat for M12-T001 … M12-T009.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M12 — write docs/milestones/m12/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca` subcommand
that reaches Supabase) need `dangerouslyDisableSandbox=true`. The real
Devpost call inside M12-T007 also needs sandbox bypass (network out
to `devpost.com`).

---

## Human decisions needed before starting M12

These were confirmed during the M12 planning conversation on 2026-05-26
and are recorded here for the milestone-loop-runner's read list:

1. **Milestone shape.** Full regression (M9/M10 pattern). Confirmed.
2. **M11 coupling.** M12 owns the `competition_type` schema; M11
   reuses it later. The `ctf` enum value is required in M12-T002 so
   M11 can plug in without a second migration. Confirmed.
3. **Team identity scope.** Minimal team model in M12 — `teams` +
   `team_memberships` tables; idea board scopes to team; no
   invite / role flow. Confirmed.
4. **UI scope.** Two new pages in M12: `HackathonDeadline.tsx` and
   `SubmissionChecklist.tsx`. Reuse existing `ApprovalInbox` /
   `DecisionGate`. Confirmed.
5. **Target hackathon.** Picked in M12-T000 from a 2–3 candidate list
   produced by the survey; human comment on the closing issue
   selects.
6. **Submission op.** Full real Devpost submit under human approval —
   analog of M9 `kaggle_submit`. One submission per milestone.
   Confirmed.
7. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed.

The closing GitHub issue for M12 is the canonical record of these
decisions and is `decision:confirmed` + `ai:ready` once they are
captured.
