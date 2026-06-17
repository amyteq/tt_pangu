# M15 — Loop Prompts

_Close the goal loop on real LB signal + pay down the ADR-0018 tech-debt: add the
explicit submit step so a kernel push actually advances the leaderboard, port
`refresh-rules` onto kaggle 2.0.x, and land the three ADR-0018 hardening
follow-ups (#59/#60/#61) + the local-Docker retire/parity (#64)._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M14 closed (`docs/milestones/m14/final-review.md` exists; the
push≠submit gap #77 + refresh-rules port #78 carried into this milestone)._
_Shared rules: every Loop Prompt below MUST follow
`docs/milestone-loop-protocol.md` (sequencing, no real Kaggle / Anthropic
outside designated paths, DB DSN + sandbox bypass, per-milestone worktree
by default, secret denylist, Discovery / Debate Gate on `arch:` tasks)._

---

## M15 at a glance

M14 left the goal loop one step short: its sanctioned live run did **2 real
kernel pushes but recorded 0 new leaderboard scores**, because a kernel push is
not a competition submission (gap #77). M15 adds the explicit **submit** step
(push → terminal → **submit** → score), running it **autonomously under the KCA
autonomy model** (ADR-0021), and pays down the ADR-0018 tech-debt that M12/M14
deferred.

Per the owner's scope decision, M15 = **goal-loop completion (#77, #78) +
ADR-0018 hardening (#59, #60, #61) + #64**:

| Theme | Issue | Priority | M15 task |
|---|---|---|---|
| Goal loop needs explicit submit step (push ≠ LB submission) | #77 | P1 | T002 (+ T000 design, T007 live) |
| Port `refresh-rules` off removed `competition_view` (kaggle 2.0.x) | #78 | P2 | T001 |
| ADR-0018 F1 — jsonb type-check for `competitions.submission_format` | #59 | P2 | T003 |
| ADR-0018 F2 — `approved_by_user_id` FK on `human_decisions` | #60 | P1 | T004 |
| ADR-0018 F3 — `profile_fallback` event in `permission_policy.py` | #61 | P2 | T005 |
| Cloud Supabase migration parity / retire local Docker | #64 | P2 | T006 |

**Deferred to M16** (not pulled into `ai:ready` — all `decision:needed`):

- #21 / #85 — cross-account quota pool + multi-account user-pool design.
- #83 — cheaper / free GPU compute for experiments.
- FK target for `approved_by_user_id` finalised once Supabase auth
  (`auth.users`) lands.

Direct entry into M15 is blocked until **all** are true:

- M14 is closed on `main` (`docs/milestones/m14/final-review.md` exists and
  reports the push≠submit deviation as the open item M15 resolves).
- Cloud Supabase is the active DB; migrations 0001–0011 applied (0012 lands in
  T004).
- Issues #77 #78 #59 #60 #61 #64 are `ai:ready` (each was `ai:triage`;
  promotion requires explicit acceptance-criteria sign-off — the criteria are
  pinned to each issue body in the task specs).

### What's in scope

| Capability | Owned by | M15 touches |
|---|---|---|
| Explicit-submit-step design + ADR-0020 addendum | `docs/adr/0020-goal-driven-kaggle-loop.md` (addendum) | T000 |
| `refresh-rules` ported onto kaggle 2.0.x | `tools/kca/db.py` + `tools/kca/competition.py` | T001 (issue #78) |
| Explicit submit step (push → submit → score) + autonomy screen + budget gate | `tools/kca/kg.py` + `tools/kca/agent/audit.py` | T002 (issue #77) |
| submission_format JSON-Schema per `competition_type` + read-time validator | `tools/kca/schemas/submission_format/` + `tools/kca/submission_checklist.py` | T003 (issue #59) |
| `human_decisions.approved_by_user_id` (migration 0012) + populate + resolver | `supabase/migrations/0012_m15_*.sql` + `tools/kca/decisions.py` + `permission_policy.py` | T004 (issue #60) |
| `profile_fallback` event on resolver fallback | `tools/kca/agent/permission_policy.py` + `db.append_job_event` | T005 (issue #61) |
| Cloud parity check + retire local Docker docs/config | `docs/milestone-loop-protocol.md` §3 + `docs/tooling/local-supabase.md` + `README.md` | T006 (issue #64) |
| Live autonomous submit validation (≥1 real LB score) | `docs/evidence/m15/T007/` + `kca-<slug>.yaml` autonomy config | T007 |
| Regression tests + exit criteria + final review | `tests/test_m15_*.py` + `docs/milestones/m15/final-review.md` | T008 |

### What's NOT in scope

- **Cross-account quota pooling / multi-account user pool** (#21/#85) —
  `decision:needed`; M16.
- **Cheaper / free GPU compute** (#83) — `decision:needed`; M16.
- **Supabase auth implementation** — M15 adds the NULL `approved_by_user_id`
  column + populate/read path; the `auth.users` FK is finalised when auth lands.
- **A new ML breakthrough** — M15 is a workflow + hardening milestone; the live
  run (T007) proves the submit→score loop records a real score, not a leaderboard
  climb.
- **New migrations beyond 0012** — only T004 touches schema.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the cloud
Supabase pooler needs `dangerouslyDisableSandbox=true`. T007's live Kaggle push +
submit also needs sandbox bypass (network out to `kaggle.com`). (Note: §3's DSN
note still references the retired local `supabase-db` container — T006 fixes it.)

---

## M15 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M15-T000 | `arch:` explicit-submit-step design + ADR-0020 addendum + Discovery / Debate Gate + 8 downstream task specs | Prompt 0 |
| M15-T001 | Port `kca competition refresh-rules` off removed `competition_view` (issue #78) | Prompt 1 |
| M15-T002 | Explicit submit step between push-terminal and `kca kaggle score` + autonomy screen + budget gate (issue #77) | Prompt 2 |
| M15-T003 | JSON-Schema type-check for `competitions.submission_format` per `competition_type` (issue #59) | Prompt 3 |
| M15-T004 | Migration 0012 `human_decisions.approved_by_user_id` + populate + resolver (issue #60) | Prompt 4 |
| M15-T005 | `profile_fallback` event in `permission_policy.py` (issue #61) | Prompt 5 |
| M15-T006 | Cloud Supabase parity check / retire local Docker (issue #64) | Prompt 6 |
| M15-T007 | Live autonomous submit validation — push → submit → score, ≥1 real LB score | Prompt 7 |
| M15-T008 | Regression tests + exit criteria validation + `docs/milestones/m15/final-review.md` | Prompt 8 |

Each task's full scope, acceptance criteria, allowed / forbidden paths, and
closeout format live in the matching `docs/tasks/m15/M15-T00N-*.md` spec
(authored during T000). Until then, the loop prompts below are the
authoritative scope.

---

## Loop Prompt 0 — M15-T000 explicit-submit-step architecture + ADR-0020 addendum (arch:)

```
/goal Execute M15-T000 explicit-submit-step architecture + ADR-0020 addendum + Discovery / Debate Gate transcripts + 8 downstream task specs until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md (note §7 — Discovery / Debate Gate is MANDATORY for this `arch:` task)
Task spec: docs/tasks/m15/M15-T000-submit-step-architecture.md

Read also (background context):
- docs/milestones/README.md §M15
- docs/adr/0020-goal-driven-kaggle-loop.md (§7 budget gate + "Known gaps / follow-ups")
- docs/adr/0021-kca-autonomy-model.md (autonomy screen + audit-log contract)
- docs/evidence/m14/T008/live-run.md (why push ≠ submit — Findings #4)
- Issue #77 (acceptance criteria — pin to the issue body)
- tools/kca/kg.py (cmd_push ~433, _watch_kernel_until_terminal ~697, cmd_score ~1317, _check_budget_gates ~195)
- docs/architecture/discovery-debate-gate.md
- .claude/agents/requirements-skeptic.md
- .claude/agents/legacy-archaeologist.md (skippable — greenfield; document the skip)
- .claude/agents/design-red-team.md

Mission:
Write the ADR-0020 addendum for the explicit submit step. Decide:
  - submit mechanism: output-CSV `kaggle competitions submit` vs kernel "Submit to Competition"
  - loop placement push → terminal → submit → score; how cmd_score matches the LB row
  - ADR-0021 autonomy integration: autonomous + audit summary to .agent/kca/audit.jsonl when enabled & screen-pass; ask otherwise; scenario-4/over-budget/ambiguous stay human-gated
  - budget-gate accounting: _check_budget_gates counts the submit
Run the Discovery / Debate Gate (skip legacy-archaeologist only with an explicit greenfield note — M15 builds on existing primitives). Attach all transcripts under docs/evidence/m15/T000/discovery/. Write the 8 task specs docs/tasks/m15/M15-T001-*.md through M15-T008-*.md as the design output.
No code, no migration, no CLI changes in this Loop Prompt — design only.
```

---

## Loop Prompt 1 — M15-T001 port `refresh-rules` off `competition_view` (issue #78)

```
/goal Execute M15-T001 port kca competition refresh-rules off removed competition_view (issue #78) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T001-refresh-rules-port.md

Read also (background context):
- M15-T000 closeout (ADR-0020 addendum)
- Issue #78 (acceptance criteria — pin to the issue body)
- tools/kca/db.py (_fetch_competition_view ~2787, _map_competition_view ~2818, KaggleApiUnsupported ~161, refresh_competition_rules)
- tools/kca/competition.py (cmd_refresh_rules ~92)
- tests/test_m14_db.py (the two degradation regression tests to preserve)

Mission:
Replace the competition_view call in db._fetch_competition_view with a current Kaggle API surface (competitions_list filtered to the slug, or the REST client) returning the fields _map_competition_view needs. Keep _map_competition_view writing the same competitions columns. Preserve the KaggleApiUnsupported degradation path so cmd_refresh_rules still emits the KAGGLE_API_UNSUPPORTED envelope on genuinely-unsupported clients.
Sequenced early so the T007 live run gets real limits instead of operator-set DB values. No submit-step work, no schema change. Mock the new API surface in tests; a single live refresh-rules may run in T007.
```

---

## Loop Prompt 2 — M15-T002 explicit submit step (issue #77)

```
/goal Execute M15-T002 explicit submit step between push-terminal and kca kaggle score + autonomy screen + budget gate (issue #77) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T002-explicit-submit-step.md

Read also (background context):
- M15-T000 closeout (ADR-0020 addendum — submit-mechanism decision)
- M15-T001 closeout (refresh-rules port)
- Issue #77 (acceptance criteria — pin to the issue body)
- tools/kca/kg.py (cmd_push ~433, _watch_kernel_until_terminal ~697, cmd_score ~1317, _check_budget_gates ~195)
- docs/adr/0021-kca-autonomy-model.md (autonomy screen + audit contract)
- tools/kca/agent/audit.py + the KCA audit path .agent/kca/audit.jsonl (CLAUDE.md still says .agent/audit.jsonl — follow the code path, flag the drift)

Mission:
Add the submit step between push-terminal and score per the T000-chosen mechanism: after _watch_kernel_until_terminal reports terminal, submit the kernel's output and record external_submission_id so cmd_score matches the LB row and writes submissions.public_lb_score. Wire the submit through the ADR-0021 autonomy screen (autonomous + intended-submission summary to .agent/kca/audit.jsonl when enabled & screen-pass; ask otherwise; scenario-4/over-budget/ambiguous human-gated). Make _check_budget_gates count the submit, not just the push.
No real Kaggle submit here — e2e/dry test mocks the submit. Live exercise is T007.
```

---

## Loop Prompt 3 — M15-T003 submission_format JSON-Schema type-check (issue #59)

```
/goal Execute M15-T003 jsonb type-check for competitions.submission_format per competition_type (issue #59) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T003-submission-format-schema.md

Read also (background context):
- Issue #59 (acceptance criteria — pin to the issue body)
- docs/adr/0018-generalized-competition-type.md §"Migration impact" + §"Resolver fallback contract"
- docs/evidence/m12/t001/discovery/design-red-team.md (open_disagreement #1)
- supabase/migrations/0009_m12_competition_type_teams.sql + 0011_m14_goal_loop.sql:71 (the column)
- tools/kca/submission_checklist.py (where the validator lands; _dedup_format_keys + build_checklist)

Mission:
Add one JSON-Schema per competition_type under tools/kca/schemas/submission_format/ (kaggle.json, devpost.json, hackathon_devpost.json, ctf.json, generic.json). Add a validator helper in tools/kca/submission_checklist.py that validates competitions.submission_format against the matching schema on read, keyed by competition_type. Validation failures log a warning + fall back to permissive behaviour — never crash the worker (ADR-0018 resolver-fallback discipline). Tests in tests/test_m12_submission_format_schema.py cover valid + invalid per type; existing M11/M12 rows pass (or update them).
No migration, no write-time enforcement.
```

---

## Loop Prompt 4 — M15-T004 `approved_by_user_id` FK on `human_decisions` (issue #60)

```
/goal Execute M15-T004 migration 0012 human_decisions.approved_by_user_id + populate + resolver (issue #60) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T004-approved-by-user-id-fk.md

Read also (background context):
- Issue #60 (acceptance criteria — pin to the issue body)
- docs/adr/0018-generalized-competition-type.md §"Team-scoped operation rules"
- supabase/migrations/0001_init.sql:157 (human_decisions; rationale is the free-text column, not notes)
- supabase/migrations/0011_m14_goal_loop.sql (0012 is the next free number)
- tools/kca/decisions.py (cmd_approve ~63)
- tools/kca/agent/permission_policy.py (owner-only enforcement consumer)

Mission:
Write supabase/migrations/0012_m15_*.sql adding human_decisions.approved_by_user_id uuid NULL (FK to auth.users deferred until Supabase auth lands — allow NULL now, document the gap in the migration comment). kca decisions approve populates the column from the calling identity. permission_policy.py can read it to enforce owner-only on team-scoped ops (NULL-tolerant: existing rows stay NULL and resolve as today). Tests cover the populate path + the NULL-tolerant resolver path. Migration applies cleanly against cloud Supabase.
The new column is in addition to rationale, not a replacement.
```

---

## Loop Prompt 5 — M15-T005 `profile_fallback` event (issue #61)

```
/goal Execute M15-T005 emit profile_fallback event in permission_policy.py (issue #61) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T005-profile-fallback-event.md

Read also (background context):
- Issue #61 (acceptance criteria — pin to the issue body)
- docs/adr/0018-generalized-competition-type.md §"Resolver fallback contract"
- tools/kca/agent/permission_policy.py (_resolve_profile_for_competition_type ~101, resolve_for_skill ~125)
- tools/kca/db.py (append_job_event ~762 — reuse for the emit)
- supabase/migrations/0003_m3_worker.sql:34 (agent_job_events shape)
- tests/test_m12_policy.py (where the new test lands)

Mission:
When _resolve_profile_for_competition_type falls back (type-specific profile file missing), emit one agent_job_events row via db.append_job_event with event_type='profile_fallback' and data jsonb {"competition_type": "<type>", "intended_profile": "<type>-runner", "actual_profile": "default", "operation": "<op>"}. Dedupe once per fallback per job. Thread job_id into the resolver so it can attribute the event. Test tests/test_m12_policy.py::test_fallback_emits_event covers a missing-profile-file run.
No change to the fallback resolution itself; observability only. No migration.
```

---

## Loop Prompt 6 — M15-T006 cloud Supabase parity / retire local Docker (issue #64)

```
/goal Execute M15-T006 cloud Supabase migration parity check / retire local Docker (issue #64) until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T006-supabase-parity-retire-local.md

Read also (background context):
- Issue #64 (acceptance criteria — pin to the issue body; (a)/(b) choice, recommendation (a))
- M15-T004 closeout (migration 0012 — the latest the parity check must cover)
- docs/milestone-loop-protocol.md §3 (DSN note still points at the retired local supabase-db container)
- docs/tooling/local-supabase.md (the local Docker setup doc to update)
- supabase/migrations/ (0001–0012) + docker-compose.yml (if present) + README.md install section

Mission:
Verify migrations 0001–0012 are all applied on the cloud project (qyoprtshfhfzrczlwbyv); record the result. Then take the issue #64 decision — recommendation (a) retire local Docker: update protocol §3 to point at the cloud DSN as the sole DB path, update README install, remove/deprecate docker-compose.yml, align docs/tooling/local-supabase.md and the memory note. If (b): add scripts/local_db_sync.py replaying 0001–0012 against the local container + a CI "verify local container parity" check.
No schema changes (T004 owns 0012); read-only parity verification of cloud.
```

---

## Loop Prompt 7 — M15-T007 live autonomous submit validation

```
/goal Execute M15-T007 live autonomous submit validation — push → submit → score, ≥1 real LB score until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T007-live-submit-validation.md

Override note: this Loop Prompt runs a REAL Kaggle kernel push AND a REAL
competition submit. The submit runs screened-autonomous under ADR-0021 (records
the intended-submission summary to .agent/kca/audit.jsonl, no per-action ask)
when kca-<slug>.yaml:autonomy.enabled is true and autonomy.screen passes;
scenario-4 / over-budget / ambiguous-rules hand back to the human.

Pre-conditions:
  - T001 + T002 closed (real limits + submit step).
  - KAGGLE_USERNAME / KAGGLE_KEY present.
  - A target competition picked (default: tpu-getting-started, re-using the M10/M14 surface).
  - kca-<slug>.yaml autonomy config present for the target competition.

Read also (background context):
- M15-T002 closeout (the submit step being exercised live)
- M15-T001 closeout (refresh-rules so live limits are real)
- docs/adr/0021-kca-autonomy-model.md (autonomy screen + scenario-4 human gate)
- docs/evidence/m14/T008/live-run.md (the deviation this closes — same evidence shape)
- CLAUDE.md §"KCA autonomous submission strategy" (4 scenarios + ~2h-before-rollover timing)
- tools/kca/kg.py (cmd_push, submit step, cmd_score, _check_budget_gates)

Mission:
Run the loop on the target competition: goal set → explore/select → kca kaggle push → terminal → submit (screened-autonomous) → kca kaggle score. Record ≥1 real submissions.public_lb_score written via the submit → score path, closing the M14-T008 deviation. The budget gate must count the submit. Capture an auditable run record under docs/evidence/m15/T007/live-run.md (mirror M14-T008's shape: goal, pushes, submits, scores, audit-row refs, findings).
No code changes — bugs found are fixed in the owning task. If the screen lands in scenario-4 / over-budget / ambiguous-rules, pause and hand back to the human per ADR-0021.
```

---

## Loop Prompt 8 — M15-T008 regression tests + exit criteria + final review

```
/goal Execute M15-T008 regression tests + exit criteria validation + docs/milestones/m15/final-review.md until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m15/M15-T008-m15-exit-criteria.md

Read also (background context):
- all M15 closeouts (T000–T007)
- docs/milestones/m14/final-review.md + docs/milestones/m14/handoff.md (layout precedents)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill
- docs/milestone-loop-protocol.md §5 (source-of-truth update rule)
- PROJECT_STATE.md ("Current milestone" + ADR-0018 follow-up sections to update)

Mission:
Add tests/test_m15_*.py covering:
  - refresh-rules port: auto-ingest on the new surface + degradation preserved (T001)
  - push → submit → score with submit mocked, incl. autonomy-screen branch + budget-gate counts-the-submit (T002)
  - submission_format validate-on-read: valid + invalid + permissive fallback per type (T003)
  - approved_by_user_id populate + NULL-tolerant resolver (T004)
  - profile_fallback event once per fallback per job (T005)
Run the milestone validation matrix, then `milestone-final-review` writes docs/milestones/m15/final-review.md mirroring the M14 layout. Write docs/milestones/m15/handoff.md for M16 (carry deferrals #21/#85 quota pool, #83 GPU, the auth.users FK finalisation). Update PROJECT_STATE / README / milestones per protocol §5. `worktree-milestone-pr` commits per-loop-prompt, pushes the worktree branch, and opens the final M15 PR against `main`.
```

---

## GitHub issue / label workflow for M15

| Task | Issue | Labels at file time |
|---|---|---|
| M15-T000 | (new — `arch:`) | `type:feature ai:ready area:agent-sdk area:kaggle priority:P1` |
| M15-T001 | #78 | `type:bug ai:ready area:kaggle priority:P2` |
| M15-T002 | #77 | `type:feature ai:ready area:agent-sdk area:kaggle priority:P1` |
| M15-T003 | #59 | `type:feature ai:ready area:supabase area:worker priority:P2` |
| M15-T004 | #60 | `type:feature ai:ready area:supabase priority:P1` |
| M15-T005 | #61 | `type:feature ai:ready area:worker priority:P2` |
| M15-T006 | #64 | `type:cleanup ai:ready area:supabase priority:P2` |
| M15-T007 | #77 (validation) | `type:feature ai:ready policy:autonomy-screened area:kaggle priority:P1` |
| M15-T008 | (new — test-gap / release) | `type:test-gap ai:ready area:testing area:release area:docs priority:P1` |

T007 runs real Kaggle pushes + submits under the **ADR-0021 autonomy screen**
(autonomous when the competition's `kca-<slug>.yaml:autonomy.enabled` is true and
`autonomy.screen` passes; the intended-submission summary is recorded to
`.agent/kca/audit.jsonl` rather than asked). Scenario-4 / over-budget /
ambiguous-rules remain human-gated.

---

## Approval gates (summary)

| Gate | When it fires | Where approval / audit is recorded |
|---|---|---|
| `kernel_push` (per push) | Each Kaggle push in T007 | reviewer gate writes `agent_reviews` + `human_decisions`; under autonomy, screened per ADR-0021 |
| `competition_submit` (NEW) | The explicit submit in T002/T007 | **screened-autonomous** under ADR-0021 — intended-submission summary → `.agent/kca/audit.jsonl`; asks only when autonomy disabled or screen fails |
| scenario-4 / over-budget / ambiguous-rules | T007 autonomy screen hits a human-gated branch | `human_decisions` row + hand back to human (ADR-0021) |

The explicit `competition_submit` step is the visible new surface this milestone
introduces; its autonomy wiring is the headline behaviour change.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m15_*.py`.
- `ruff check .` and `ruff format --check .` — clean.
- `kca competition refresh-rules --slug <slug>` auto-ingests limits on kaggle
  2.0.x (mocked test in T001; one live refresh in T007).
- push → submit → score with the submit mocked is asserted in T002 tests, incl.
  the autonomy-screen branch and the budget-gate counting the submit.
- submission_format validate-on-read covers valid + invalid + permissive
  fallback per type (T003 tests).
- `approved_by_user_id` populate path + NULL-tolerant resolver (T004 tests).
- `profile_fallback` event emitted once per fallback per job (T005 test).
- T007's run record links the `goals.id`, the `submissions.id`, the
  `.agent/kca/audit.jsonl` intended-submission row, and the real `public_lb_score`.
- `docs/milestones/m15/final-review.md` exists and follows the M14 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any of
these is true:

- The Discovery / Debate Gate (T000) flags a load-bearing requirement the
  ADR-0020 addendum does not address. Fix the addendum; do not skip.
- A real Kaggle push or submit in T007 returns an error (rate limit, bad
  metadata, rules violation). Fix path is in the owning task; re-screen; do NOT
  silently retry.
- The autonomy screen permits a submit that violates Kaggle's actual daily limit
  (caught by Kaggle 429 / 400). Halt T002/T007 and fix `_check_budget_gates`
  before any further submit.
- The autonomy screen lands in scenario-4 / over-budget / ambiguous-rules and
  the human gate is bypassed. Halt and fix the screen wiring.
- Migration 0012 fails to apply against cloud Supabase. Halt T004; do not
  hand-edit the cloud schema out-of-band.
- The DSN, credentials, or `.env*` are accidentally printed in any log, audit
  row, PR, or evidence doc. Stop and rotate the credential.

If M15 needs a new architectural decision (e.g. cross-account quota pooling —
#21/#85 — or cheaper-GPU compute — #83), **pause and ask** — those are M16
decisions (`decision:needed`), not M15 expansion. Open an ADR draft and stop
the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN comes from .vscode/.env auto-load (cloud Supabase pooler); no need
# to export SUPABASE_DB_URL manually.

# Kaggle credentials — already in .vscode/.env.harry (single-user dev) or
# in ~/.kaggle/kaggle.json. Verify with kca kaggle list --json before T007.

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M15-T000 from docs/milestones/m15/loop-prompts.md."
# ...repeat for M15-T001 … M15-T008.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M15 — write docs/milestones/m15/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls and the live Kaggle CLI calls in T007 need
`dangerouslyDisableSandbox=true` (cloud Supabase pooler + `kaggle.com`).

---

## Human decisions needed before starting M15

These should be confirmed on the canonical M15 proposal issue (or T000's ADR
addendum) before implementation begins:

1. **Submit mechanism.** Output-CSV `kaggle competitions submit` vs the kernel
   "Submit to Competition" action. T000 ADR addendum decides; depends partly on
   whether the target competition is code-only.
2. **Autonomy default for the target competition.** `kca-<slug>.yaml:autonomy.enabled`
   true (screened-autonomous submit) vs false (ask each submit) for the T007
   surface. Default proposed: enabled, per ADR-0021.
3. **`approved_by_user_id` FK target.** Interim NULL (no FK) until Supabase auth
   (`auth.users`) lands vs a placeholder identity table now. Default proposed:
   NULL + documented gap (issue #60).
4. **#64 path.** (a) retire local Docker vs (b) re-apply migrations to local +
   CI parity check. Recommendation: (a), per issue #64.
5. **Worktree.** Per-milestone worktree per `docs/milestone-loop-protocol.md`
   §5. Confirmed by precedent.
