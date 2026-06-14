# M11 → M12 Handoff Prompt

_Generated 2026-06-09 from `docs/milestones/m11/final-review.md` and `docs/milestones/README.md` §M11._
_M11 status: PARTIAL — T000–T006 + T008 done; T007 deferred pending human-supplied live-event credentials + approval comment._

Paste this into a fresh session that is starting **M12 (Devpost / hackathon workflow)**
or picking up **M11-T007 (one real live CTF flag submission)** after the human has
satisfied the pre-conditions listed below.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M9 and M11 (partial) are complete.** Your job is to start **M12**
(Devpost / hackathon workflow) or to unblock and re-run **M11-T007**
(ONE real flag submission to a live CTFtime event).

M11 shipped the first CTF / authorized-lab regression for this platform:
`ctf_events`, `ctf_challenges`, `ctf_attempts` DB tables, `src/db/ctf.py`
helpers, `tools/kca/ctf.py` (12 subcommands), frozen in-house challenge
fixtures (`web-1-cookie-monster` Flask cookie-tamper + `crypto-1-tiny-rsa`
RSA), ADR-0016 + ADR-0017, three new approval gates (`challenge_run`,
`flag_submit`, `network_egress`), and a full e2e test suite (8 e2e / 7
smoke / 13 DB / 32 policy / 29 CLI tests). The only deferred item is
T007: the ONE real live flag submission, blocked on human-supplied
credentials and `decision:confirmed` on the closing issue.

## Read these files first

1. `PROJECT_STATE.md` — current state at M11 partial exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions.
4. `docs/milestones/README.md` — M11 (partial landed deliverables + follow-up list) + M12 section.
5. `docs/milestones/m11/final-review.md` — 23 PASS / 1 SKIP-BLOCKED / 0 FAIL validation matrix; all seven M11 follow-ups A–G.
6. `docs/architecture/m11-ctf-workflow.md` — 7-section CTF workflow architecture.
7. `docs/adr/0016-ctf-data-model.md` — CTF DB table shape.
8. `docs/adr/0017-ctf-approval-gates.md` — `challenge_run` / `flag_submit` / `network_egress` ops + enforcement-layer pinning.
9. `docs/engineering-practice.md` — the GitHub interface model.
10. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
11. `docs/milestones/m12/loop-prompts.md` (if it exists) — M12 planning loop prompts.

## State at M11 exit (partial)

### Passed tasks (T000–T006, T008)

- **T000** — 3 Discovery / Debate Gate reports at `docs/evidence/m11/discovery/`. Byte-checkable acceptance lines present.
- **T001** — `supabase/migrations/0008_m11_ctf.sql` applied to cloud; 4 ctf_* tables; `src/db/ctf.py` 6 helpers; ADR-0016.
- **T002** — `challenge_run` / `flag_submit` / `network_egress` in all 3 permission profiles; reviewer.py + worker.py + settings.json + guard_tool.py wired; ADR-0017 with enforcement-layer pinning.
- **T003** — `tools/kca/ctf.py` 12 subcommands; command_registry registered; COMMANDS.md docs; 29/29 CLI tests.
- **T004** — Bespoke CC0-1.0 + MIT in-house fixtures under `data/ctf/kca-fixtures-2026/` (1 web Flask cookie-tamper + 1 crypto tiny RSA); event/challenges/scopes in cloud; `event_id=26fc7fb2-b84d-498b-af0d-f69956d8beb2`; 0 flag-value leaks.
- **T005** — Agent solved both fixtures locally: web `flag_length=21`, crypto `flag_length=17`, both sha256-verified; 2 `ctf_attempts(accepted=true)` + 2 `experiment_runs` in cloud; docker cleaned; 0 flag leaks.
- **T006** — `challenge_run` approve round-trip + `flag_submit` approve round-trip (LOCAL_WRITE) + `kaggle.com` `network_egress` reject smoke recorded in cloud. Follow-ups: (1) `agent_jobs.competition_id` schema drift bypassed in driver (follow-up A); (2) `kca ctf flag submit` non-dry-run does env-check before reviewer-gate (follow-up B).
- **T008** — 8/8 e2e + 7/7 smoke (SKIP without DSN) + 13/13 DB + 32/32 reviewer + 29/29 CLI; 169 total tests / 0 failures; ruff clean; in-process-only test pattern eliminates credential leak.

### Deferred task (T007)

**T007 SKIP-BLOCKED** — all 5 pre-conditions failed in the autonomous run:
no `KCA_ALLOW_REMOTE`, no `~/.ctf/<slug>.json`, no live event/scope row,
gh CLI hook-denied so closing-issue verification was impossible, no live
flag recovered. Halted cleanly without attempting any submission.

### T007 unblock punch list (human action required)

1. Set `KCA_ALLOW_REMOTE=1` in the session environment.
2. Register on a live CTFtime event (human action on the event site).
3. Populate `~/.ctf/<event-slug>.json` with `{"username": "...", "token": "..."}`.
4. Run `kca ctf event register --slug <event-slug> ...` to insert the live event row.
5. Run `kca ctf scope set --event <event-slug> ...` with `target_urls` covering the submit endpoint.
6. Comment "approved to submit" on the T007 closing GitHub issue; add `decision:confirmed` + `ai:ready` labels manually (gh CLI hook denies automated label changes — see follow-up E).
7. Recover the flag for the chosen challenge via the local T005/T006 solver loop (or against the live challenge endpoint under a separate `challenge_run` approval).
8. Re-run M11-T007 Loop Prompt from `docs/milestones/m11/loop-prompts.md`.

### Test posture at M11 partial exit

- Sandbox-mode pytest: 168 passed / 19 errors (all errors are DB-connection errors for `@requires_db` decorated tests connecting to the unreachable local container — expected in sandbox).
- `SUPABASE_DB_URL="" pytest tests/test_m11_smoke.py` → 7/7 SKIP (correct).
- Cloud DB pytest (dangerouslyDisableSandbox): 13/13 DB tests, 7/7 smoke tests PASS.
- `ruff check . && ruff format --check .` — clean on 87 files.

### DB state at M11 partial exit (cloud, `.vscode/.env`)

- `ctf_events`: `kca-fixtures-2026` row (`event_id=26fc7fb2-b84d-498b-af0d-f69956d8beb2`).
- `ctf_challenges`: 2 rows (web-1-cookie-monster, crypto-1-tiny-rsa).
- `ctf_scopes`: 2 rows (ctf-local-kca-fixtures-2026-web-1, ctf-local-kca-fixtures-2026-crypto-1).
- `ctf_attempts`: 2 rows from T005 (`accepted=true`, `flag_length` 21 + 17); T006 flag_submit attempt (`accepted=true`, `http_status=null`).
- `agent_reviews`: `challenge_run` (approve) + `flag_submit` (approve) + `network_egress` (reject) rows from T006.
- `human_decisions`: 2 rows for the T006 approve round-trips.

### New artifacts on disk at M11 partial exit

- `supabase/migrations/0008_m11_ctf.sql`
- `src/db/ctf.py`
- `docs/adr/0016-ctf-data-model.md`, `docs/adr/0017-ctf-approval-gates.md`
- `tools/kca/ctf.py`, `tools/kca/agent/command_registry.py` (updated), `tools/kca/COMMANDS.md` (updated)
- `data/ctf/kca-fixtures-2026/web-1-cookie-monster/{challenge.yaml,description.md,docker-compose.yml,attachments/,solver_template.py,expected.sha256}`
- `data/ctf/kca-fixtures-2026/crypto-1-tiny-rsa/{challenge.yaml,description.md,attachments/params.json,solver_template.py,expected.sha256}`
- `data/ctf/README.md`, `docs/evidence/m11/T004-licensing-brief.md`
- `docs/evidence/m11/discovery/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`
- `scripts/m11_t005_solve_bundled.py`, `scripts/m11_t006_reviewer_gate.py`
- `tests/test_m11_e2e.py`, `tests/test_m11_smoke.py`, `tests/test_m11_db.py`
- `tests/test_kca_ctf_cli.py`, `tests/test_reviewer_m11.py`, `tests/_audit_grep.py`
- `.kca/permissions/{default,permissive-dev,competition-runner}.yaml` (updated)
- `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/guard_tool.py`, `.claude/skills/ctf-sandbox/SKILL.md` (updated)
- `docs/architecture/m11-ctf-workflow.md`
- `docs/milestones/m11/final-review.md`, `docs/milestones/m11/handoff.md` (this file)
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`, `docs/tasks/README.md` (updated)

## Cross-cutting follow-ups from M11 (file as GitHub issues)

### A. `agent_jobs.competition_id` schema drift on cloud

- **Type:** bug.
- **Labels:** `type:bug`, `area:supabase`, `priority:P2`.
- **Symptom:** T006 driver bypassed `_db.create_job()` because the cloud `agent_jobs.competition_id` column is missing. Schema drift between local migration state and cloud.
- **Suggested fix:** check which migrations haven't been applied to cloud; apply idempotently.
- **Acceptance:** `_db.create_job(competition_id=<id>)` works without a column error on cloud.

### B. `kca ctf flag submit` non-dry-run does env-check before reviewer-gate

- **Type:** bug / security.
- **Labels:** `type:bug`, `area:cli`, `area:security`, `priority:P1`.
- **Symptom:** `cmd_flag_submit` in `tools/kca/ctf.py` checks for `KCA_ALLOW_REMOTE` and credential presence before calling `should_consult_reviewer`. A missing credential causes a pre-gate failure, not a gate-then-credential error. This means a misconfigured env can bypass the gate in a confusing way.
- **Suggested fix:** reorder so `should_consult_reviewer` fires first; credential check happens only after approval is granted.
- **Acceptance:** `kca ctf flag submit` without credentials still fires the reviewer-gate and only fails at the credential step after an approve verdict.

### C. T004 fixture-authoring trail contains deterministic crypto flag

- **Type:** security (low severity — flag is deterministic and reproducible from committed `params.json`, but the audit trail shouldn't persist it).
- **Labels:** `type:security`, `area:testing`, `priority:P1`.
- **Symptom:** `.agent/audit/tool-events.jsonl` timestamps 15:19/15:20 contain the deterministic crypto flag value from T004 fixture authoring. The flag is mathematically derivable from committed `params.json`, so this is a disclosure of an already-public value — but the pattern of storing flag values in audit trails must be addressed.
- **Suggested fix:** add flag-pattern scrubbing to the audit JSONL writer (same pattern as `response_excerpt` scrubbing in `record_attempt`).
- **Acceptance:** `grep -r "kca{" .agent/` returns 0 hits after re-running T004.

### D. `expected.sha256` web-1 churn

- **Type:** test-gap.
- **Labels:** `type:test-gap`, `area:ctf`, `priority:P2`.
- **Symptom:** `data/ctf/kca-fixtures-2026/web-1-cookie-monster/expected.sha256` is regenerated on every solve run (the harness generates a fresh flag each time). The file is committed, so each T005 run leaves a dirty worktree.
- **Suggested fix:** fix the web flag in the fixture (e.g., as a hex secret in `.env.test`); or document that the harness always owns the web flag and the committed `expected.sha256` is a placeholder (`<harness-generated>`).
- **Acceptance:** `git status` shows no dirty `expected.sha256` after running `m11_t005_solve_bundled.py`.

### E. gh CLI hook denial blocks `decision:confirmed` verification

- **Type:** bug / usability.
- **Labels:** `type:bug`, `area:security`, `area:ci`, `priority:P2`.
- **Symptom:** The `.claude/hooks/guard_tool.py` hook denies `gh issue view`, `gh issue edit`, and `gh pr create` for label-inspection / label-set operations in T000, T007, and T008, forcing manual out-of-band verification.
- **Suggested fix:** add a read-only `gh issue view` allow to the hook; or document an out-of-band verification path (e.g., checking `gh issue view --json labels` without the hook).
- **Acceptance:** `gh issue view <N> --json state,labels` works in the agent session without a hook denial.

### F. httpx-level `network_egress` interceptor for subprocess egress (ADR-0017 deferred)

- **Type:** feature / security.
- **Labels:** `type:feature`, `area:security`, `area:worker`, `priority:P1`.
- **Symptom:** The reviewer-gate and hook cover direct worker HTTP calls. A solver subprocess that shells out to `curl` or uses `urllib` can bypass the gate entirely. ADR-0017 §enforcement-layer-pinning records this explicitly as deferred.
- **Suggested fix:** add an httpx-monkey-patch or a subprocess env injector (`http_proxy=block://`) that captures and audits subprocess HTTP calls.
- **Acceptance:** a test that asserts a subprocess `curl` call from a CTF job context is caught and denied at the `network_egress` gate.

### G. Per-challenge rate-limit column on `ctf_scopes`

- **Type:** feature.
- **Labels:** `type:feature`, `area:ctf`, `priority:P3`.
- **Symptom:** T000 design-red-team raised the question of per-challenge rate-limiting. No `rate_limit_per_hour` column exists on `ctf_scopes`.
- **Suggested fix:** migration 0009 adding `rate_limit_per_hour integer null`; guard in `cmd_flag_submit` that checks the rate limit before attempting a submission.
- **Acceptance:** `kca ctf scope set --rate-limit 5` sets the column; `cmd_flag_submit` respects it.

## Cross-cutting follow-ups carried forward from M9

- **M9-A** — `competitions.repo_url` schema drift (`area:kaggle`, `type:bug`). See `docs/milestones/m9/handoff.md §A`.
- **M9-B** — Secrets-file hygiene in pytest subprocess (issue #11, P0). Filed; referenced in M11-T008 soft pre-req.
- **M9-C** — `decision_api`: no `GET /decisions` endpoint (`area:supabase`, `type:feature`).
- **M9-D** — `reviewer_decision` literal event_type not emitted (`area:worker`, `type:docs`).
- **M9-E** — Migration 0004 optional columns not applied to local DB (`area:supabase`, `type:bug`).

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets, flags, credentials, or `~/.ctf/*` content.
- M11 used NO real live flag submissions (T007 deferred). Any live CTF submission needs fresh `decision:confirmed` on the closing issue plus `KCA_ALLOW_REMOTE=1` and a matching `ctf_scopes.target_urls` row.
- DB calls require `dangerouslyDisableSandbox=true` against the cloud DSN in `.vscode/.env`. Do NOT print the DSN value.
- Per-milestone worktree per `docs/milestone-loop-protocol.md` §5.

## Current task

Either:

**(a) Start M12 (Devpost / hackathon workflow).** `docs/milestones/m12/loop-prompts.md` already exists (planning landed PR #32). The first M12 task is M12-T000 (survey candidate Devpost events). Use `docs/milestones/m12/loop-prompts.md` as the entry point. Per-milestone worktree per protocol §5. Decision needed: which Devpost / hackathon event to target (picked in M12-T000 under human approval).

**(b) Resume M11-T007 (one real live flag submission).** Confirm all 5 pre-conditions above are met. Then run the M11-T007 Loop Prompt from `docs/milestones/m11/loop-prompts.md`. After T007 PASS, re-run T009 to update `docs/milestones/m11/final-review.md` from PARTIAL to `✓ done`.

**(c) File M11 follow-up issues A–G.** Use `.github/ISSUE_TEMPLATE/` to file each follow-up with the label sets listed above. Triage agent should add `ai:triage`; do not promote to `ai:ready` without AC + owner.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
