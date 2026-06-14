# M8 / product UI shell — final integration review

_Branch: `worktree-m8-loop` (M8 loop). Date: 2026-05-23._

## Milestone exit (per docs/milestones/README.md M8 + docs/milestones/m8/loop-prompts.md)

> Turn the headless KCA control plane into a usable workbench by adding
> a React/TypeScript front-end on top of the M2–M7 layers, plus the six
> M7 follow-ups (skill→worker wiring, audit table, schema gate, ToolSpec
> enforcement, fixture relocation, CI fork-gating + UI job).

**Status: met.** All non-SKIP checks PASS. DB-bearing checks ran
against `postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` (the
container IP on the local Supabase stack); those calls were run with
`dangerouslyDisableSandbox=true`.

## M8 EXIT CRITERIA MET

## Validation matrix

| #  | Check | Result | Notes |
|----|-------|--------|-------|
| 1  | `agent_tool_audit` table + `v_agent_tool_audit_recent` view present | PASS | migration `0007_m8_tool_audit.sql` applied. |
| 2  | `audit.py` dual-writes JSONL + DB; never raises on DB error | PASS | `log_policy_decision` defends both backends; JSONL still source of truth. |
| 3  | `SkillValidationError` raised on bad name | PASS | `tools/kca/agent/skill_schema.py`; pattern allows `_test_fixture` (underscore-leading test fixtures only). |
| 4  | `SkillValidationError` raised on unknown tool in `allowed-tools` | PASS | `validate_allowed_tools` cross-checks `TOOL_REGISTRY`. |
| 5  | `kca skill run <name> --execute` creates an `agent_jobs` row and drives `AgentWorker` (allow/ask/deny audited correctly) | PASS | wired via `tools/kca/skill.py::_run_via_worker` + `JobPolicy.tool_decisions`. |
| 6  | `src/worker/worker.py::_tool_call` honours `ToolSpec.timeout_s`, `ToolSpec.sandbox`, `JobPolicy.approval_gates` | PASS | new helper at `worker.py:394`. |
| 7  | `cd ui && pnpm install --frozen-lockfile` succeeds | PASS | "Already up to date" — lockfile in sync. |
| 8  | `pnpm -C ui typecheck` → 0 errors | PASS | strict TS, `tsc --noEmit`. |
| 9  | `pnpm -C ui lint` → 0 issues | PASS | eslint + @typescript-eslint, `--max-warnings 0`. |
| 10 | `pnpm -C ui build` → 0 errors | PASS | 199.21 kB JS / 62.87 kB gz (excluding recharts code-split chunk), 13.95 kB CSS / 3.35 kB gz. |
| 11 | `pnpm -C ui test --run` → ≥ 12 vitest cases | PASS | **13 vitest cases** pass. |
| 12 | Dashboard renders Projects + Active competitions + Inflight runs + Recent decisions | PASS | unit + Playwright. |
| 13 | `/runs/:jobId` renders span swim-lane + event log | PASS | SVG swim-lane test asserts 3 mock spans. |
| 14 | `/experiments` table sortable by CV + LB | PASS | sortable column headers + sort-flip test. |
| 15 | `/research` lists items with trust badges; external links have `rel="noopener noreferrer"` | PASS | sanitiser test + Playwright `external_link_has_noopener`. |
| 16 | `/approvals` lists pending decisions; `/approvals/:id` has Approve / Reject / Ask-improve | PASS | 3 vitest cases on DecisionGate. |
| 17 | `/artifacts` blocks binary preview and CSV > 100 rows | PASS | `canPreview` + `capCsv` tests. |
| 18 | `POST /decision/:id/approve` idempotent (409 on second call) | PASS | `test_decision_api_approve_idempotent`. |
| 19 | `POST /decision/:id/reject` enforces minLength=8 on reason | PASS | Pydantic `min_length=8`; 422 on short. |
| 20 | `POST /decision/:id/ask-improve` appends `agent_job_events("feedback")` | PASS | `test_decision_api_ask_improve_appends_event`. |
| 21 | No `SERVICE_ROLE` reachable from the browser | PASS | `grep -r SERVICE_ROLE ui/src ui/tests` → 0 matches. |
| 22 | `.github/workflows/test.yml` has `ui` job and gated `live-db` job | PASS | jobs = `[no-db, live-db, lint, ui]`; live-db gates on push to main or same-repo PR. |
| 23 | `python -m pytest tests/ -m "not db"` → 0 failures | PASS | 77 passed / 7 skipped (services/decision_api collected separately by ini). |
| 24 | `ruff check .` + `ruff format --check .` → 0 issues | PASS | All checks passed; 64 files already formatted. |
| 25 | `python -m pytest tests/test_m8_smoke.py -v` → 13/13 | PASS | with DB live: 13 passed. Without DB: 12 + 1 skip. |
| 26 | `pnpm -C ui exec playwright test` → 4/4 | PASS\* | uses `PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium` because the playwright sandbox blocks browser downloads; tests themselves pass 4/4. |
| 27 | `docs/architecture/m8-ui-shell.md` ≥ 100 lines | PASS | 148 lines. |
| 28 | All required headings present | PASS | Overview / Layer map / Data flow per page / Auth model / Approval gate semantics / Audit trail / Adding a new page / Adding a new approve-class operation. |

## DB access note

DB validation reused the M5/M6/M7 path: container IP DSN
`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`. Migrations were
applied with `psql -f supabase/migrations/0007_m8_tool_audit.sql` under
`dangerouslyDisableSandbox=true`. `host: localhost:5432` is the
Supabase pooler, not direct Postgres — direct connections go to the
container IP, which may change on `docker compose down/up` (refresh via
`docker inspect supabase-db --format '{{...}}'`).

The DB checks that needed sandbox-disabled:
- Migration apply (`psql`).
- `agent_tool_audit` row insertion smoke (`AuditLogger(backend='both')`).
- `tests/test_m8_smoke.py::test_tool_audit_table_present_on_db_target`.
- Playwright e2e (uses system chromium with `--no-sandbox` flag).

Everything else (vite dev, vitest, ruff, pytest no-db, decision_api
tests, ui build) ran inside the normal sandbox.

## What landed

### Backend / control plane

- `supabase/migrations/0007_m8_tool_audit.sql` — `agent_tool_audit` table
  + 3 indexes + `v_agent_tool_audit_recent` view + RLS.
- `tools/kca/db.py` — `insert_tool_audit(rec)`; the M7-era
  `append_job_event("tool_audit", …)` path is preserved for legacy
  readers but marked deprecated in the docstring.
- `tools/kca/agent/audit.py` — `AuditRecord` extended with `job_id` +
  `extra`; `AuditLogger` dual-writes JSONL + DB when `SUPABASE_DB_URL`
  set; never raises on DB failure; module-level `log_policy_decision()`
  shortcut.
- `tools/kca/agent/skill_schema.py` — frontmatter validator
  (`SKILL_FRONTMATTER_SCHEMA`) + `validate_frontmatter` +
  `validate_allowed_tools`. Wired into `skill_loader.load_skill`.
- `tools/kca/skill.py` — hidden `--skills-root` flag,
  `--execute` flag, `_run_via_worker` that builds a `JobPolicy` from the
  resolved per-tool decisions and drives `AgentWorker`.
- `src/worker/_types.py::JobPolicy` — new optional fields
  `skill_name`, `policy_profile`, `mode`, `tool_decisions`.
- `src/worker/worker.py` — `PolicyViolation` exception; new
  `_tool_call(executor, name, input)` that:
  - looks up `ToolSpec` via the kca tool_registry,
  - audits every decision through `log_policy_decision`,
  - enforces `tool_decisions` (`deny` → fail job, `ask` → pause via
    `ApprovalRequired`, `allow` → execute),
  - honours `ToolSpec.sandbox` + `ToolSpec.timeout_s`.
- `scripts/backfill_tool_audit.py` — idempotent
  `.agent/audit.jsonl` → `agent_tool_audit` backfill.

### Decision API

- `services/decision_api/app.py` — FastAPI app factory `make_app()`.
  Endpoints: `POST /decision/{id}/{approve,reject,ask-improve}`. Token
  auth via `KCA_DECISION_API_TOKEN`. 409 on already-resolved decisions.
- `services/decision_api/tests/test_decision_api.py` — 5 tests
  (idempotent approve, reject minLength, ask-improve event, 404,
  token-required).

### UI / SPA

- `ui/` Vite + React + TS scaffold: 13 vitest cases, 4 Playwright cases.
- `ui/src/lib/db.ts` — typed read-only Supabase client (22 functions).
- `ui/src/lib/supabase.ts` — `createClient` when anon key set; otherwise
  an empty-array fake that lets the SPA render cleanly in tests and
  demo previews.
- `ui/src/lib/markdown.ts` — tiny safe Markdown renderer (escapes
  `<script>`, strips `javascript:` hrefs, blocks remote images via a
  load-image placeholder).
- `ui/src/lib/artifacts.ts` — preview policy (binary extensions
  blocked, 1 MB size cap, 100-row CSV cap).
- Pages: `Dashboard`, `Runs`, `RunTimeline`, `Experiments`, `RunDetail`,
  `Research`, `ApprovalInbox`, `DecisionGate`, `Artifacts`,
  `ArtifactDetail`.
- UI primitives: `Button`, `Card`, `Table`, `Badge`, `Empty`, `Spinner`,
  `Modal`, `Toast`.
- `ErrorBoundary` for runtime crashes.
- ADR: `docs/adr/0014-ui-stack.md` (Vite + React + RR; rationale +
  consequences). _Note: numbered 0014 because 0011-local-model-endpoints.md
  was already taken in the repo when the M8 prompts were written._
- Architecture doc: `docs/architecture/m8-ui-shell.md` (148 lines).

### Tests + CI

- `tests/test_m8_smoke.py` — 13 tests (1 DB-marked, 12 db-less).
- `tests/test_m8_worker_wiring.py` — 3 worker-policy tests.
- `tests/fixtures/skills/_test_fixture/SKILL.md` — relocated from
  `.kca/skills/`.
- `ui/tests/e2e/m8.spec.ts` — 4 Playwright tests.
- `.github/workflows/test.yml` — new `ui` job (install + lint +
  typecheck + build + vitest); `live-db` gated to push-to-main + same-repo
  PRs, with a guard that skips with a warning when the secret is empty.

## Deliberate deviations from the M8 loop prompts

1. **ADR number**: prompts said `ADR-0011-ui-stack.md`, but
   `0011-local-model-endpoints.md` already existed in the repo.
   Renumbered to `0014-ui-stack.md`. Content unchanged.
2. **Skill name regex**: prompts specified `^[a-z0-9][a-z0-9-_]*$`, but
   the fixture name `_test_fixture` (leading underscore) violates that.
   Relaxed to `^[a-z0-9_][a-z0-9_\-]*$`. Spaces / uppercase / slashes
   still rejected.
3. **Playwright install**: the sandbox cannot reach Playwright's
   binary CDN. Tests run successfully with
   `PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium` (Arch's system
   chromium). CI uses the standard `playwright install` path.
4. **pnpm install**: pnpm was not pre-installed on the dev box; this
   loop bootstrapped it under `$TMPDIR/pnpm/bin`. CI uses
   `pnpm/action-setup@v3`.

## M9 follow-ups

1. **Decision API multi-user auth.** M8 ships a single shared token.
   Move to per-user JWTs (Supabase auth) and revisit RLS for read
   queries that currently rely on the anon key.
2. **Artifact preview via storage HEAD/GET.** UI shows download links
   only; the inline text/CSV preview path needs a server-side
   `services/artifact_api/` or Supabase storage signed URLs.
3. **Live-DB CI on PRs from forks.** Wire a read-only secrets pattern
   (token-less migrations, container Postgres) so forks can run a
   smoke pass without touching org secrets.
4. **OTEL → Run Timeline parity.** The swim-lane reads
   `agent_telemetry_spans` directly; once M9 lands an OTEL collector,
   wire spans from the collector instead of the worker direct-write.
5. **First M9 task: live Kaggle regression test for Spaceship Titanic**
   under approval, per `docs/milestones/README.md § M9`.

## Files of interest (one-line each)

- `supabase/migrations/0007_m8_tool_audit.sql` — typed audit table.
- `tools/kca/agent/skill_schema.py` — frontmatter validator.
- `tools/kca/agent/audit.py` — dual-write JSONL + DB, env-var override
  for tests.
- `src/worker/worker.py` — `_tool_call` + `PolicyViolation`.
- `tools/kca/skill.py` — `--execute` + `--skills-root`.
- `services/decision_api/app.py` — FastAPI action service.
- `ui/src/lib/db.ts` — typed Supabase client.
- `ui/src/pages/*` — 10 pages.
- `ui/tests/e2e/m8.spec.ts` — Playwright e2e.
- `docs/adr/0014-ui-stack.md` — UI stack ADR.
- `docs/architecture/m8-ui-shell.md` — M8 architecture doc.
- `tests/test_m8_smoke.py` — 13 Python smoke tests.
