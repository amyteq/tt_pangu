# M11 — Loop Prompts

_Authorized CTF / lab workflow milestone — first non-Kaggle competition platform on
the kaggle-code-agent stack._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M9 exit confirmed (live LB recorded on Spaceship Titanic; see
`docs/milestones/m9/final-review.md`). M10 may run in parallel; the only hard dependency
M11 inherits from M10 is the dotenv-leak fix (issue #11), which must be
merged on `main` before **M11-T008** writes its e2e refusal tests._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md`
(sequencing, no real Kaggle/Anthropic outside designated approval paths, DB DSN +
sandbox bypass, **per-milestone worktree by default**, secret denylist, **§7
Discovery / Debate Gate for `arch:` tagged tasks**)._

---

## M11 at a glance

M11 is the **first CTF / authorized-lab regression** for this platform, and
the first milestone to validate that the worker / reviewer / approval-inbox
stack works for a **non-Kaggle competition policy**. M9 + M10 covered Kaggle
CSV submission and Kaggle kernel push respectively. M11 covers CTF jeopardy:
challenge inventory, scoped solver execution, and flag submission to the
event endpoint.

The CTF user pattern (from the planning Q&A) is:

1. Check [CTFtime calendar](https://ctftime.org/calendar/) for upcoming events.
2. Register on the event site **as a human** (no browser-automated sign-up in
   M11); record event credentials under `~/.ctf/<event-slug>.json` or
   `CTF_<EVENT>_*` env vars.
3. For each challenge: read description, download attachments, decide whether
   the challenge is local-only (zip / docker bundle) or remote (must hit the
   event's challenge endpoint).
4. Solve locally where possible; submit the flag to the event's API.

M11 brings (1) into a `kca ctf event register` LOCAL_WRITE flow, defers (2)
to the human, exercises (3) end-to-end against a **frozen past-event bundle**
under `data/ctf/<event>/<challenge>/` for deterministic CI, and exercises (4)
once for real against a **single live CTFtime-listed event** under explicit
human approval.

M11 is **not** a leaderboard-chasing milestone. The acceptance criterion is
that the CTF workflow runs end-to-end correctly under the approval gates and
hard-refuses out-of-scope targets. Solver quality / category coverage is
captured as future work — see `docs/architecture/m11-ctf-workflow.md` §
"Out of scope".

Direct entry into M11 is blocked until **all** are true:

- M9 is merged on `main` (`docs/milestones/m9/final-review.md` exists and reports PASS).
- The Discovery / Debate Gate (M11-T000) has produced all three subagent
  reports with byte-for-byte acceptance lines under
  `docs/evidence/m11/discovery/`.
- Issue #11 (dotenv-leak / secret-file hygiene in pytest subprocess) is
  merged on `main`. This is a soft pre-req for **M11-T008** (the e2e
  refusal-path test): M11-T000 through M11-T007 may proceed in parallel
  with #11 work.
- The local Supabase container is running; migration `0001_init.sql`'s
  `ctf_scopes` table is reachable.

### What's in scope

| Capability | Owned by | M11 touches |
|---|---|---|
| Discovery / Debate Gate for CTF data model + new approval ops | `.claude/agents/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`, `docs/architecture/discovery-debate-gate.md` | T000 — all three reports + byte-checkable acceptance |
| Event / challenge / attempt schema | `supabase/migrations/0008_m11_ctf.sql` + `src/db/ctf.py` | T001 |
| New approval operations (`challenge_run`, `flag_submit`, `network_egress`) | `.kca/permissions/{default,permissive-dev,competition-runner}.yaml`, `src/worker/reviewer.py`, `src/worker/worker.py`, `.claude/settings.json`, `.claude/hooks/guard_tool.py` | T002 |
| `kca ctf` CLI surface | `tools/kca/ctf.py` + `tools/kca/kca.py::add_parsers` | T003 |
| Frozen past-event challenge bundle (1 web + 1 crypto) | `data/ctf/<event-slug>/{web-1,crypto-1}/` | T004 |
| Agent worker drives ctf-sandbox skill to solve locally | `src/worker/`, `.claude/skills/ctf-sandbox/SKILL.md`, `tools/kca/run.py` | T005 |
| Reviewer-gate before solver run + flag submit | `src/worker/reviewer.py`, `services/decision_api/app.py`, UI Approval Inbox | T006 |
| ONE real flag submission to a live CTFtime event | `tools/kca/ctf.py::cmd_flag_submit`, `ctf_attempts` table | T007 — single real call |
| E2E refusal-path tests | `tests/test_m11_e2e.py`, `tests/test_m11_smoke.py` | T008 |
| ADRs + architecture doc | `docs/adr/0016-ctf-data-model.md`, `docs/adr/0017-ctf-approval-gates.md`, `docs/architecture/m11-ctf-workflow.md` | T001 / T002 / T009 |
| Final review + handoff | `milestone-final-review` skill, `worktree-milestone-pr` skill | T009 |
| GitHub issue / label workflow | `.github/labels.yml`, `.github/ISSUE_TEMPLATE/feature-work.yml`, PR template | every task |

### What's NOT in scope

- Running flag submissions outside T007's single approved call.
- Browser-automated event sign-up. M11 reads human-supplied credentials only.
- Pwn / reverse-engineering / forensics agent-loop solves. The taxonomy
  supports them (`ctf_challenges.category`) but the M11 solve loop exercises
  only `web` + `crypto`. Filed as follow-up issues at milestone close.
- CTFtime calendar polling / auto-event-watch / scheduled-job auto-submit.
- Changing production Supabase.
- Implementing M10 follow-ups (parallel milestone; cross-cutting items file
  as their own issues).
- Implementing M9 follow-ups A, C, D, E (still tracked as issues #14, #15, #16,
  #17). Issue #11 is the only soft pre-req (see entry gates).

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the local
`supabase-db` container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`)
needs `dangerouslyDisableSandbox=true`. The real CTF event API call inside
M11-T007 also needs sandbox bypass and an approved `ctf_scopes.target_urls`
entry covering the submit endpoint.

---

## M11 task summary

| Task | Tag | Goal | Loop Prompt |
|---|---|---|---|
| M11-T000 | `arch:` | Discovery / Debate Gate for the CTF data model + three new approval ops + CTFtime workflow taxonomy. Three subagent reports under `docs/evidence/m11/discovery/`. **Blocks T001+.** | Prompt 0 |
| M11-T001 | `arch:` | Migration `0008_m11_ctf.sql` + `src/db/ctf.py` helpers. ADR-0016 lands here. | Prompt 1 |
| M11-T002 | `arch:` | Permission policy + reviewer-gate wiring for `challenge_run`, `flag_submit`, `network_egress`. ADR-0017 lands here. | Prompt 2 |
| M11-T003 | — | `kca ctf` CLI surface (`event/challenge/scope/solver/flag`). | Prompt 3 |
| M11-T004 | — | Frozen past-event bundle under `data/ctf/<event>/{web-1,crypto-1}/`. | Prompt 4 |
| M11-T005 | — | Agent worker loop solves bundled web + crypto challenge locally; records `ctf_attempts` + `experiment_runs`. | Prompt 5 |
| M11-T006 | — | Reviewer gate fires for `challenge_run` + `flag_submit`; UI Approval Inbox surfaces; approval round-trip recorded. | Prompt 6 |
| M11-T007 | — | **ONE** real flag submission to a live CTFtime-listed event under explicit human approval. | Prompt 7 |
| M11-T008 | — | `tests/test_m11_e2e.py` + `tests/test_m11_smoke.py` (dry-run + refusal paths, no creds, no net). Soft pre-req: issue #11 merged. | Prompt 8 |
| M11-T009 | — | M11 exit criteria + `docs/milestones/m11/final-review.md` + handoff + worktree-milestone-pr. | Prompt 9 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m11/M11-T00N-*.md` spec.

---

## Loop Prompt 0 — M11-T000 Discovery / Debate Gate

```
/goal Execute M11-T000 Discovery / Debate Gate for the M11 CTF architecture until all three subagent reports exist with verbatim acceptance lines or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md (especially §7 Discovery / Debate Gate)
Task spec: docs/tasks/m11/M11-T000-discovery-debate-gate.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md §M11
- docs/architecture/discovery-debate-gate.md
- docs/architecture/design-archaeology.md
- docs/milestones/m9/handoff.md
- docs/adr/0005-job-taxonomy.md (project_kind enum, ctf platform slug)
- docs/adr/0006-configurable-approval-gates.md (approval-op data shape)
- supabase/migrations/0001_init.sql (existing ctf_scopes table)
- .claude/skills/ctf-sandbox/SKILL.md (existing workflow)
- src/worker/reviewer.py (existing reviewer-gate pattern)
- docs/evidence/m9_4-kkr-replay/ (worked precedent: kkr.py replay)

Mission (full version in task spec):
Invoke legacy-archaeologist (with the existing CTF artefacts named in §
"Read also"), then requirements-skeptic, then design-red-team — in that
order. Produce three reports under docs/evidence/m11/discovery/ that
satisfy the verbatim acceptance lines in docs/architecture/
discovery-debate-gate.md. Do NOT write code, do NOT modify schema, do
NOT touch .kca/permissions/ in this Loop Prompt. T000 is gate-only.
A missing acceptance line is a T000 FAIL and blocks T001 onward.
```

---

## Loop Prompt 1 — M11-T001 CTF schema + DB layer

```
/goal Execute M11-T001 ctf_events / ctf_challenges / ctf_attempts schema + src/db/ctf.py helpers until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T001-ctf-schema-db.md

Read also (background context):
- M11-T000 closeout + docs/evidence/m11/discovery/legacy-archaeologist.md
  (load-bearing for the schema shape decisions)
- supabase/migrations/0001_init.sql (ctf_scopes already exists)
- supabase/migrations/0004_m4_competition_repo.sql (latest competition
  table extension precedent)
- src/db/__init__.py / src/db/research.py (helper pattern precedent)
- docs/adr/0016-ctf-data-model.md (write this ADR as part of T001 if
  not already drafted from T000's design-red-team report)

Mission (full version in task spec):
Author supabase/migrations/0008_m11_ctf.sql with ctf_events,
ctf_challenges, ctf_attempts (FKs to projects + ctf_scopes; RLS
enabled, no policies yet). Apply against the local supabase-db
container only (NEVER production). Add src/db/ctf.py with the
register/add/get/list/record helpers named in the task spec. Add
ADR-0016 documenting the table shape, multi-event identity, and
retention policy for failed attempts. No CLI changes in this Loop
Prompt — those land in T003.
```

---

## Loop Prompt 2 — M11-T002 Approval gates (`challenge_run` / `flag_submit` / `network_egress`)

```
/goal Execute M11-T002 new approval operations + reviewer-gate wiring until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T002-approval-gates.md

Read also (background context):
- M11-T000 closeout + docs/evidence/m11/discovery/design-red-team.md
- M11-T001 closeout
- docs/adr/0006-configurable-approval-gates.md (operation data shape)
- .kca/permissions/{default,permissive-dev,competition-runner}.yaml
- src/worker/reviewer.py (should_consult_reviewer, run_review,
  target_op shape)
- src/worker/worker.py (_tool_call, target_op extraction)
- .claude/settings.json (ask-list pattern)
- .claude/hooks/guard_tool.py (deny-list pattern; ~/.ctf/* coverage)
- docs/tasks/m9/M9-T003-reviewer-approval-gate.md (kaggle_submit
  precedent)
- docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md (kernel_push
  precedent)

Mission (full version in task spec):
Add three operations to .kca/permissions/*.yaml: challenge_run (ask),
flag_submit (ask), network_egress (deny outside an authorized
ctf_scopes.target_urls row; ask when scope+URL match). Extend
src/worker/reviewer.py::should_consult_reviewer to include the new
ops. Extend src/worker/worker.py::_tool_call to emit target_op for
the new ops. Add Bash(kca ctf flag submit*) to .claude/settings.json
ask-list. Extend .claude/hooks/guard_tool.py to cover ~/.ctf/*.json
reads outside the allow-listed kca ctf flow. Add ADR-0017 documenting
the three ops, defaults, audit shape. Smoke-test each op's
default_decision via the unit-test pattern in tests/test_reviewer.py
(or add a new tests/test_reviewer_m11.py).
```

---

## Loop Prompt 3 — M11-T003 `kca ctf` CLI surface

```
/goal Execute M11-T003 kca ctf CLI surface until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T003-kca-ctf-cli.md

Read also (background context):
- M11-T001 closeout (DB helpers in src/db/ctf.py)
- M11-T002 closeout (the new approval ops)
- tools/kca/competition.py (cmd_register precedent — LOCAL_WRITE,
  idempotent)
- tools/kca/kg.py (cmd_submit + cmd_push — credential-gate +
  reviewer-gate + audit-row sequence)
- tools/kca/research_fetch.py (HTTP + Playwright; reuse, don't fork)
- tools/kca/kca.py::add_parsers (subparser registration pattern)
- tools/kca/COMMANDS.md (CLI documentation pattern)

Mission (full version in task spec):
Add tools/kca/ctf.py with subcommands:
  event {register, list, info}
  challenge {add, fetch, list, info}
  scope {set, list, verify}
  solver run [--dry-run]
  flag submit [--dry-run]
All LOCAL_WRITE commands write only the local DB. Remote calls
(challenge fetch from a registered event URL, flag submit) require
KCA_ALLOW_REMOTE=1 + dangerouslyDisableSandbox AND a matching
ctf_scopes.target_urls row. Register the ctf subparser in
tools/kca/kca.py::add_parsers. Document the new surface in
tools/kca/COMMANDS.md. The flag submit subcommand must echo only
"accepted=true|false" + http status, never the flag string itself.
```

---

## Loop Prompt 4 — M11-T004 Frozen past-event challenge bundle

```
/goal Execute M11-T004 frozen past-event challenge bundle (1 web + 1 crypto) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T004-frozen-challenges.md

Read also (background context):
- M11-T001 closeout (ctf_events / ctf_challenges / ctf_scopes schema)
- M11-T003 closeout (kca ctf event register / challenge add)
- .gitignore (data/ rules)
- .claude/skills/ctf-sandbox/SKILL.md (workflow expectations)
- The picoCTF archive (https://picoctf.org/) OR another permissively
  licensed past-event source — research-brief the licensing first.

Mission (full version in task spec):
Pick a permissively licensed past-event source (picoCTF or
equivalent). Author data/ctf/<event-slug>/web-1/ and
data/ctf/<event-slug>/crypto-1/ as bundled challenges with:
  - challenge.yaml (category, points, description, attachments,
    expected_flag_format, scope_ref pointing to a ctf_scopes row)
  - attachments (small files; 1MB cap per file; bigger = gitignored)
  - docker-compose.yml (web challenge only; crypto runs in-process)
  - solver_template.py (skeleton the agent will fill in T005)
Insert via `kca ctf event register` + `kca ctf challenge add` (T003).
Record source attribution + license in data/ctf/README.md.
No agent solve in this Loop Prompt — that's T005.
```

---

## Loop Prompt 5 — M11-T005 Agent loop solves bundled challenges locally

```
/goal Execute M11-T005 agent solver loop against bundled web + crypto challenges until both flags recovered or stop after 100 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T005-local-solve-loop.md

Read also (background context):
- M11-T004 closeout (bundled challenges + scope rows)
- .claude/skills/ctf-sandbox/SKILL.md (workflow body — may be
  extended in T005 to cite the new kca ctf commands)
- src/worker/worker.py (AgentWorker loop)
- tools/kca/run.py (run-init + record-metric)
- tools/kca/ctf.py::cmd_solver_run (T003)
- docs/tasks/m9/M9-T002-baseline-loop.md (the closest precedent — Kaggle
  baseline-loop pattern adapted to CTF)

Mission (full version in task spec):
Drive AgentWorker through one solve cycle per bundled challenge.
Sequence: read challenge.yaml + attachments → category triage →
solver_template.py → run in-scope (web: docker-compose up + httpx;
crypto: in-process) → recover flag → record ctf_attempts row
(accepted=true) + experiment_runs row with flag_length (NOT value).
No remote network. No reviewer gate fires here (gates exercise in
T006 with a more realistic challenge_run path). Both flags MUST be
recovered for T005 to PASS.
```

---

## Loop Prompt 6 — M11-T006 Reviewer gate for `challenge_run` + `flag_submit`

```
/goal Execute M11-T006 reviewer-gate firing for challenge_run and flag_submit until both gates record an agent_reviews + human_decisions round-trip or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T006-reviewer-gate.md

Read also (background context):
- M11-T002 closeout (the new ops)
- M11-T005 closeout (solver loop)
- src/worker/reviewer.py
- services/decision_api/app.py
- tools/kca/decisions.py
- supabase/migrations/0006_m6_reviews_spans.sql (agent_reviews
  schema)
- ui/src/pages/ApprovalInbox.tsx, DecisionGate.tsx
- docs/tasks/m9/M9-T003-reviewer-approval-gate.md (kaggle_submit
  precedent)
- docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md (kernel_push
  precedent)
- Issue #15 (no GET /decisions endpoint — work around as M9/M10 did)
- Issue #16 (reviewer_decision event_type wording drift — use what
  the worker emits today)

Mission (full version in task spec):
Drive the worker to a point where it must (a) execute challenge_run
against the bundled web challenge in T004 (this time with the gate
ON), and separately (b) submit a flag for the same challenge via
flag_submit (still LOCAL_WRITE — no real network). Both reviewer
gates fire; both write agent_reviews + human_decisions rows. The
decision_api exposes the pending decisions to the UI Approval Inbox.
Approve both via `kca decisions approve --id <id>` (NOT via a real
external call). The next step (real flag submit) is gated to T007
and requires explicit human-typed approval recorded on the closing
issue.
```

---

## Loop Prompt 7 — M11-T007 ONE real flag submission to a live event

```
/goal Execute M11-T007 one approved live flag submission to a CTFtime-listed event until ctf_attempts row recorded or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T007-live-flag-submission.md

Override note: this is the ONLY Loop Prompt in the milestone that
makes a real external network call to a CTF event API.
Pre-conditions before running:
  - M11-T006 closeout shows a `decision:confirmed` human decision
    on the closing issue.
  - ~/.ctf/<event-slug>.json or CTF_<EVENT>_USERNAME / CTF_<EVENT>_TOKEN
    is populated for the chosen event (human action; no automation).
  - A ctf_scopes row exists for the chosen event with target_urls
    covering the submit endpoint; scope is not expired.
  - The closing issue has `policy:approval-required` AND a human
    comment explicitly approving the submission (this milestone's
    only such record).
  - The flag was recovered locally (or via in-scope challenge_run
    against the live event's challenge endpoint, also under approval).

Read also (background context):
- M11-T003 closeout (kca ctf flag submit credential-gate)
- M11-T006 closeout (approval round-trip)
- tools/kca/ctf.py::cmd_flag_submit
- .claude/settings.json (Bash(kca ctf flag submit*) on ask)
- supabase/migrations/0008_m11_ctf.sql (ctf_attempts shape)
- docs/tasks/m9/M9-T004-real-submission.md (single-submission precedent)

Mission (full version in task spec):
Run exactly ONE real `kca ctf flag submit --event <slug>
--challenge <slug> --flag <flag>` against the approved live event.
Record the ctf_attempts row with accepted=true|false and the event
response's HTTP status. Do NOT echo the flag string anywhere. Do
NOT iterate beyond this one submission inside this Loop Prompt. If
the event returns an error (rate limit, invalid flag, scope drift),
HALT and open a follow-up issue — do not silently retry.
```

---

## Loop Prompt 8 — M11-T008 E2E smoke + refusal-path tests (dry-run, no credentials)

```
/goal Execute M11-T008 tests/test_m11_e2e.py + tests/test_m11_smoke.py until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T008-e2e-dryrun-test.md

Soft pre-req: issue #11 (dotenv-leak / secret-file hygiene in pytest
subprocess) should be merged on `main` BEFORE this Loop Prompt runs.
Verify with `gh issue view 11 --json state` returns `"CLOSED"`. If
#11 is not yet closed, do NOT write a test that subprocess-shells in
a way that would inherit `.env` or `~/.ctf/*` to the child. Halt and
ask if unsure.

Read also (background context):
- tests/test_m9_e2e.py (closest pattern — Kaggle dry-run)
- tests/test_m9_smoke.py (DB-gated assertion pattern)
- tests/test_m10_e2e.py (kernel-push refusal pattern; mirror its
  shape for flag_submit / challenge_run refusals)
- src/worker/worker.py (dry_run path)
- tools/kca/ctf.py::cmd_flag_submit (credential-gate refusal)
- Issue #11 (the leak this test must NOT repeat)

Mission (full version in task spec):
Add tests/test_m11_e2e.py covering:
  (a) flag_submit refused without prior approval (dry-run path)
  (b) challenge_run refused for a target URL outside
      ctf_scopes.target_urls
  (c) network_egress denied for an attempted POST to kaggle.com
      from a CTF job context (cross-platform isolation)
  (d) bundled web + crypto solver round-trip works locally without
      real network (uses the T004 fixtures)
  (e) audit-grep: 0 lines echo .env or ~/.ctf/* contents in any test
      run's stdout/stderr
Add tests/test_m11_smoke.py with DB-gated assertions mirroring
tests/test_m9_smoke.py. No real network. No credentials. CI picks
the tests up under the existing no-db + live-db jobs.
```

---

## Loop Prompt 9 — M11-T009 Exit criteria + final review

```
/goal Execute M11-T009 M11 exit criteria validation + final review until docs/milestones/m11/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m11/M11-T009-m11-exit-criteria.md

Read also (background context):
- all M11 closeouts (T000–T008)
- docs/milestones/m9/final-review.md (layout precedent)
- docs/milestones/m10/final-review.md (when it lands — closest CTF-style
  layout match)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix (10 checks from
docs/milestones/README.md §M11 + the per-task closeout assertions), then
call milestone-final-review to write docs/milestones/m11/final-review.md
mirroring the M9 / M10 layout. Write docs/architecture/m11-ctf-
workflow.md if not already drafted. Update PROJECT_STATE.md,
README.md, and docs/milestones/README.md §M11 to `✓ done`. Write
docs/milestones/m11/handoff.md per docs/milestones/_templates/handoff-prompt.md.

Override note: this is the only Loop Prompt in M11 that calls
worktree-milestone-pr (one commit per Loop Prompt + the final
review as the last commit, push the worktree branch, open the
final M11 PR against main).
```

---

## GitHub issue / label workflow for M11

Each M11 task is filed as a GitHub issue using the `feature-work.yml` form,
labelled per task type. The canonical **M11 proposal issue** (TBD —
filed before T000 starts) collects the planning Q&A decisions; individual
task issues link back to it.

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M11-T000 | `type:feature`, `ai:triage`, `arch:`, `area:agent`, `area:docs` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M11-T001 | `type:feature`, `ai:triage`, `arch:`, `area:supabase`, `area:db` | `ai:ready` (after T000 closed) | `ai:implementing` → close |
| M11-T002 | `type:feature`, `ai:triage`, `arch:`, `area:worker`, `area:security`, `area:policy` | `ai:ready` (after T001 closed) | `ai:implementing` → close |
| M11-T003 | `type:feature`, `ai:triage`, `area:cli`, `area:ctf` | `ai:ready` (after T001 + T002 closed) | `ai:implementing` → close |
| M11-T004 | `type:feature`, `ai:triage`, `area:ctf`, `area:fixtures` | `ai:ready` (after T003 closed) | `ai:implementing` → close |
| M11-T005 | `type:feature`, `ai:triage`, `area:worker`, `area:ctf` | `ai:ready` (after T004 closed) | `ai:implementing` → close |
| M11-T006 | `type:feature`, `ai:triage`, `area:worker`, `area:supabase`, `area:ui` | `ai:ready` (after T005 closed) | `ai:implementing` → close |
| M11-T007 | `type:feature`, `ai:blocked`, `policy:approval-required`, `decision:needed`, `area:ctf`, `priority:P0` | `decision:confirmed` + `ai:ready` only after human comment "approved to submit" | `ai:implementing` → close |
| M11-T008 | `type:test-gap`, `ai:triage`, `area:testing`, `area:ci` | `ai:ready` only after issue #11 is closed | `ai:implementing` → close |
| M11-T009 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T008 closed | `ai:implementing` → close |

T007 is the only task that starts `ai:blocked` and requires a
`decision:confirmed` comment with an explicit "approved to submit" record
before triage may promote it to `ai:ready`. This is enforced by the
`github-issue-triage` agent rules in `.claude/skills/github-issue-triage/`.

T008 is the only task gated on closing a separate issue (#11). The
triage agent should refuse to promote T008 to `ai:ready` while
`gh issue view 11 --json state` returns `"OPEN"`.

The PR for each task uses `.github/pull_request_template.md`. The
"Remote side effects" section is load-bearing: T007's PR is the ONLY
M11 PR that may check the "Live external API call" box, and must link the
approval comment from the closing issue.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `challenge_run` | Worker is about to invoke a solver against a target whose URL is in `ctf_scopes.target_urls` OR is a local in-scope service | `agent_reviews` row + `human_decisions` row + (T007 only) comment on the closing GitHub issue | Project owner / reviewer named on the issue |
| `flag_submit` | `tools/kca/ctf.py::cmd_flag_submit` is invoked with `--dry-run=False` | `agent_reviews` row + `human_decisions` row + (T007 only) approval comment | Project owner |
| `network_egress` | Worker attempts to call any host NOT in `ctf_scopes.target_urls` AND the host is not on the global allowlist | DENY at the reviewer-gate; recorded as `agent_reviews.verdict=reject` + audit row in `agent_tool_audit` | Not applicable — deny is final; the human must edit the scope row to widen it |
| `kaggle_submit` | Not used in M11 | n/a | n/a |
| `kernel_push` | Not used in M11 | n/a | n/a |

The CTF approval flow inside M11 is:

```
worker stages solver / flag artifact + target URL
  → reviewer-gate writes agent_reviews row + agent_job_events
    (target_op="challenge_run" or "flag_submit")
  → decision_api surfaces pending decision (POST /decisions queued;
    UI reads via supabase-js until issue #15 lands GET /decisions)
  → UI Approval Inbox renders pending decision
  → human approves via UI (POST /decisions/<id>/approve) OR
    `kca decisions approve --id <id>`
  → (T007 only) human comments "approved to submit" on the closing
    issue
  → triage agent promotes issue to `decision:confirmed` + `ai:ready`
  → M11-T007 Loop Prompt runs ONE `kca ctf flag submit`
  → ctf_attempts row written with accepted=true|false + http_status
  → PR opens with the approval comment linked
```

A second real flag submission inside M11 is **out of scope**. If a
follow-up challenge in M11-T005 or M11-T007 surfaces another flag
that the human wants submitted, file it as a new M11-followup issue
and gate it the same way.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m11_e2e.py` + `tests/test_m11_smoke.py`
  (M11-T008) passing in dry-run.
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui install --frozen-lockfile`, `pnpm -C ui lint`,
  `pnpm -C ui typecheck`, `pnpm -C ui build`, `pnpm -C ui run test --run`
  — all clean. (May SKIP in the agent's local sandbox if pnpm is not on
  PATH, same posture as M9 / M10 — CI is authoritative.)
- All three Discovery / Debate Gate reports exist at
  `docs/evidence/m11/discovery/{legacy-archaeologist,
  requirements-skeptic,design-red-team}.md` with byte-checkable
  acceptance lines.
- `kca ctf event list --json`, `kca ctf challenge list --event <slug>
  --json`, `kca ctf scope list --json` exit 0; help text mentions
  reviewer-gated operations.
- `manifest.json` for the frozen event is committed; raw oversize
  attachments (>1MB) are not (`data/ctf/<event>/*/attachments/` stays
  gitignored beyond the cap).
- M11-T007 closing issue links to the approval comment AND the resulting
  `ctf_attempts` row id AND the event's HTTP status response.
- `docs/milestones/m11/final-review.md` exists and follows the M9 / M10 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- A real CTF event call returns an error from the event API outside T007's
  single approved call (rate limit, scope violation, bad credentials). The
  fix path is local: regenerate solver / re-verify scope and re-request
  approval; do NOT silently retry.
- The reviewer gate (M11-T006) fails to fire for `challenge_run` or
  `flag_submit` when it should, or fires when it shouldn't.
- Any `policy:approval-required` issue advances without the corresponding
  `decision:confirmed` label and comment.
- Any test in the validation suite regresses from green to red.
- The DSN, Kaggle credentials, `~/.ctf/*`, or `.env*` are accidentally
  printed in any log, audit row, or PR. Stop and rotate the credential
  immediately.
- The Discovery / Debate Gate at T000 surfaces an undecided question that
  invalidates the data model (e.g. multi-event identity collision; team-
  account vs. individual-account ambiguity). Pause, draft a new ADR, and
  restart T000.
- A `network_egress` deny fails to trigger for an attempted call to a host
  outside the scope row (silent egress = critical security regression).
- Issue #11 is reopened mid-milestone with evidence that the leak
  re-emerged. Halt T008 work until #11 is green again.

If M11 needs a new architectural decision (e.g. multi-event credential
rotation; pwn/rev solver harness; CTFtime calendar auto-watch), **pause
and ask** — those are M11-followup / M13 decisions, not M11 expansion.
Open an ADR draft in `docs/adr/` and stop the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# CTF event credentials — populate ~/.ctf/<event-slug>.json from the
# event site (human action). Or use env vars CTF_<EVENT>_USERNAME /
# CTF_<EVENT>_TOKEN. Then verify with `kca ctf event info --slug
# <event>` (READ_ONLY). Never `cat ~/.ctf/*.json`.

# Per-prompt invocation (each Loop Prompt runs inside the shared M11
# worktree per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M11-T000 from docs/milestones/m11/loop-prompts.md."
# ...repeat for M11-T001 … M11-T009.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M11 — write docs/milestones/m11/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca` subcommand
that reaches Supabase) need `dangerouslyDisableSandbox=true`. The real
CTF event API call inside M11-T007 also needs sandbox bypass (network
out to the event's submit endpoint, which MUST be covered by the
`ctf_scopes.target_urls` row for the chosen event).

---

## Human decisions needed before starting M11

The following decisions need to be `decision:confirmed` on the M11 proposal
issue (TBD) before the milestone-loop-runner picks up M11-T000:

1. **Live event for T007.** Which CTFtime-listed event will host the
   single real flag submission? The planning Q&A named `bbbctf.com` as a
   reference; confirm whether to use it or the next upcoming event on
   `https://ctftime.org/calendar/`. Pre-decision affects T004 (frozen
   bundle slug naming) and T007 (credential file path).
2. **Frozen-bundle source.** Which permissively licensed past-event
   archive will T004 pull challenges from? Default candidate: picoCTF
   (CMU/Carnegie Mellon, permissive license). Alternatives: pwnable.kr,
   CSAW Quals archive, individual past-event releases on GitHub.
   T004 must research-brief the license before bundling.
3. **Scope shape.** Does `ctf_scopes` need any new columns beyond what
   migration 0001 already provides (`authorized_scope`, `target_urls`,
   `local_only`, `expires_at`)? The Discovery / Debate Gate may surface
   this; if it proposes additions, fold them into migration 0008.
4. **Challenge-category exercise scope.** Confirmed: web + crypto for
   T005 / T006 / T007. Pwn / rev / forensics filed as M11 follow-ups
   at T009 closeout.
5. **Per-event credential format.** Confirmed: `~/.ctf/<event-slug>.json`
   (JSON object with `username`, `token`, optional `team_id`) OR
   `CTF_<EVENT>_USERNAME` + `CTF_<EVENT>_TOKEN` env vars. The
   guard_tool hook denies direct file reads except inside the
   `kca ctf` flow (T002 wires this).
6. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed.
