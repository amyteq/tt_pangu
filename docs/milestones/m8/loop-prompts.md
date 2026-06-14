# M8 Loop Prompts

_Product UI shell — React/TypeScript front-end on top of the M2–M7 control plane._
_For sequential, mostly autonomous execution on Arch Linux._
_Prerequisite: M7 exit criteria confirmed met (see `docs/milestones/m7/final-review.md`)._

---

## M8 at a glance

M8 turns the headless KCA platform into a usable workbench by adding a human
interface on top of the M2 control plane, M5 research data, M6 reviewer /
telemetry data, and the M7 permission policy + audit trail.

M8 is **not** a greenfield UI experiment: it must respect every safety
boundary M2–M7 enforced. The Supabase client used by the UI never bypasses
the `permission_policy` resolution or the `kaggle_submit` / `kernel_push`
approval gates. The UI's job is to **render** those decisions for a human,
not to forge them.

M8 also absorbs the six follow-ups carried forward from `docs/milestones/m7/final-review.md`:

1. Wire skill execution through the worker (`kca skill run <name>` non-dry-run
   now pipes the rendered skill body into `AgentWorker` with
   `JobPolicy.approval_gates` populated from `resolve_for_skill`).
2. Promote `agent_job_events.event_type="tool_audit"` into a dedicated
   `agent_tool_audit` table + view (migration 0007).
3. JSON-Schema gate for SKILL.md frontmatter (refuse malformed skills at load).
4. Hook `ToolSpec.timeout_s`, `sandbox`, and `approval_label` into
   `src/worker/worker.py::_tool_call` so runtime matches declared policy.
5. Retire `.kca/skills/_test_fixture/` — replace with a real platform skill
   or move into `tests/fixtures/`.
6. CI: confirm secret wiring on the `live-db` job, gate forks, add a
   UI build/lint/typecheck job.

### UI layers shipped in M8

| Layer | Tech | Owns |
|---|---|---|
| **App shell** | Vite + React + TypeScript + React Router | layout, nav, auth, theming |
| **Data client** | `@supabase/supabase-js` + typed schema | read-only Supabase queries against the existing tables |
| **Action client** | small Python-FastAPI service (or direct DB writes via signed RPC) | approve/reject decisions, never the kaggle CLI itself |
| **UI primitives** | Tailwind CSS + headlessui (no design-system dep) | tables, cards, modal, toasts |
| **Charts (minimal)** | `recharts` | CV-score timeline, cost-over-time |

Pages shipped:

| Page | Source data | Notes |
|---|---|---|
| Dashboard | `projects`, `competitions`, `runs` | overview cards, "in-flight" runs |
| Run Timeline | `agent_job_events`, `agent_telemetry_spans` | OTEL spans from M6 rendered as a swim-lane |
| Experiments | `experiments`, `runs`, `submissions` | sortable by metric |
| Research | `research_items`, `research_citations` (M5) | trust label + source URL |
| Approval Inbox | `human_decisions`, `agent_reviews`, `agent_tool_audit` (M7 follow-up #2) | shows operation, cv_score, cost_so_far, artifact preview |
| Decision Gate | one decision detail page | Approve / Reject / Ask-agent-to-improve actions |
| Artifacts | `artifacts` + storage paths | browse, preview small files only |

DB/sandbox notes carry over from M7:

```bash
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
KCA_DB_TARGET=local
```

Container IP may change on `docker compose down/up`; refresh with:
```bash
docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

DB calls require `dangerouslyDisableSandbox: true`. The Vite dev server runs
inside the normal sandbox on `localhost:5173`.

---

## M8 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M8-T000 | UI stack ADR + scaffold (Vite + React + TS, Tailwind, Supabase client) | Prompt 0 |
| M8-T001 | Migration 0007 — `agent_tool_audit` table + view; promote M7 audit JSONL into DB | Prompt 1 |
| M8-T002 | JSON-Schema gate on SKILL.md frontmatter; retire `_test_fixture` skill | Prompt 2 |
| M8-T003 | Skill → worker wiring; `ToolSpec` enforcement in `worker._tool_call` | Prompt 3 |
| M8-T004 | App shell — layout, nav, theming, read-only Supabase client | Prompt 4 |
| M8-T005 | Dashboard page — projects / competitions / in-flight runs | Prompt 5 |
| M8-T006 | Run Timeline page — OTEL span swim-lane + event log | Prompt 6 |
| M8-T007 | Experiments / Runs page — sortable table, metric drill-down | Prompt 7 |
| M8-T008 | Research page — citations, trust labels, source links | Prompt 8 |
| M8-T009 | Approval Inbox + Decision Gate page — Approve / Reject / Ask-improve | Prompt 9 |
| M8-T010 | Artifact Browser — listing + small-file preview (read-only) | Prompt 10 |
| M8-T011 | CI: UI build / lint / typecheck job; gate `live-db` on forks | Prompt 11 |
| M8-T012 | `tests/test_m8_smoke.py` + minimal Playwright smoke | Prompt 12 |
| M8-T013 | `docs/architecture/m8-ui-shell.md` — data flow, auth, gate semantics | Prompt 13 |
| M8-T014 | M8 exit criteria + `docs/milestones/m8/final-review.md` + `docs/milestones/m8/handoff.md` | Prompt 14 |

---

## Loop Prompt 0 — UI stack ADR + scaffold (M8-T000)

```
Read:
1. docs/milestones/README.md   (M8 section — stack constraints + planned capabilities)
2. docs/milestones/m7/handoff.md   (M7 → M8 handoff, M7 follow-ups)
3. docs/architecture/kca-cli-architecture.md   (the surface M8 calls into)
4. docs/adr/   (latest ADRs — match style)
5. pyproject.toml   (kca entry point + dev deps)
6. .claude/settings.json   (permissions allow-list for npm/pnpm/node/vite)

Goal: decide and document the UI stack, then scaffold the `ui/` workspace
with Vite + React + TypeScript + Tailwind + `@supabase/supabase-js`.

Step 1 — Write docs/adr/ADR-0011-ui-stack.md.
  - Status: Accepted.
  - Context: M8 needs a TypeScript-first React surface developed in Claude
    Code, talking to the existing Supabase control plane. Two viable shapes:
      A) Next.js app router (file-based routing, RSC, API routes).
      B) Vite + React + React Router (pure SPA, no SSR).
  - Decision: **Vite + React + React Router**. Rationale:
      - The product is an operator/dev workbench, not a public site; SEO
        and SSR are non-goals.
      - Backend writes already live in `tools/kca/*` + `src/worker/`;
        the UI does not need API routes.
      - Faster cold-start dev loop matches the Claude Code editing cadence.
      - Smaller surface to keep safe with the M7 permission policy.
  - Consequences:
      - All authenticated mutations go through Supabase RPC functions or
        a small Python action service (M9+). The browser never holds a
        service-role key.
      - Server-rendered features (e.g. social previews) are explicitly
        out of scope for M8.

Step 2 — Scaffold `ui/`:
  mkdir -p ui
  cd ui
  pnpm create vite . --template react-ts
  pnpm add @supabase/supabase-js react-router-dom recharts clsx
  pnpm add -D tailwindcss postcss autoprefixer @types/node \
    @testing-library/react @testing-library/jest-dom vitest jsdom \
    @playwright/test
  pnpm exec tailwindcss init -p

Step 3 — Wire Tailwind + base CSS:
  - `ui/tailwind.config.js`: content `["./index.html", "./src/**/*.{ts,tsx}"]`.
  - `ui/src/index.css`: `@tailwind base; @tailwind components; @tailwind utilities;`
  - Replace the Vite template `App.tsx` with a placeholder
    `<h1 className="p-4 text-2xl">kaggle-code-agent</h1>` so the smoke test
    has something to assert on.

Step 4 — Supabase client stub (read-only):
  ui/src/lib/supabase.ts:
    import { createClient } from "@supabase/supabase-js";
    const url  = import.meta.env.VITE_SUPABASE_URL  ?? "http://localhost:54321";
    const anon = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
    export const supabase = createClient(url, anon, {
      auth: { persistSession: false },
    });

  ui/.env.example:
    VITE_SUPABASE_URL=http://localhost:54321
    VITE_SUPABASE_ANON_KEY=replace_me

  Confirm `ui/.env*` is in the repo-level `.gitignore`.

Step 5 — Wire the root package scripts:
  ui/package.json scripts: `dev`, `build`, `preview`, `lint`, `test`,
  `typecheck` (= `tsc --noEmit`).

Verification:
  cd ui && pnpm install                 → 0 errors
  cd ui && pnpm typecheck               → 0 errors
  cd ui && pnpm build                   → builds to ui/dist
  cd ui && pnpm dev &                   → serves on :5173
  curl -s http://localhost:5173/        → HTML containing the placeholder
  pkill -f "vite" || true               (clean up dev server)

  test -f docs/adr/ADR-0011-ui-stack.md
  grep -q "Vite + React" docs/adr/ADR-0011-ui-stack.md

  python -m pytest tests/ -v -m "not db"   → 0 failures (UI scaffold must
                                              not break Python tests)

Do NOT git add or commit. Report: pnpm install summary, build output size,
typecheck status, ADR path.
```

---

## Loop Prompt 1 — `agent_tool_audit` migration (M8-T001)

```
Read:
1. docs/milestones/m7/final-review.md   (§ M8 follow-up #2)
2. supabase/migrations/0006_m6_reviews_spans.sql   (style template)
3. tools/kca/agent/audit.py   (AuditRecord fields + JSONL writer)
4. tools/kca/db.py            (append_job_event implementation)
5. docs/architecture/kca-cli-architecture.md   (Audit trail section)

Goal: add a first-class `agent_tool_audit` table, backfill the M7 JSONL
records into it, and switch the audit writer to dual-write
(`JSONL` for offline ops + DB when `SUPABASE_DB_URL` is set).

Step 1 — Write supabase/migrations/0007_m8_tool_audit.sql:
  CREATE TABLE IF NOT EXISTS agent_tool_audit (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id  UUID        NOT NULL,
    job_id      UUID        NULL REFERENCES agent_jobs(id) ON DELETE SET NULL,
    skill_name  TEXT        NULL,
    tool_name   TEXT        NOT NULL,
    operation   TEXT        NOT NULL,
    decision    TEXT        NOT NULL CHECK (decision IN ('allow','ask','deny')),
    mode        TEXT        NOT NULL DEFAULT 'default',
    policy_profile TEXT     NOT NULL DEFAULT 'default',
    audit_required BOOLEAN  NOT NULL DEFAULT false,
    args_hash   TEXT        NOT NULL,
    extra       JSONB       NOT NULL DEFAULT '{}'::jsonb
  );
  CREATE INDEX agent_tool_audit_session_idx ON agent_tool_audit(session_id);
  CREATE INDEX agent_tool_audit_job_idx     ON agent_tool_audit(job_id);
  CREATE INDEX agent_tool_audit_ts_idx      ON agent_tool_audit(ts DESC);

  CREATE OR REPLACE VIEW v_agent_tool_audit_recent AS
    SELECT a.*, j.skill_name AS job_skill_name, j.status AS job_status
    FROM agent_tool_audit a
    LEFT JOIN agent_jobs j ON j.id = a.job_id
    ORDER BY a.ts DESC
    LIMIT 200;

Step 2 — Update tools/kca/db.py:
  - Add `def insert_tool_audit(rec: dict) -> None` that INSERTs into
    `agent_tool_audit`. Best-effort: if no DB, return silently.
  - Keep `append_job_event(event_type="tool_audit", ...)` working but mark
    it deprecated in a docstring.

Step 3 — Update tools/kca/agent/audit.py:
  - In `AuditLogger.record`, when `backend in ("db", "both")` AND
    `SUPABASE_DB_URL` is set, call `insert_tool_audit(rec)` in addition
    to writing the JSONL line.
  - Never raise on DB failure; log to stderr and continue.

Step 4 — Optional backfill script:
  scripts/backfill_tool_audit.py:
    - Reads .agent/audit.jsonl
    - Inserts each line into agent_tool_audit (de-dup by (session_id, ts, tool_name)).
    - Idempotent.
  Document it in docs/architecture/kca-cli-architecture.md § Audit trail.

Verification (DB calls require dangerouslyDisableSandbox=true):
  # apply migration
  psql "$SUPABASE_DB_URL" -f supabase/migrations/0007_m8_tool_audit.sql
  psql "$SUPABASE_DB_URL" -c "\d agent_tool_audit"
    → table present with all columns

  # writer dual-writes
  python -c "
  from tools.kca.agent.audit import AuditLogger
  import pathlib, json, uuid
  log = AuditLogger(backend='both', file_path=pathlib.Path('.agent/audit.jsonl'))
  rec = log.log_policy_decision(
      tool='bash', operation='bash', decision='ask',
      skill_name='_test_fixture', mode='default',
      policy_profile='permissive-dev',
      args={'cmd': 'echo hi'},
  )
  print('wrote', rec.session_id)
  "
  psql "$SUPABASE_DB_URL" -c "SELECT count(*) FROM agent_tool_audit;"
    → at least 1

  python -m pytest tests/ -v -m "not db"   → 0 failures
  python -m pytest tests/ -v -m db         → all DB tests pass (with sandbox off)

Do NOT git add or commit. Report: migration applied, row count, JSONL still
present, deprecation note added.
```

---

## Loop Prompt 2 — SKILL.md schema gate + retire `_test_fixture` (M8-T002)

```
Read:
1. tools/kca/agent/skill_loader.py   (current SkillMeta + load_skill)
2. .kca/skills/run-milestone/SKILL.md   (example of a real skill)
3. .kca/skills/_test_fixture/SKILL.md   (fixture to retire)
4. tests/test_m7_smoke.py   (assertions that still depend on _test_fixture)
5. docs/milestones/m7/final-review.md   (§ M8 follow-up #3 and #5)

Goal: validate SKILL.md frontmatter against a JSON Schema at load time,
and move the test fixture out of `.kca/skills/` so it cannot be invoked
from the production CLI.

Step 1 — Add tools/kca/agent/skill_schema.py:
  SKILL_FRONTMATTER_SCHEMA = {
    "type": "object",
    "required": ["name", "description"],
    "additionalProperties": False,
    "properties": {
      "name":         {"type": "string", "pattern": "^[a-z0-9][a-z0-9-_]*$"},
      "description":  {"type": "string", "minLength": 1, "maxLength": 280},
      "version":      {"type": "string"},
      "argument-hint":{"type": "string"},
      "arguments":    {"type": "array", "items": {"type": "string"}},
      "allowed-tools":{"type": "array", "items": {"type": "string"}},
      "approval-policy": {"type": "string"},
      "disable-model-invocation": {"type": "boolean"},
      "tags":         {"type": "array", "items": {"type": "string"}},
    },
  }
  def validate_frontmatter(data: dict) -> None:
      """Raise SkillValidationError on schema mismatch."""

  class SkillValidationError(ValueError): ...

Step 2 — Wire into skill_loader.load_skill:
  - After YAML parse, call `validate_frontmatter(parsed)`.
  - On error, raise SkillValidationError with the path included.
  - Add a fast-fail when `allowed-tools` references a tool absent from
    TOOL_REGISTRY — raise with the offending tool name.

Step 3 — Move the test fixture:
  mkdir -p tests/fixtures/skills/_test_fixture
  git mv .kca/skills/_test_fixture/SKILL.md tests/fixtures/skills/_test_fixture/SKILL.md
  rmdir .kca/skills/_test_fixture
  # Update list_skills() to also accept an explicit skills_root (already supports it)
  # Update tests/test_m7_smoke.py to point fixture-loading tests at
  # tests/fixtures/skills as skills_root.

Step 4 — Add CLI flag for invoking a fixture skill via the test root:
  In tools/kca/skill.py, add a hidden `--skills-root` flag (default None,
  resolves to .kca/skills). Used only in tests; do NOT advertise in --help.

Verification:
  # Schema rejection
  python -c "
  from tools.kca.agent.skill_loader import load_skill, SkillValidationError
  import tempfile, pathlib, textwrap
  d = pathlib.Path(tempfile.mkdtemp()) / 'bad/SKILL.md'
  d.parent.mkdir(parents=True, exist_ok=True)
  d.write_text(textwrap.dedent('''---\nname: Bad Name With Spaces\ndescription: x\n---\nbody'''))
  try:
      load_skill('bad', skills_root=d.parent.parent)
      print('FAIL: should reject')
  except SkillValidationError as e:
      print('PASS:', e)
  "

  # Unknown tool in allowed-tools rejected
  python -c "
  from tools.kca.agent.skill_loader import load_skill, SkillValidationError
  # build a temp skill with allowed-tools: [does_not_exist]
  # expect SkillValidationError
  "  # (use tempfile pattern as above)

  # All real skills still load
  python -c "
  from tools.kca.agent.skill_loader import list_skills
  names = {m.name for m in list_skills()}
  assert {'run-milestone','triage-log','prepare-submission','review-pr'} <= names
  assert '_test_fixture' not in names, 'fixture should no longer ship via .kca/skills/'
  print('PASS real skills present, fixture removed')
  "

  python -m pytest tests/test_m7_smoke.py -v   → all pass after fixture path update
  python -m pytest tests/ -v -m "not db"        → 0 failures

Do NOT git add or commit. Report: schema rejection path, fixture move, test
suite still green.
```

---

## Loop Prompt 3 — Skill → worker wiring + `ToolSpec` enforcement (M8-T003)

```
Read:
1. src/worker/worker.py                 (_tool_call, AgentWorker loop)
2. src/worker/_types.py                 (JobPolicy, approval_gates)
3. src/worker/tools.py                  (current tool dispatch)
4. tools/kca/skill.py                   (kca skill run handler)
5. tools/kca/agent/tool_registry.py     (ToolSpec.timeout_s, sandbox, approval_label)
6. tools/kca/agent/permission_policy.py (resolve_for_skill)
7. docs/milestones/m7/final-review.md              (§ M8 follow-ups #1 and #4)

Goal: implement the M7 follow-ups #1 and #4 together — `kca skill run`
without `--dry-run` now drives an `AgentWorker` whose tool calls are
gated by the M7 permission policy and respect the ToolSpec metadata.

Step 1 — `kca skill run <name> [--mode <mode>] --execute` (or drop --dry-run
to keep the existing flag shape):
  - Build a JobPolicy:
      policy = JobPolicy(
          skill_name=name,
          allowed_tools=skill.meta.allowed_tools,
          approval_gates={
              tool: resolve_for_skill(skill.meta, tool, mode=args.mode)
              for tool in skill.meta.allowed_tools
          },
          max_turns=..., max_cost_usd=..., max_runtime_s=...,
      )
  - Create the agent_job row via tools/kca/db.create_agent_job(skill_name=name,
    policy=policy, rendered_prompt=rendered_body, …).
  - Hand to AgentWorker.run(job_id).

Step 2 — In src/worker/worker.py::_tool_call:
  - Resolve the ToolSpec via tool_registry.get_tool(tool_name).
  - Enforce ToolSpec.timeout_s as a hard timeout (use signal/alarm or
    subprocess.run timeout depending on the tool implementation).
  - Honour ToolSpec.sandbox:
      "sandboxed"          → run in current process (no extra escape).
      "unsandboxed"        → require approval_label resolved to "allow"
                             OR a satisfied approval gate from policy.
      "isolated_workspace" → cwd must be the job's workspace path.
  - Cross-check JobPolicy.approval_gates[tool_name]:
      "allow" → proceed.
      "ask"   → write human_decisions row + agent_job_events("decision_pending")
                + return a paused-job marker; do NOT execute.
      "deny"  → raise PolicyViolation, mark job failed.
  - On any decision, call audit.log_policy_decision(...) so the
    `agent_tool_audit` table records the outcome.

Step 3 — Tests:
  - Extend tests/test_m7_smoke.py (or add tests/test_m8_worker_wiring.py)
    with three tests:
      a) approval_gate "allow" → tool executes, audit row records "allow".
      b) approval_gate "ask"   → job pauses, human_decisions row created,
                                  audit row records "ask", no side effect.
      c) approval_gate "deny"  → job fails, no side effect, audit row "deny".
  - Use a fake ToolSpec ("noop_test_tool") wired into TOOL_REGISTRY behind
    a `_register_test_tool()` helper guarded by `pytest`-only import — do
    not pollute the production registry.

Verification:
  python -m pytest tests/test_m8_worker_wiring.py -v   → 3 passed
  python -m pytest tests/ -v -m "not db"                → 0 failures

  # End-to-end smoke with a benign skill (no real Kaggle / GH side effects):
  python tools/kca/kca.py skill run triage-log \
    --arg job_id=00000000-0000-0000-0000-000000000000 --execute --json
    → ok=true, job_id returned, audit rows present (verify via
      `python tools/kca/kca.py tool audit --limit 3 --json`)

  # Deny path: try to run a skill whose policy resolves to deny
  # (use competition-runner profile + an op that returns deny).
  # Confirm job ends with status="failed" and human_decisions has the row.

Do NOT git add or commit. Report: 3 wiring tests, audit rows, end-to-end
smoke job ID + status.
```

---

## Loop Prompt 4 — UI app shell + read-only data client (M8-T004)

```
Read:
1. ui/src/App.tsx                       (placeholder from Prompt 0)
2. ui/src/lib/supabase.ts               (from Prompt 0)
3. docs/architecture/kca-cli-architecture.md   (mental model for layers)
4. supabase/migrations/0001..0007       (table shapes for typed queries)

Goal: build the app shell — top nav, side nav, theme, error boundary,
routing, and a typed Supabase data client.

Step 1 — Routing:
  ui/src/main.tsx: wrap App in BrowserRouter.
  ui/src/routes.tsx: declare routes:
    /                  → Dashboard
    /runs              → Runs
    /runs/:jobId       → RunTimeline
    /experiments       → Experiments
    /research          → Research
    /approvals         → ApprovalInbox
    /approvals/:id     → DecisionGate
    /artifacts         → Artifacts

Step 2 — Layout:
  ui/src/components/Layout.tsx:
    - Header: project name, environment badge (local/dev/prod from
      VITE_KCA_ENV), GitHub link, "M8 preview" pill.
    - Side nav: links to the seven pages above with active-route highlight.
    - <Outlet /> for nested routes.
  ui/src/components/ErrorBoundary.tsx: catches render errors, shows the
  stack in dev, a friendly message in prod.

Step 3 — Typed data client:
  ui/src/lib/db.ts:
    Define narrow TypeScript types for each table the UI reads:
      Project, Competition, AgentJob, AgentJobEvent, AgentTelemetrySpan,
      Experiment, Run, Submission, ResearchItem, ResearchCitation,
      HumanDecision, AgentReview, Artifact, AgentToolAudit.
    Each function returns Promise<T[]> or Promise<T|null>:
      listProjects, getProject, listCompetitions,
      listRecentRuns, listRunsForCompetition,
      getJob, listJobEvents, listJobSpans,
      listExperiments, listSubmissions,
      listResearchItems, listCitationsForRun,
      listPendingDecisions, getDecision, listReviewsForJob,
      listArtifacts, listToolAudit.

  Each function uses the Supabase JS client; no raw SQL strings.
  Every function MUST handle the "no rows" case explicitly.

Step 4 — Generic UI primitives (no design-system dep):
  ui/src/ui/{Button,Card,Table,Badge,Empty,Spinner,Modal,Toast}.tsx
  Tailwind-only, no JS state unless necessary.

Verification:
  cd ui && pnpm typecheck                         → 0 errors
  cd ui && pnpm build                             → 0 errors
  cd ui && pnpm dev &                             → :5173
  curl -s http://localhost:5173/ | grep -q "kaggle-code-agent"
  curl -s http://localhost:5173/approvals | grep -q "<html"
  pkill -f "vite" || true

  # Type-check coverage:
  cd ui && pnpm exec tsc --noEmit --strict       → 0 errors

  python -m pytest tests/ -v -m "not db"          → 0 failures

Do NOT git add or commit. Report: route count, typed query count,
typecheck status.
```

---

## Loop Prompt 5 — Dashboard page (M8-T005)

```
Read:
1. ui/src/lib/db.ts                          (typed query functions)
2. ui/src/components/Layout.tsx
3. supabase/migrations/0001_init.sql        (projects, competitions)
4. supabase/migrations/0003_m3_worker.sql   (agent_jobs)
5. supabase/migrations/0006_m6_reviews_spans.sql (telemetry, reviews)

Goal: implement the Dashboard page — overview of projects, active
competitions, and currently running / pending jobs.

ui/src/pages/Dashboard.tsx:
  Sections:
    1. "Projects" — Card grid (one per project), shows competition count
       and last-active job timestamp.
    2. "Active competitions" — Table of `competitions` where there is
       at least one job in the last 30 days. Columns: slug, name, repo,
       open runs, last CV score, last submission status.
    3. "Inflight runs" — Table of agent_jobs WHERE status IN
       ('queued','running','awaiting_decision'). Columns: skill_name,
       status, started_at, turns_used, cost_so_far, link to RunTimeline.
    4. "Recent decisions" — last 10 rows from human_decisions, with
       a green pill for approved, red for rejected, amber for pending.

UI rules:
  - Every list section uses <Empty /> when there is no data.
  - Every loading state uses <Spinner />, never a blank screen.
  - Never call mutating endpoints from this page.

Verification:
  cd ui && pnpm test -- --run                    → page test asserts the
    four sections render with mock data (use vitest + RTL with a stubbed
    supabase client; do NOT call the real DB in unit tests).

  # Manual smoke (requires running DB):
  cd ui && pnpm dev &
  curl -s http://localhost:5173/ | grep -q "Projects"
  curl -s http://localhost:5173/ | grep -q "Active competitions"
  curl -s http://localhost:5173/ | grep -q "Inflight runs"
  curl -s http://localhost:5173/ | grep -q "Recent decisions"
  pkill -f "vite" || true

  cd ui && pnpm typecheck                         → 0 errors
  python -m pytest tests/ -v -m "not db"          → 0 failures

Do NOT git add or commit. Report: section presence, vitest results,
typecheck status.
```

---

## Loop Prompt 6 — Run Timeline + event log (M8-T006)

```
Read:
1. supabase/migrations/0003_m3_worker.sql       (agent_job_events shape)
2. supabase/migrations/0006_m6_reviews_spans.sql (agent_telemetry_spans, OTEL)
3. src/worker/telemetry.py                      (span fields populated)
4. ui/src/lib/db.ts                             (listJobEvents, listJobSpans)

Goal: render a single agent job as a swim-lane timeline of OTEL spans
plus a paginated event log on the right.

ui/src/pages/RunTimeline.tsx:
  - Route: /runs/:jobId
  - Top: Job summary card — skill_name, status, turns_used, cost_so_far,
    started_at / ended_at, link to project + competition.
  - Middle: SVG swim-lane:
      - One row per `span.name` (or grouped by `span.attributes.kind`:
        job / turn / tool / reviewer / local-probe).
      - X axis: elapsed time since job start.
      - Hover tooltip: span name + duration + attributes JSON.
      - Color: green=ok, red=error, amber=in-progress.
      - Use a simple <svg> render — no D3, no recharts here.
  - Right rail: paginated event log from agent_job_events.
      - Filter by event_type (tool_call, decision_request, review_verdict,
        budget_warning, error).
      - Each row: ts | event_type | summary | expand-to-JSON.

UI rules:
  - The page is read-only. No buttons that emit writes.
  - Empty job → render <Empty /> with link back to /runs.

Verification:
  cd ui && pnpm test -- --run                   → page test renders 3 mock
    spans into a swim-lane and asserts the row count.

  cd ui && pnpm typecheck                       → 0 errors

  # Manual smoke (requires running DB with at least one job from
  # Prompt 3's end-to-end smoke):
  cd ui && pnpm dev &
  JOB_ID=$(psql "$SUPABASE_DB_URL" -t -A -c \
    "SELECT id FROM agent_jobs ORDER BY started_at DESC LIMIT 1;")
  curl -s "http://localhost:5173/runs/$JOB_ID" | grep -q "skill"
  pkill -f "vite" || true

  python -m pytest tests/ -v -m "not db"        → 0 failures

Do NOT git add or commit. Report: swim-lane rendered, span count, event
log row count.
```

---

## Loop Prompt 7 — Experiments / Runs table (M8-T007)

```
Read:
1. supabase/migrations/0004_m4_competition_repo.sql  (experiments, runs, submissions)
2. ui/src/lib/db.ts   (listExperiments, listRunsForCompetition)
3. ui/src/pages/Dashboard.tsx   (table style to mirror)

Goal: a sortable, filterable table of experiments and runs across
competitions, with a drill-down to per-run metrics.

ui/src/pages/Experiments.tsx:
  Header filters: competition slug, status, "show submitted only".
  Table columns:
    - Experiment ID + name
    - Competition
    - Last run ts
    - CV score (best of runs.metric_value where metric_name = cv_score)
    - LB score (latest submissions.public_score)
    - Status badge
    - link to /runs/:jobId for the latest run

Sortable by: ts desc (default), CV asc/desc, LB asc/desc.
Pagination: 25 per page, server-side via Supabase `.range(...)`.

ui/src/pages/RunDetail.tsx (route: /experiments/:experimentId):
  - Lists all runs for the experiment.
  - For each run: ts, metric_name, metric_value, artifact link.
  - Links to the run timeline page.

UI rules:
  - Sortable column headers must be keyboard accessible.
  - Numeric columns right-aligned, monospace.

Verification:
  cd ui && pnpm test -- --run                  → sort + filter logic tests
    pass with mock data; column count matches spec.

  cd ui && pnpm typecheck                      → 0 errors
  cd ui && pnpm build                          → 0 errors

  python -m pytest tests/ -v -m "not db"       → 0 failures

Do NOT git add or commit. Report: column list, sort tests, build size.
```

---

## Loop Prompt 8 — Research page (M8-T008)

```
Read:
1. supabase/migrations/0005_m5_research_citations.sql
2. tools/kca/research.py                        (trust labels, source URL fields)
3. ui/src/lib/db.ts                             (listResearchItems, listCitationsForRun)

Goal: surface the M5 research items and citations so a human can audit
what the agent read.

ui/src/pages/Research.tsx:
  Left rail: research items list, newest first. Each row shows:
    - title / source URL (link opens in new tab with rel="noopener noreferrer")
    - trust label (badge: green=high, amber=medium, red=low/unknown)
    - related_run_id link
    - fetched_at ts
  Main panel: when an item is selected:
    - rendered Markdown summary
    - citations table: run_id, span snippet, similarity, link to /runs/:jobId
    - "raw source" disclosure (collapsed by default; expands to the
      stored DOM snapshot path under artifacts/research/)

UI rules:
  - All external URLs open in a new tab, rel="noopener noreferrer".
  - Markdown render uses a strict sanitiser (no inline JS, no remote
    images by default — show "load image" placeholder).
  - Never auto-fetch external content from the browser; only display
    what is already in the DB / artifacts.

Verification:
  cd ui && pnpm test -- --run                  → sanitiser test asserts
    `<script>` tags are stripped; rel attributes present on <a>.

  cd ui && pnpm typecheck                      → 0 errors

  python -m pytest tests/ -v -m "not db"       → 0 failures

Do NOT git add or commit. Report: sanitiser test, trust label colours,
external link rel attribute count.
```

---

## Loop Prompt 9 — Approval Inbox + Decision Gate (M8-T009)

```
Read:
1. supabase/migrations/0003_m3_worker.sql       (human_decisions)
2. supabase/migrations/0006_m6_reviews_spans.sql (agent_reviews)
3. supabase/migrations/0007_m8_tool_audit.sql   (agent_tool_audit)
4. tools/kca/decisions.py                       (approve / reject CLI)
5. tools/kca/agent/permission_policy.py         (decision semantics)
6. docs/milestones/README.md   (M8 § Decision-gate UI requirements)

Goal: the most important M8 page. A human sees every pending decision,
approves / rejects / asks-the-agent-to-improve, and the write path goes
through the EXISTING `kca decisions` mechanism — the browser never
bypasses the permission policy.

Step 1 — `ui/src/pages/ApprovalInbox.tsx`:
  - List human_decisions where status = 'pending'.
  - Columns: operation, run_id link, requested_at, policy_profile,
    reviewer_verdict (from agent_reviews if any), action link.
  - Default sort: oldest first ("FIFO so nothing rots").

Step 2 — `ui/src/pages/DecisionGate.tsx` (route /approvals/:id):
  Show the full context required by the milestone spec:
    - operation
    - cv_score (joined from runs.metric_value where metric_name='cv_score')
    - cost_so_far (joined from agent_jobs.cost_so_far)
    - artifact preview (top 50 lines if the file is text and < 1 MB;
      otherwise a download link only — never preview binaries inline)
    - reviewer verdict + reasoning (from agent_reviews)
    - recent tool audit entries for the job (from agent_tool_audit)

  Three actions:
    - Approve  → POST to action service (Step 3) with reason field optional.
    - Reject   → POST with reason required (UI enforces minLength=8).
    - Ask agent to improve → POST with a structured "feedback" payload
      (free text + optional metric_target). The backend appends to
      `agent_job_events` and resumes the job at the next planning turn.

  All three actions disable buttons immediately and show a spinner until
  the response comes back. On success, redirect to /approvals.

Step 3 — Action service:
  Stand up a tiny FastAPI app at `services/decision_api/` (Python).
    POST /decision/:id/approve
    POST /decision/:id/reject
    POST /decision/:id/ask-improve
  Each endpoint:
    - Validates the user (M8 ships local-only: simple HMAC over
      `KCA_DECISION_API_TOKEN`; UI reads token from a same-origin
      cookie set out-of-band by `kca ui login`).
    - Calls the existing functions in tools/kca/decisions.py.
    - Writes audit via tools.kca.agent.audit.log_policy_decision.
  Wire pnpm dev's vite.config.ts to proxy `/api/*` to localhost:8787.

UI rules:
  - The browser cannot construct a `kaggle competitions submit` call; it
    can only call /decision/:id/approve. The actual submit still flows
    through the worker after the approval is recorded.
  - "Approve" button is RED-DESTRUCTIVE-style if the operation is
    SUBMISSION-class (kaggle_submit, kernel_push, supabase_migrate),
    AMBER-CAUTION-style otherwise.
  - Decision changes are atomic: the API rejects with 409 if the
    decision is already non-pending.

Verification:
  cd ui && pnpm test -- --run                   → DecisionGate tests assert
    button colour by operation class + the "minimum 8 chars" reason rule.

  # Action service round-trip (offline; the API is mocked to not call
  # real Kaggle):
  python -m pytest services/decision_api/tests -v   → all pass

  # Manual smoke:
  KCA_DECISION_API_TOKEN=dev-token \
    uvicorn services.decision_api.app:app --port 8787 &
  cd ui && pnpm dev &
  curl -s http://localhost:5173/approvals | grep -q "Approval Inbox"
  pkill -f "vite|uvicorn" || true

  cd ui && pnpm typecheck                       → 0 errors
  python -m pytest tests/ -v -m "not db"        → 0 failures

Do NOT git add or commit. Report: 3 actions, 409 atomic rule, button
colour rules, all tests green.
```

---

## Loop Prompt 10 — Artifact Browser (M8-T010)

```
Read:
1. supabase/migrations/0001_init.sql            (artifacts table)
2. docs/adr/                                   (artifact storage ADR)
3. ui/src/lib/db.ts                             (listArtifacts)

Goal: a read-only artifact browser. Lists artifacts by job/run and
previews small text files inline; binaries get a download link only.

ui/src/pages/Artifacts.tsx:
  Filters: job_id, competition slug, artifact_type.
  Table columns: path, type, size, sha256 (first 12 chars), created_at, run link.

ui/src/pages/ArtifactDetail.tsx (route /artifacts/:id):
  - Show metadata.
  - If text and size < 1 MB: inline preview via <pre> with a content-type
    guess (utf-8 only). For CSV: a first-100-rows table render.
  - If binary or > 1 MB: download link only. Show a clear warning.
  - Never preview .pkl, .pt, .h5, .bin, .so — always download-only.

Verification:
  cd ui && pnpm test -- --run                   → size-cap test, binary
    extension blocklist test, CSV 100-row cap test.

  cd ui && pnpm typecheck                       → 0 errors
  cd ui && pnpm build                           → 0 errors

  python -m pytest tests/ -v -m "not db"        → 0 failures

Do NOT git add or commit. Report: blocklist enforced, size cap honoured,
build OK.
```

---

## Loop Prompt 11 — CI: UI build + live-db fork gating (M8-T011)

```
Read:
1. .github/workflows/test.yml             (existing no-db / live-db / lint)
2. docs/milestones/m7/final-review.md                (§ M8 follow-up #6 — confirm
                                            secret wiring + gate forks)
3. ui/package.json                        (lint, build, typecheck scripts)

Goal: extend CI so PRs run the UI build/lint/typecheck job; the live-db
job no longer runs on forks but DOES run on push to main with secrets.

Step 1 — Add a `ui` job to .github/workflows/test.yml:
  ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm, cache-dependency-path: ui/pnpm-lock.yaml }
      - run: pnpm -C ui install --frozen-lockfile
      - run: pnpm -C ui lint
      - run: pnpm -C ui typecheck
      - run: pnpm -C ui build
      - run: pnpm -C ui test -- --run

Step 2 — Gate the live-db job:
  jobs.live-db.if: |
    github.event_name == 'push' && github.ref == 'refs/heads/main'
    || (github.event_name == 'pull_request'
        && github.event.pull_request.head.repo.full_name == github.repository)

  Add a step that asserts `secrets.SUPABASE_DB_URL` is non-empty; if it's
  empty (fork PR), skip with a clear log line rather than failing.

Step 3 — Add a `python-lint-strict` step that runs `ruff check --select=ALL --ignore=...`
  using the existing ruff config (no new rules — just confirm the existing
  ruleset).

Verification:
  python -c "
  import yaml
  d = yaml.safe_load(open('.github/workflows/test.yml'))
  jobs = d['jobs']
  assert 'ui' in jobs, jobs.keys()
  assert 'if' in jobs['live-db'], jobs['live-db']
  print('PASS workflow shape')
  "

  # Local equivalent of the UI job:
  pnpm -C ui install --frozen-lockfile   → 0 errors
  pnpm -C ui lint                        → 0 issues
  pnpm -C ui typecheck                   → 0 errors
  pnpm -C ui build                       → 0 errors
  pnpm -C ui test -- --run               → all pass

  python -m pytest tests/ -v -m "not db" → 0 failures

Do NOT git add or commit. Report: jobs in workflow, live-db gating
expression, all local mirror steps green.
```

---

## Loop Prompt 12 — Smoke tests + Playwright (M8-T012)

```
Read:
1. tests/test_m7_smoke.py                       (Python smoke style)
2. tools/kca/agent/audit.py                     (insert_tool_audit, AuditLogger)
3. tools/kca/agent/skill_loader.py              (SkillValidationError)
4. services/decision_api/app.py                 (action endpoints)
5. ui/src/pages/*.tsx                           (page IDs for Playwright selectors)

Goal: tests/test_m8_smoke.py (Python, 12–15 tests) + ui/tests/e2e/m8.spec.ts
(Playwright, 4 tests). All pass without ANTHROPIC_API_KEY, KAGGLE_KEY, or
real network egress; live-DB-dependent tests use the @pytest.mark.db gate.

Required Python tests (use these names verbatim):
  1.  test_tool_audit_table_present_on_db_target [db]
        Reads pg_catalog to confirm agent_tool_audit + view exist.
  2.  test_tool_audit_dual_write_jsonl_only(tmp_path)
        With SUPABASE_DB_URL unset, AuditLogger(backend='both') still
        writes the JSONL line and does NOT raise.
  3.  test_skill_schema_rejects_bad_name(tmp_path)
        load_skill on a SKILL.md with name "Bad Name" raises SkillValidationError.
  4.  test_skill_schema_rejects_unknown_tool(tmp_path)
        allowed-tools containing "made_up_tool" raises SkillValidationError.
  5.  test_skill_fixture_no_longer_in_kca_skills()
        '.kca/skills/_test_fixture' does NOT exist on disk.
  6.  test_skill_fixture_still_loadable_from_tests_root()
        load_skill('_test_fixture', skills_root=tests/fixtures/skills) works.
  7.  test_worker_tool_call_allow_path(monkeypatch)
        Approval gate "allow" → tool executes, audit row recorded.
  8.  test_worker_tool_call_ask_path(monkeypatch)
        Approval gate "ask" → no side effect, human_decisions row created,
        audit row "ask".
  9.  test_worker_tool_call_deny_path(monkeypatch)
        Approval gate "deny" → no side effect, job status="failed",
        audit row "deny".
  10. test_decision_api_approve_idempotent(client)
        Two POSTs to /decision/:id/approve → first 200, second 409.
  11. test_decision_api_reject_minlength(client)
        POST /decision/:id/reject with reason of length 7 → 400.
  12. test_decision_api_ask_improve_appends_event(client)
        Successful call appends agent_job_events("feedback") row.
  13. test_kca_skill_run_execute_creates_job(monkeypatch)
        `kca skill run triage-log --arg job_id=... --execute --json`
        returns a job_id; agent_jobs row exists.

Required Playwright tests (ui/tests/e2e/m8.spec.ts):
  1. dashboard_has_four_sections — visits /, asserts 4 section headings.
  2. approvals_inbox_lists_pending — visits /approvals, asserts table
     row count matches a seeded fixture (use Supabase docker test fixture).
  3. decision_gate_blocks_short_reason — types 5-char reject reason,
     "Reject" button stays disabled; types 10 chars, becomes enabled.
  4. external_link_has_noopener — every <a target="_blank"> on /research
     has rel="noopener noreferrer".

Verification:
  python -m pytest tests/test_m8_smoke.py -v   → 13/13 pass (db-marked
                                                  tests run only when
                                                  SUPABASE_DB_URL is set)
  cd ui && pnpm exec playwright install --with-deps chromium
  cd ui && pnpm exec playwright test            → 4/4 pass
  python -m pytest tests/ -v -m "not db"        → 0 failures total

Do NOT git add or commit. Report: per-test status, Playwright trace
location, any flaky test re-run count.
```

---

## Loop Prompt 13 — M8 architecture documentation (M8-T013)

```
Read:
1. docs/architecture/kca-cli-architecture.md   (style template)
2. ui/src/lib/db.ts                            (data flow inventory)
3. services/decision_api/app.py                (action service shape)
4. supabase/migrations/0007_m8_tool_audit.sql  (audit table)

Goal: write docs/architecture/m8-ui-shell.md.

Required sections:

## Overview
One paragraph: M8 surfaces the M2–M7 control plane as a read-mostly UI.
The browser never writes to Supabase directly except through the
decision_api action service, which routes through the existing
`tools/kca/decisions.py` paths so M7 policy gates stay authoritative.

## Layer map
Diagram (ASCII) of:
  Browser (Vite SPA) → Supabase JS (read) → Postgres
                    → /api/decision/* → decision_api → kca decisions → Postgres
                                                                       → worker resume

## Data flow per page
For each of: Dashboard, RunTimeline, Experiments, Research, ApprovalInbox,
DecisionGate, Artifacts — list the tables read and the joins performed.

## Auth model
- Local-only token via KCA_DECISION_API_TOKEN.
- M8 ships single-user; multi-user lands in M9 or later.
- No service-role key ever reaches the browser.

## Approval gate semantics
- "Approve" / "Reject" / "Ask agent to improve" map to existing
  `tools/kca/decisions.py` functions.
- The browser cannot mutate `agent_jobs.status` directly; only the
  action service can, and only via the kca decisions API.
- M7 permission_policy.resolve_for_skill is the source of truth for
  which operations need a decision; UI is purely a presentation layer.

## Audit trail
- Every action service mutation writes a row to `agent_tool_audit`.
- `.agent/audit.jsonl` continues to exist for offline ops; the dual-write
  behaviour from M8-T001 keeps both backends in sync when DB is available.

## Adding a new page
Step-by-step: add route → add typed query in `ui/src/lib/db.ts` →
add page component → write vitest test → optional Playwright case.

## Adding a new approve-class operation
Step-by-step: add ToolSpec to TOOL_REGISTRY (M7) → add policy record →
add decision_api wiring → render in DecisionGate.

Verification:
  test -f docs/architecture/m8-ui-shell.md
  wc -l docs/architecture/m8-ui-shell.md         → at least 100 lines
  for h in "Overview" "Layer map" "Data flow per page" "Auth model" \
           "Approval gate semantics" "Audit trail" \
           "Adding a new page" "Adding a new approve-class operation"; do
    grep -q "$h" docs/architecture/m8-ui-shell.md \
      && echo "PASS $h" || echo "FAIL $h"
  done

  python -m pytest tests/ -v -m "not db"          → 0 failures

Do NOT git add or commit. Report: line count, section headings, any FAIL.
```

---

## Loop Prompt 14 — M8 exit criteria + final review + handoff (M8-T014)

```
Goal: verify ALL M8 exit criteria. Gate before M8 is declared complete.

Run each check and report PASS / FAIL / SKIP:

Backend follow-ups (from M7):
 1. supabase/migrations/0007_m8_tool_audit.sql applied; `agent_tool_audit`
    table + `v_agent_tool_audit_recent` view present.
 2. tools/kca/agent/audit.py dual-writes JSONL + DB; never raises on DB error.
 3. SkillValidationError raised on bad name; on unknown tool in allowed-tools.
 4. `.kca/skills/_test_fixture/` removed; tests/fixtures/skills/_test_fixture/
    SKILL.md present.
 5. `kca skill run <name> --execute` creates an agent_jobs row and drives
    AgentWorker; allow/ask/deny paths all produce the right audit rows.
 6. `src/worker/worker.py::_tool_call` honours ToolSpec.timeout_s,
    ToolSpec.sandbox, and JobPolicy.approval_gates.

UI app shell:
 7. `cd ui && pnpm install --frozen-lockfile` succeeds.
 8. `pnpm -C ui typecheck` → 0 errors.
 9. `pnpm -C ui lint` → 0 issues.
10. `pnpm -C ui build` → 0 errors.
11. `pnpm -C ui test -- --run` → all pass (≥ 12 vitest cases).

UI pages:
12. Dashboard shows Projects + Active competitions + Inflight runs + Recent decisions.
13. /runs/:jobId renders span swim-lane + event log.
14. /experiments table sortable by CV + LB.
15. /research lists items with trust badges; external links have rel="noopener noreferrer".
16. /approvals lists pending decisions; /approvals/:id has Approve / Reject / Ask-improve.
17. /artifacts blocks binary preview and CSV >100 rows.

Action service:
18. POST /decision/:id/approve idempotent (409 on second call).
19. POST /decision/:id/reject enforces minLength=8 on reason.
20. POST /decision/:id/ask-improve appends agent_job_events("feedback").
21. No service-role key reachable from the browser (search ui/ for
    `SERVICE_ROLE` → 0 matches).

CI:
22. `.github/workflows/test.yml` has a `ui` job and a gated `live-db` job.
23. `python -m pytest tests/ -v -m "not db"` → 0 failures.
24. `ruff check .` → 0 issues; `ruff format --check .` → 0 issues.

Smoke + e2e:
25. `python -m pytest tests/test_m8_smoke.py -v` → 13/13 pass
    (or ≥ 12 + any extras).
26. `pnpm -C ui exec playwright test` → 4/4 pass.

Architecture doc:
27. docs/architecture/m8-ui-shell.md exists, ≥ 100 lines.
28. All required headings present (Overview, Layer map, Data flow per
    page, Auth model, Approval gate semantics, Audit trail, Adding a
    new page, Adding a new approve-class operation).

Final document:
  Print full validation matrix (check | PASS/FAIL/SKIP | note).
  If all non-SKIP pass → output "M8 EXIT CRITERIA MET".
  Create docs/milestones/m8/final-review.md following the structure of
  docs/milestones/m7/final-review.md with:
    - Validation matrix.
    - What landed (files created / modified, with one-line purpose each).
    - DB access note (which checks needed dangerouslyDisableSandbox).
    - M9 follow-ups list.

Also update, in order:
  1. PROJECT_STATE.md — set current milestone to M9, summarise M8
     deliverables, clear M8 open decisions.
  2. README.md — update "Current milestone" from M8 to M9.
  3. docs/milestones/README.md — mark M8 ✓ done with one-line summary; bump
     the header status line (the stale "M6 done, M7 in planning" line
     should already have been fixed during M7 closeout; if not, fix it now).
  4. docs/milestones/m8/handoff.md — per-milestone handoff prompt for the
     next AI tool / session that will start M9 (live Kaggle regression test
     for Spaceship Titanic, per docs/milestones/README.md § M9). Use
     docs/milestones/_templates/handoff-prompt.md as the canonical template. Populate:
       - Read-first list (PROJECT_STATE.md, AGENTS.md, CLAUDE.md, M9
         section of docs/milestones/README.md, docs/milestones/m8/final-review.md, latest
         ADRs, docs/architecture/m8-ui-shell.md, docs/architecture/kca-cli-architecture.md).
       - "State at M8 exit" (1–3 lines summarising what landed +
         exit-matrix outcome + M9 follow-ups list).
       - "Current task" stub for the first M9 task (typically Prompt 0
         of docs/milestones/m9/loop-prompts.md once that file exists; if not yet
         written, the first task is to draft it).
     This step is required by docs/milestones/README.md § Milestone final-review
     protocol; do not skip it.

Do NOT git add or commit unless the human explicitly requests it.
Report: full matrix, final status.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
# Confirm M7 exit state
python -m pytest tests/ -v -m "not db"   # should be 0 failures from M7
python tools/kca/kca.py skill list --json | head -20

# Node / pnpm
node --version    # >= 20
pnpm --version    # >= 9
# If missing:
#   curl -fsSL https://get.pnpm.io/install.sh | sh -
#   # then `source ~/.zshrc` or open a new shell

# DB (only needed for db-marked tests + migration application)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local
# Refresh container IP if needed:
# docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'

# Decision API
export KCA_DECISION_API_TOKEN=dev-token
```

### Settings additions for autonomous M8 loop

These entries extend the M7 `.claude/settings.json` allow-list:

```json
"Bash(pnpm -C ui*)",
"Bash(pnpm install*)",
"Bash(pnpm dlx*)",
"Bash(pnpm exec*)",
"Bash(vite*)",
"Bash(uvicorn*)",
"Bash(curl -s http://localhost:5173*)",
"Bash(curl -s http://localhost:8787*)",
"Bash(pkill -f *vite*)",
"Bash(pkill -f *uvicorn*)"
```

### Sandbox notes

UI development is mostly local: pnpm install (npmjs registry — already
allowed), Vite dev server on :5173, vitest, Playwright headless chromium
on :5173, and the decision_api on :8787. None of these need
`dangerouslyDisableSandbox`. The DB-bearing checks in Prompts 1, 3, 9, 12,
and 14 do — same pattern as M7.

Playwright browser download in Prompt 12 pulls from playwright.dev which
is on the network allow-list.

### Full autonomous run

```bash
claude --bg \
  --name "M8" \
  --model opus \
  --effort high \
  "/goal Execute M8 Loop Prompts 0 through 14 from docs/milestones/m8/loop-prompts.md
in sequence. Each prompt's acceptance checks must pass before moving to
the next. On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push unless Prompt 14 completes with M8 EXIT
CRITERIA MET and the human explicitly requests it.
Do not call the real Kaggle API. Do not exfiltrate Supabase credentials
to the browser bundle. Use the mocked decision_api in tests.
For DB validation use:
  SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
  (container IP; refresh via docker inspect supabase-db if it changes)
DB calls require dangerouslyDisableSandbox=true.
Vite dev server, Playwright, and decision_api run inside the normal sandbox.
Report PASS/FAIL for each prompt's verification step inline.
Stop at any FAIL that cannot be fixed within 3 attempts and report the blocker."
```

### Closeout checklist

After M8 EXIT CRITERIA MET, before moving to M9:

- [ ] docs/milestones/m8/final-review.md created with validation matrix.
- [ ] PROJECT_STATE.md updated: current milestone = M9.
- [ ] README.md current milestone updated to M9.
- [ ] docs/milestones/README.md M8 marked ✓ done; stale "M6 done, M7 in planning"
      header at line 3 cleared.
- [ ] docs/milestones/m8/handoff.md written from docs/milestones/_templates/handoff-prompt.md template.
- [ ] No `SERVICE_ROLE` strings or other secret material in the `ui/` bundle.
- [ ] `tests/fixtures/skills/_test_fixture/` is the only place the fixture lives.
- [ ] Human reviews `docs/milestones/m8/final-review.md` and confirms M9 scope
      (live Spaceship Titanic submission flow under approval).
