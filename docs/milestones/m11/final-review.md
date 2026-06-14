# M11 / authorized CTF / lab workflow — final integration review

_Branch: `worktree-m11-execution`._
_Date: 2026-06-09._

## Milestone exit (per docs/milestones/README.md M11)

> Support CTF-style challenges only inside explicit authorization boundaries.
> Challenge scope and authorization metadata; local container/lab-only execution;
> solver script generation and testing; writeup generation; hard policy blocks
> for external scanning, real targets, credential theft, persistence, or unsafe
> actions. CTF workflow is useful for local/sandbox labs and safely refuses
> out-of-scope activity.

**Status: PARTIAL (T007 deferred — single live submission pending human action).**
T000–T006 and T008 (12 of 13 Loop Prompts excluding T007) all closed PASS.
T007 (one real flag submission to a live CTFtime event) halted cleanly without
attempting any submission: all five pre-conditions failed in the autonomous run
(no `KCA_ALLOW_REMOTE`, no `~/.ctf/<slug>.json`, no live event/scope row, gh CLI
hook-denied so closing-issue verification impossible, no live flag recovered).
DB-bearing validation ran against the cloud Supabase DSN (`.vscode/.env`) under
`dangerouslyDisableSandbox=true`. All other checks ran inside the sandbox.
No production data touched. No flag values, credentials, or `~/.ctf/*` contents
appear in any commit, PR body, or new doc.

## Validation matrix

| #  | Check | Result | Notes |
|----|-------|--------|-------|
| 1  | T000 — `docs/evidence/m11/discovery/legacy-archaeologist.md` exists with byte-checkable acceptance line | PASS | File exists; ends with "Output MUST cover all 10 sections; ≥5 distinct legacy behavior dimensions must be named explicitly, including any multi-account / owner / env mapping". 10 legacy dimensions named including `ctf_scopes`, `safety-guard`, `ctf-sandbox`, reviewer.py, ADR-0005. |
| 2  | T000 — `docs/evidence/m11/discovery/requirements-skeptic.md` exists with byte-checkable acceptance line | PASS | File exists; ends with "Output MUST contain ≥5 questions spread across ≥3 categories, and an `explicit_unknowns:` section listing things the agent could not answer without human input." ≥5 questions across hidden_constraints / multi-event-identity / scope-shape / rate-limit / credential-owner categories. |
| 3  | T000 — `docs/evidence/m11/discovery/design-red-team.md` exists with byte-checkable acceptance line | PASS | File exists; ends with "Output MUST include ≥3 alternatives, ≥1 dropped capability with file:line evidence, all four long-term-cost axes, and ≥1 actionable `open_disagreements` entry." ≥3 alternatives present; subprocess isolation as dropped alternative (file:line from kkr.py replay); 4 cost axes; httpx-interceptor open disagreement. |
| 4  | T001 — Migration `0008_m11_ctf.sql` present; 4 `ctf_*` tables applied to cloud | PASS | `supabase/migrations/0008_m11_ctf.sql` committed; cloud DB seeded: `ctf_events`, `ctf_challenges`, `ctf_attempts` (+ pre-existing `ctf_scopes`). `test_m11_db.py` 13/13 PASS against cloud. |
| 5  | T001 — `src/db/ctf.py` helpers callable; ADR-0016 present | PASS | `src/db/ctf.py` with `register_event`, `add_challenge`, `get_challenge`, `list_events`, `record_attempt`, `set_scope_for_challenge` helpers. `docs/adr/0016-ctf-data-model.md` present; status: Accepted. Multi-account columns (`event_account`, `team_id`) on `ctf_attempts` folded in per T000 debate. |
| 6  | T002 — Three new approval ops in all 3 permission profiles; reviewer-gate fires | PASS | `challenge_run`, `flag_submit`, `network_egress` in `.kca/permissions/{default,permissive-dev,competition-runner}.yaml`; `src/worker/reviewer.py::should_consult_reviewer` extended; `src/worker/worker.py::_tool_call` emits `target_op`; `.claude/settings.json` ask-list includes `kca ctf flag submit*`; `.claude/hooks/guard_tool.py` covers `~/.ctf/*.json`. ADR-0017 present; enforcement-layer pinning: reviewer-gate primary, hook secondary, httpx-interceptor deferred. |
| 7  | T002 — `tests/test_reviewer_m11.py` 32/32 PASS | PASS | 32 tests covering policy default_decision for all three ops across all three profiles, audit_required flag, conditional_allow shape, and target_op resolution (10 `resolve_target_op` cases). 32/32 PASS in 0.04s (sandbox-mode). |
| 8  | T003 — `kca ctf` CLI covers all 5 sub-namespaces (event/challenge/scope/solver/flag) | PASS | `tools/kca/ctf.py` 12 subcommands: `event {register,list,info}`, `challenge {add,fetch,list,info}`, `scope {set,list,verify}`, `solver run [--dry-run]`, `flag submit [--dry-run]`. Registered in `tools/kca/agent/command_registry.py`. `tools/kca/COMMANDS.md` updated. |
| 9  | T003 — `tests/test_kca_ctf_cli.py` 29/29 PASS | PASS | 29 CLI tests covering all subcommands, `--dry-run` paths, credential-gate refusal (no creds present), flag not echoed to stdout. 29/29 PASS in 1.74s (sandbox-mode). |
| 10 | T004 — Frozen past-event bundle (1 web + 1 crypto) under `data/ctf/`; licensing documented | PASS | `data/ctf/kca-fixtures-2026/{web-1-cookie-monster,crypto-1-tiny-rsa}/` committed; bespoke CC0-1.0 + MIT in-house fixtures (not picoCTF). Attribution + license in `data/ctf/README.md`. Event inserted to cloud: `event_id=26fc7fb2-b84d-498b-af0d-f69956d8beb2`. `data/ctf/kca-fixtures-2026/web-1-cookie-monster/attachments/` (Dockerfile + app.py) committed under 1MB cap. |
| 11 | T004 — Licensing brief present; 0 flag-value leaks in any committed file | PASS | `docs/evidence/m11/T004-licensing-brief.md` present. `git grep -i "kca{" -- .` returns 0 hits across all tracked files. |
| 12 | T005 — Agent solved both fixtures locally; 2 `ctf_attempts` rows with `accepted=true` | PASS | Web: `flag_length=21`, sha256-verified; crypto: `flag_length=17`, sha256-verified. Both `ctf_attempts` rows have `accepted=true`. 2 `experiment_runs` rows recorded via `kca run init` + `kca run record-metric --key flag_length`. Docker used for web; in-process for crypto; docker cleaned up. 0 flag leaks. |
| 13 | T005 — 0 flag values in any audit / DB row / stdout | PASS | `flag_length` (integer) stored; flag string never passed to `record_attempt`. Stdout shows only `flag_length=N`. Note: pre-existing T004 fixture-authoring trail at `.agent/audit/tool-events.jsonl` (15:19/15:20) contains the deterministic crypto flag — filed as M11 follow-up C. |
| 14 | T006 — Reviewer-gate round-trip for `challenge_run` (`agent_reviews` + `human_decisions` rows) | PASS | `challenge_run` approve round-trip recorded in cloud: `agent_reviews` row written; `human_decisions.verdict=approve`; `m11_t006_reviewer_gate.py` driver script (scripts/). |
| 15 | T006 — Reviewer-gate round-trip for `flag_submit` (LOCAL_WRITE path) | PASS | `flag_submit` approve round-trip recorded in cloud: `agent_reviews` row written; `http_status=null` (LOCAL_WRITE); `human_decisions.verdict=approve`. |
| 16 | T006 — Refusal smoke: `network_egress` DENY for `kaggle.com` from CTF job context | PASS | `kaggle.com` POST from a CTF job context recorded as `agent_reviews.verdict=reject` (network_egress deny). Smoke test `test_network_egress_denied_to_kaggle_from_ctf_job` PASS in `test_m11_e2e.py`. |
| 17 | T006 — Follow-ups documented | PASS (deviation noted) | (1) cloud `agent_jobs.competition_id` schema drift bypassed in driver (`_db.create_job()` skipped); filed as M11 follow-up A. (2) `kca ctf flag submit` non-dry-run does env-check before reviewer-gate; filed as M11 follow-up B. |
| 18 | T007 — ONE real flag submission with `ctf_attempts` row | SKIP-BLOCKED | All 5 pre-conditions failed in the autonomous run: no `KCA_ALLOW_REMOTE`, no `~/.ctf/<slug>.json`, no live event/scope row, gh CLI hook-denied (closing-issue verification impossible), no live flag recovered. Halted cleanly without any network call. Pending human action (see T007 punch list below). |
| 19 | T008 — `tests/test_m11_e2e.py` 8/8 PASS (5 required + 3 hygiene additions) | PASS | 8 tests: (a) `flag_submit` refused without approval, (b) `challenge_run` refused for out-of-scope URL, (b2) scope-expiry refusal, (c) `network_egress` denied for kaggle.com from CTF job, (d) bundled web+crypto solver round-trip local, (e) 0 secret leak in test stdout, (f) audit-grep helper self-test, (g) 0 real network calls. 8/8 PASS in 0.27s. |
| 20 | T008 — `tests/test_m11_smoke.py` 7/7 SKIP cleanly without DSN | PASS | 7 DB-gated assertions SKIP when `SUPABASE_DB_URL=""` (verified with `SUPABASE_DB_URL="" pytest tests/test_m11_smoke.py`). With DSN: 7/7 PASS against cloud (dangerouslyDisableSandbox). |
| 21 | T008 — Full test suite 0 failures; ruff clean | PASS | `python -m pytest tests/` in sandbox-mode: 168 passed / 19 errors (all errors are DB-connection errors for tests decorated `@requires_db` that try to connect to unreachable local Supabase container — not M11 regressions; pre-existing pattern). `ruff check . && ruff format --check .` both clean on 87 files. |
| 22 | T009 — `docs/architecture/m11-ctf-workflow.md` present (7 sections) | PASS | Written as part of T009. Sections: 1. Calendar discovery + event registration, 2. Credential file shape + load path, 3. Challenge inventory + category triage, 4. Solver execution under `challenge_run` gate, 5. Flag recovery + sha256 verification, 6. Flag submission under `flag_submit` gate, 7. Out-of-scope follow-ups. |
| 23 | T009 — ADR-0016 + ADR-0017 present | PASS | `docs/adr/0016-ctf-data-model.md` (status: Accepted, M11-T001). `docs/adr/0017-ctf-approval-gates.md` (status: Accepted, M11-T002). Both cross-link to discovery evidence. |
| 24 | Audit-grep: 0 flag / credential / `~/.ctf/*` leaks in any new file | PASS | `git grep -i "kca{" -- .` → 0 hits. No `~/.ctf/` paths in any committed file. No token / password values in any doc, PR body, or commit message. |

**Tally: 23 PASS / 1 SKIP-BLOCKED (T007) / 0 FAIL.**

## T007 unblock punch list

T007 (ONE real flag submission to a live CTFtime-listed event) requires all of
the following human actions before the autonomous runner can proceed:

1. Set `KCA_ALLOW_REMOTE=1` in the session environment.
2. Register on a CTFtime-listed event (human action on the event site).
3. Populate `~/.ctf/<event-slug>.json` with `{"username": "...", "token": "..."}`.
4. Run `kca ctf event register --slug <event-slug> ...` to insert the live event row.
5. Run `kca ctf scope set --event <event-slug> ...` with a `target_urls` entry covering the event's flag-submit API endpoint.
6. Comment "approved to submit" on the T007 closing GitHub issue; a human must also add `decision:confirmed` and `ai:ready` labels (triage agent is blocked by the gh CLI hook).
7. Recover the flag for the chosen challenge via the T005/T006 solver loop under the live event's `challenge_run` approval.
8. Re-run M11-T007 Loop Prompt with these pre-conditions satisfied.

## DB access note

DB validation ran against the cloud Supabase DSN stored in `.vscode/.env`.
The DSN is NOT printed in this document. Calls that needed `dangerouslyDisableSandbox=true`:

- `kca ctf event register`, `kca ctf challenge add`, `kca ctf scope set` (LOCAL_WRITE against cloud).
- `scripts/m11_t006_reviewer_gate.py` (reads and writes `agent_reviews` + `human_decisions`).
- `python -m pytest tests/test_m11_db.py tests/test_m11_smoke.py` (DB-gated assertions).

Sandbox-mode checks (no `dangerouslyDisableSandbox`):

- `tests/test_m11_e2e.py` — 8 tests, 0 DB, 0 net, 0 creds.
- `tests/test_kca_ctf_cli.py` — 29 tests, 0 DB, 0 net.
- `tests/test_reviewer_m11.py` — 32 tests, 0 DB, 0 net.

Container IP note: the local Supabase container (`172.21.0.4`) was not reachable
during this T009 sandbox-mode run (DB-gated tests ERROR on connection). The cloud
DSN was used for all DB verification as stated in the loop prompt.

## What landed

### M11-T000 — Discovery / Debate Gate

- `docs/evidence/m11/discovery/legacy-archaeologist.md` — 10-section report on pre-M11 CTF artefacts; surfaces multi-account, `ctf_scopes`, `safety-guard`, `reviewer.py`, and ADR-0005 as key legacy dimensions.
- `docs/evidence/m11/discovery/requirements-skeptic.md` — ≥5 questions across ≥3 categories; `explicit_unknowns` section covering scope-shape, rate-limit, credential-owner pairing, frozen-bundle license.
- `docs/evidence/m11/discovery/design-red-team.md` — ≥3 alternatives (subprocess isolation, in-process credential read, scope-wildcard); dropped subprocess isolation with file:line evidence; httpx-interceptor as open disagreement.

### M11-T001 — CTF schema + DB layer

- `supabase/migrations/0008_m11_ctf.sql` — `ctf_events`, `ctf_challenges`, `ctf_attempts` tables; FKs to `projects` + `ctf_scopes`; RLS enabled. Multi-account columns (`event_account`, `team_id`) on `ctf_attempts`.
- `src/db/ctf.py` — 6 helpers: `register_event`, `add_challenge`, `get_challenge`, `list_events`, `record_attempt`, `set_scope_for_challenge`.
- `docs/adr/0016-ctf-data-model.md` — table shape, multi-event identity, retention policy for failed attempts.

### M11-T002 — Approval gates

- `.kca/permissions/{default,permissive-dev,competition-runner}.yaml` — `challenge_run`, `flag_submit`, `network_egress` ops added to all three profiles.
- `src/worker/reviewer.py` — `should_consult_reviewer` extended for the three new ops.
- `src/worker/worker.py` — `_tool_call` emits `target_op` for the new ops.
- `.claude/settings.json` — `kca ctf flag submit*` added to ask-list.
- `.claude/hooks/guard_tool.py` — `~/.ctf/*.json` reads denied outside the `kca ctf` allow-list.
- `docs/adr/0017-ctf-approval-gates.md` — enforcement-layer pinning: reviewer-gate primary, hook secondary, httpx-interceptor deferred to follow-up F.

### M11-T003 — `kca ctf` CLI surface

- `tools/kca/ctf.py` — 12 subcommands across 5 namespaces (event/challenge/scope/solver/flag). Credential-gate + reviewer-gate + `flag_length`-not-value hygiene throughout.
- `tools/kca/agent/command_registry.py` — `ctf` subparser registered.
- `tools/kca/COMMANDS.md` — `kca ctf` surface documented.

### M11-T004 — Frozen past-event bundle

- `data/ctf/kca-fixtures-2026/web-1-cookie-monster/` — Flask cookie-tamper web challenge (CC0-1.0): `challenge.yaml`, `description.md`, `docker-compose.yml`, `attachments/{Dockerfile,app.py}`, `solver_template.py`, `expected.sha256`.
- `data/ctf/kca-fixtures-2026/crypto-1-tiny-rsa/` — Tiny RSA crypto challenge (MIT): `challenge.yaml`, `description.md`, `attachments/params.json`, `solver_template.py`, `expected.sha256`.
- `data/ctf/README.md` — source attribution + license.
- `docs/evidence/m11/T004-licensing-brief.md` — research-brief confirming license terms.
- Cloud DB: event `kca-fixtures-2026` (`event_id=26fc7fb2-b84d-498b-af0d-f69956d8beb2`) + 2 challenges + 2 scope rows inserted.

### M11-T005 — Local solve loop

- `scripts/m11_t005_solve_bundled.py` — harness driving both challenge solvers; web: docker-compose + httpx; crypto: in-process; records `ctf_attempts` + `experiment_runs` with `flag_length` only. 0 flag leaks.
- Cloud DB: 2 `ctf_attempts` rows (`accepted=true`): web `flag_length=21`, crypto `flag_length=17`, both sha256-verified.

### M11-T006 — Reviewer gate

- `scripts/m11_t006_reviewer_gate.py` — drives `challenge_run` approve round-trip and `flag_submit` approve round-trip (LOCAL_WRITE); `kaggle.com` network_egress reject smoke.
- Cloud DB: `agent_reviews` rows for `challenge_run`, `flag_submit` (approve), `network_egress` (reject); `human_decisions` rows for the two approvals.

### M11-T007 — Live flag submission

- SKIP-BLOCKED. No rows written. No network calls. No credentials used. Halted cleanly.

### M11-T008 — E2E and smoke tests

- `tests/test_m11_e2e.py` — 8 tests (513 lines); 8/8 PASS in 0.27s (sandbox-mode, 0 net / 0 DB / 0 creds).
- `tests/test_m11_smoke.py` — 7 DB-gated assertions (320 lines); 7/7 SKIP without DSN; 7/7 PASS with cloud DSN.
- `tests/test_m11_db.py` — 13 unit tests for DB helpers (411 lines); SKIP without DSN; 13/13 PASS with cloud DSN.
- `tests/test_reviewer_m11.py` — 32 policy tests (no DB/net); 32/32 PASS.
- `tests/test_kca_ctf_cli.py` — 29 CLI tests (no DB/net); 29/29 PASS.
- `tests/_audit_grep.py` — shared audit-grep helper used by `test_m11_e2e.py`.

### M11-T009 — Final review + docs

- `docs/milestones/m11/final-review.md` — this document.
- `docs/architecture/m11-ctf-workflow.md` — 7-section CTF workflow architecture doc.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md` — updated to M11 partial state.
- `docs/milestones/m11/handoff.md` — M11 → M12 handoff.

## M12 follow-ups

The following cross-cutting items surfaced during M11 and should be filed as
GitHub issues for resolution before or during M12 / M13:

1. **A. `agent_jobs.competition_id` schema drift** — T006 driver bypassed `_db.create_job()` because the cloud `agent_jobs.competition_id` column is missing (schema drift). Labels: `type:bug`, `area:supabase`, `priority:P2`.
2. **B. `kca ctf flag submit` non-dry-run does env-check before reviewer-gate** — the credential presence check fires before the `should_consult_reviewer` path, meaning a missing credential causes a confusing pre-gate failure rather than a gate-then-credential flow. Labels: `type:bug`, `area:cli`, `area:security`, `priority:P1`.
3. **C. T004 fixture-authoring trail at `.agent/audit/tool-events.jsonl`** — timestamps 15:19/15:20 contain the deterministic crypto flag (the flag is mathematically determined by `params.json`, so this is reproducible; but the audit trail should not persist flag values). Labels: `type:security`, `area:testing`, `priority:P1`.
4. **D. `expected.sha256` web-1 churn** — `web-1-cookie-monster/expected.sha256` is regenerated on each solve run (the harness generates a fresh flag each time). The file is committed between runs, leading to dirty-worktree after T005. A more stable design would fix the web flag in the fixture. Labels: `type:test-gap`, `area:ctf`, `priority:P2`.
5. **E. gh CLI hook denial blocks `decision:confirmed` verification** — the gh CLI hook denies reads of issue labels in several T000/T007/T008 verification steps, forcing manual confirmation. Broaden the hook or provide an out-of-band verification path. Labels: `type:bug`, `area:security`, `area:ci`, `priority:P2`.
6. **F. httpx-level `network_egress` interceptor for subprocess egress** — ADR-0017 §enforcement-layer-pinning deferred the httpx-level interceptor that would catch solver subprocess calls bypassing the reviewer-gate. Labels: `type:feature`, `area:security`, `area:worker`, `priority:P1`.
7. **G. Per-challenge rate-limit as a `ctf_scopes` column** — T000 design-red-team carry-over. Add `rate_limit_per_hour integer` to `ctf_scopes`; guard in `cmd_flag_submit`. Labels: `type:feature`, `area:ctf`, `priority:P3`.
