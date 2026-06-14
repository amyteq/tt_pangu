# M6 / MVP-6 Loop Prompts

_Multi-agent review + OTEL telemetry + local-model layer._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M5 exit criteria confirmed met (see `docs/milestones/m5/final-review.md`)._

---

## M6 at a glance

M6 introduces three coordinated capabilities on top of the M5 worker:

1. A **reviewer agent** that runs synchronously before high-stakes
   operations (`kaggle_submit`, `supabase_migrate`, `git_force_push`,
   `dataset_upload`, `delete_artifact`). The reviewer reads the job's
   event trail + final plan, emits `approve | reject | abstain`, and
   either satisfies the matching approval gate, escalates to a human
   decision, or fails the job.
2. A **local-model layer** that talks to vLLM / Ollama on the user's two
   GPU hosts (`snorlax` RTX 4090, `may` RTX 3090) through OpenAI-compatible
   HTTP. The router probes endpoints with a short TTL cache and falls back
   to `KCA_LOCAL_FALLBACK_MODEL` (default `claude-haiku-4-5`) when none are
   up. Two new job types — `log_triage` and `summarise` — route to the
   local layer by default.
3. **OpenTelemetry instrumentation** per ADR-0007 with three exporters:
   stderr (dev), SQLite (`.agent/telemetry.sqlite`), and Supabase
   (`agent_telemetry_spans`). Spans cover the job, each turn, each tool
   call, each reviewer run, and each local-endpoint probe.

DB validation uses the M5-confirmed DSN:

```bash
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
KCA_DB_TARGET=local
```

`172.21.0.4` is the `supabase-db` container IP; container IPs change on
`docker compose down/up`. Refresh with
`docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.
DB and local-endpoint calls run with `dangerouslyDisableSandbox: true`
because LAN/Docker hosts aren't in the sandbox proxy allow-list.

---

## M6 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M6-T000 | Migration 0006 — `agent_reviews` + `agent_telemetry_spans` + `agent_jobs.otel_*` | Prompt 0 |
| M6-T001 | DB layer — reviews + telemetry helpers | Prompt 1 |
| M6-T002 | Local-model endpoint layer + availability probe | Prompt 2 |
| M6-T003 | `env.example` update for local endpoints + reviewer + OTEL | Prompt 3 |
| M6-T004 | Reviewer worker + sync-gate integration (ADR-0012) | Prompt 4 |
| M6-T005 | OTEL instrumentation (console + SQLite + Supabase) (ADR-0013) | Prompt 5 |
| M6-T006 | Local-model job types (`log_triage`, `summarise`) + `kca local triage` | Prompt 6 |
| M6-T007 | `kca review list / show / run` CLI | Prompt 7 |
| M6-T008 | TC-3 Spaceship Titanic end-to-end | Prompt 8 |
| M6-T009 | `tests/test_m6_smoke.py` (12–14 tests) | Prompt 9 |
| M6-T010 | M6 exit criteria + `docs/milestones/m6/final-review.md` | Prompt 10 |

---

## Loop Prompt 0 — Migration 0006 (M6-T000)

```
Read:
1. docs/tasks/m6/M6-T000-migration-0006-reviews-spans.md
2. supabase/migrations/0005_m5_research_citations.sql  (additive ALTER style)
3. supabase/migrations/0003_m3_worker.sql              (agent_jobs shape)
4. docs/milestones/README.md  (M6 section)

Goal: write supabase/migrations/0006_m6_reviews_spans.sql.

Part A — agent_reviews:
  id uuid PK, job_id NOT NULL FK→agent_jobs(id) ON DELETE CASCADE,
  run_id FK→experiment_runs(id), reviewer_model text NOT NULL,
  reviewer_kind text NOT NULL DEFAULT 'sync',
  target_op text, verdict text NOT NULL,
  rationale text, evidence jsonb NOT NULL DEFAULT '{}',
  cost_usd numeric(10,4) NOT NULL DEFAULT 0,
  decision_id FK→human_decisions(id) ON DELETE SET NULL,
  otel_span_id text, created_at timestamptz NOT NULL DEFAULT now().
  + indexes (job_id, target_op); RLS ON.

Part B — agent_telemetry_spans:
  id bigserial PK, trace_id text NOT NULL, span_id text NOT NULL,
  parent_span_id text, job_id FK→agent_jobs(id) ON DELETE CASCADE,
  kind text NOT NULL, name text NOT NULL,
  started_at timestamptz NOT NULL, ended_at timestamptz,
  duration_ms bigint, attributes jsonb NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'ok', error text.
  + indexes (trace_id, job_id, kind); RLS ON.

Part C — agent_jobs additions:
  ADD COLUMN IF NOT EXISTS otel_trace_id text,
  ADD COLUMN IF NOT EXISTS otel_root_span_id text.

Verification:
  # With SUPABASE_DB_URL set:
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0006_m6_reviews_spans.sql
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0006_m6_reviews_spans.sql  # twice
  psql "$SUPABASE_DB_URL" -c "\d agent_reviews"        | grep -E "verdict|reviewer_model|target_op"
  psql "$SUPABASE_DB_URL" -c "\d agent_telemetry_spans" | grep -E "trace_id|kind|attributes"
  psql "$SUPABASE_DB_URL" -c "\d agent_jobs"           | grep -E "otel_trace_id|otel_root_span_id"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: migration created, idempotent re-apply, schema check.
```

---

## Loop Prompt 1 — DB layer (M6-T001)

```
Read:
1. docs/tasks/m6/M6-T001-db-layer-reviews-telemetry.md
2. tools/kca/db.py (__all__, _with_conn)
3. supabase/migrations/0006_m6_reviews_spans.sql

Goal: extend tools/kca/db.py with:
  create_review(*, job_id, reviewer_model, verdict, reviewer_kind="sync",
                target_op=None, rationale=None, evidence=None,
                run_id=None, cost_usd=0.0, decision_id=None,
                otel_span_id=None) -> str
  get_review(review_id) -> dict
  list_reviews(job_id=None, verdict=None, limit=50) -> list[dict]
  find_review_for_op(job_id, target_op) -> dict | None
  record_span(*, trace_id, span_id, parent_span_id=None, job_id=None,
              kind, name, started_at, ended_at=None, duration_ms=None,
              attributes=None, status="ok", error=None) -> int
  list_spans(trace_id=None, job_id=None, kind=None, limit=200) -> list[dict]
  set_job_trace(job_id, trace_id, root_span_id) -> None

Rules:
- Validate `verdict` ∈ {approve, reject, abstain}; ValueError otherwise.
- record_span must never raise; on DB unavailable, return -1 and log to stderr.

Verification:
  python -c "
  from tools.kca import db
  syms = sorted(s for s in dir(db) if any(k in s for k in ('review','span','trace')))
  print(syms)
  "
  # With DB up: see acceptance criteria in M6-T001 spec.
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: symbols added, live smoke result.
```

---

## Loop Prompt 2 — Local-model layer (M6-T002)

```
Read:
1. docs/tasks/m6/M6-T002-local-model-layer.md
2. src/worker/routing.py  (M5 model routing)
3. src/worker/_types.py   (JobPolicy.model)
4. ADR-0004 (LiteLLM)

Goal: src/worker/local_model.py with:
  @dataclass LocalEndpoint(name, url, model, backend, api_key)
  load_endpoints() -> list[LocalEndpoint]   # iterate KCA_LOCAL_ENDPOINT_<n>_*
  probe(ep, timeout_s=2.0) -> {"ok", "models", "latency_ms", "error"}
  ProbeCache (TTL = KCA_LOCAL_PROBE_CACHE_TTL_S, default 60s)
  pick_endpoint(priority=None, cache=None) -> LocalEndpoint | None
  litellm_kwargs_for(ep) -> {"model", "api_base", "api_key",
                              "custom_llm_provider": "openai"}

Also draft docs/adr/0011-local-model-endpoints.md (numbered slots,
priority order, probe TTL, fallback).

Update src/worker/routing.py:
  MODEL_ROUTES["log_triage"] = "local"
  MODEL_ROUTES["summarise"]  = "local"
  When model_for(...) returns "local" the caller resolves via
  local_model.pick_endpoint(); when None → KCA_LOCAL_FALLBACK_MODEL or
  DEFAULT_MODEL.

New tools/kca/local.py with subcommands:
  kca local list  [--json]
  kca local probe [--name <ep>] [--json]
  kca local pick  [--json]
Register in kca.py.

Verification:
  # Default env.example has all endpoints commented out:
  python -c "from src.worker.local_model import load_endpoints; print(load_endpoints())"
    → []
  python tools/kca/kca.py local probe --json
    → {"ok_count": 0, "endpoints": []}
  python tools/kca/kca.py local pick --json
    → {"ok": false, "reason": "no endpoint available", "fallback": "claude-haiku-4-5"}
  # Then export 2 endpoint slots and re-run:
  KCA_LOCAL_ENDPOINT_0_NAME=test \
  KCA_LOCAL_ENDPOINT_0_URL=http://127.0.0.1:1/v1 \
  KCA_LOCAL_ENDPOINT_0_MODEL=x KCA_LOCAL_ENDPOINT_0_BACKEND=vllm \
  KCA_LOCAL_ENDPOINT_0_API_KEY=local \
    python tools/kca/kca.py local probe --json
    → endpoint with ok=false, error mentions connection refused
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: each verification + ADR present.
```

---

## Loop Prompt 3 — env.example update (M6-T003)

```
Read:
1. docs/tasks/m6/M6-T003-env-example-update.md
2. env.example (current state)

Goal: append the M6 block to env.example exactly as written in the task
spec — 4 commented-out endpoint blocks (snorlax-vllm, snorlax-ollama,
may-vllm, may-ollama) + uncommented routing knobs + reviewer + OTEL
sections.

Verification:
  grep -c "KCA_LOCAL_ENDPOINT_" env.example          → 20
  grep -c "^KCA_REVIEWER_"      env.example          → 5
  grep -c "^KCA_OTEL_"          env.example          → 4
  python -c "from src.worker.local_model import load_endpoints; print(load_endpoints())"
    → []  (all 4 endpoints are commented out in env.example)
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: greps and load_endpoints result.
```

---

## Loop Prompt 4 — Reviewer worker (M6-T004)

```
Read:
1. docs/tasks/m6/M6-T004-reviewer-worker.md
2. src/worker/worker.py (_handle_approval_required, AgentWorker.resume)
3. tools/kca/decisions.py
4. docs/adr/0006-configurable-approval-gates.md
5. tools/kca/db.py (create_review, find_review_for_op)

Goal: implement src/worker/reviewer.py with ReviewRequest, ReviewVerdict,
Reviewer class. Default reviewer model from KCA_REVIEWER_MODEL (default
claude-opus-4-7); dry_run=True returns deterministic approve.

Wire into AgentWorker._handle_approval_required:
  - _should_consult_reviewer(op) reads KCA_REVIEWER_TRIGGER_OPS.
  - If reviewer hasn't already run for (job_id, target_op):
      build ReviewRequest from list_job_events(job_id),
      call Reviewer(...).review(req),
      db.create_review(...).
    - verdict=approve → emit approval_resume event with
      event_data={"source":"reviewer","verdict":"approve"} and let the
      resume path consume the one-shot allowlist.
    - verdict=reject + KCA_REVIEWER_ESCALATE_REJECT=1 → fall through to
      existing human-decisions path with rationale.
    - verdict=reject + ESCALATE_REJECT=0 → job_status='failed',
      stop_reason='reviewer_reject'.
    - verdict=abstain → human-decisions path unchanged.

Also draft docs/adr/0012-multi-agent-review.md.

Update tools/kca/decisions.py:
  decisions list --include-reviews surfaces reviewer rows alongside
  human decisions.

Verification:
  python -c "
  from src.worker.reviewer import Reviewer
  v = Reviewer(dry_run=True).review_dry_run()
  assert v.verdict == 'approve', v
  print('PASS reviewer dry-run')
  "
  # Live: simulate a kaggle_submit gate (see M6-T004 acceptance criteria).
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: reviewer dry-run + ADR + escalation paths.
```

---

## Loop Prompt 5 — OTEL instrumentation (M6-T005)

```
Read:
1. docs/tasks/m6/M6-T005-otel-instrumentation.md
2. docs/adr/0007-otel-telemetry-strategy.md
3. src/worker/worker.py (run loop, _append_event)
4. tools/kca/db.py::record_span (from M6-T001)

Goal: src/worker/telemetry.py — TracerProvider configured once from
KCA_OTEL_EXPORTERS (console, sqlite, supabase). Three SpanProcessors:
  - ConsoleExporter: stderr "kind name duration_ms attrs"
  - SQLiteExporter: KCA_OTEL_SQLITE_PATH (default .agent/telemetry.sqlite)
  - SupabaseExporter: best-effort db.record_span(...).
Helpers: start_job_span, with_turn_span, with_tool_span, with_review_span,
with_probe_span, with_local_call_span.

Update AgentWorker.run to wrap job/turn/tool spans; assign trace_id +
root_span_id via db.set_job_trace(...).

Also draft docs/adr/0013-otel-console-sqlite-supabase.md.

pyproject.toml: add opentelemetry-sdk; opentelemetry-exporter-otlp is
optional (lazy import).

Verification:
  KCA_OTEL_ENABLED=1 KCA_OTEL_EXPORTERS=console \
    python scripts/run_job.py --prompt "p" --dry-run --json 2>otel.log
  grep -E "kind=job|kind=turn|kind=tool" otel.log | head -3
    → at least one of each

  KCA_OTEL_ENABLED=1 KCA_OTEL_EXPORTERS=sqlite \
  KCA_OTEL_SQLITE_PATH=$TMPDIR/m6.sqlite \
    python scripts/run_job.py --prompt "p" --dry-run --json
  sqlite3 $TMPDIR/m6.sqlite "select kind, count(*) from spans group by kind"
    → job=1, turn>=1, tool>=1

  KCA_OTEL_ENABLED=0 \
    python scripts/run_job.py --prompt "p" --dry-run --json 2>otel.log
  test ! -s otel.log
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: per-exporter results + ADR present.
```

---

## Loop Prompt 6 — Local-model job types (M6-T006)

```
Read:
1. docs/tasks/m6/M6-T006-local-model-job-types.md
2. src/worker/local_model.py (from M6-T002)
3. src/worker/routing.py (updated in M6-T002)
4. tools/kca/db.py::list_job_events (M5)

Goal: src/worker/triage.py with:
  triage_job_events(job_id, *, endpoint=None, max_input_chars=16000) -> dict
  summarise_text(text, *, max_input_chars=16000, endpoint=None) -> dict
Both LiteLLM-driven through local_model.litellm_kwargs_for(endpoint), with
a strict <=400 word summary prompt; fall back to KCA_LOCAL_FALLBACK_MODEL
when no endpoint is up (unless KCA_LOCAL_REQUIRE_LOCAL=1).

tools/kca/local.py additions:
  kca local triage --job-id <uuid> [--endpoint <name>] [--json]
  kca local summarise --file <path> [--endpoint <name>] [--json]

src/worker/reviewer.py: when event_trail > 8 KB, call
triage.summarise_text(event_trail) and substitute the summary into the
reviewer prompt.

Verification:
  # With all endpoints down + fallback enabled:
  KCA_LOCAL_REQUIRE_LOCAL=0 python tools/kca/kca.py local triage \
    --job-id 00000000-0000-0000-0000-000000000000 --json
    → ok=false (job not found) OR ok=true with endpoint="fallback:claude-haiku-4-5"
  # With strict local:
  KCA_LOCAL_REQUIRE_LOCAL=1 python tools/kca/kca.py local triage \
    --job-id 00000000-0000-0000-0000-000000000000 --json
    → ok=false, error="no endpoint"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: fallback + strict + reviewer integration.
```

---

## Loop Prompt 7 — `kca review` CLI (M6-T007)

```
Read:
1. docs/tasks/m6/M6-T007-kca-review-cli.md
2. tools/kca/decisions.py (subcommand pattern)
3. tools/kca/db.py (create_review, get_review, list_reviews)
4. src/worker/reviewer.py (from M6-T004)

Goal: tools/kca/review.py with list / show / run subcommands; register
in kca.py.

Verification:
  python tools/kca/kca.py review --help
    → lists list / show / run
  python tools/kca/kca.py review list --json
    → {"ok": true, "reviews": [], "db_warning": "..."}
  python tools/kca/kca.py review run --job-id <real-job> --dry-run --json
    → {"verdict": "approve", "reviewer_model": "<configured>", ...}
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: each subcommand.
```

---

## Loop Prompt 8 — TC-3 Spaceship Titanic (M6-T008)

```
Read:
1. docs/tasks/m6/M6-T008-tc3-spaceship-titanic.md
2. docs/testing/competition-test-cases.md (TC-1, TC-2 layout)
3. docs/milestones/m5/loop-prompts.md Loop Prompt 8 (TC-2 structure)

Setup: see task spec; baseline LogisticRegression + iteration
HistGradientBoostingClassifier on a synthetic make_classification dataset.

Reviewer-gate exercise: run a `--require-approval kaggle_submit --dry-run`
job; reviewer auto-approves; submission validated locally.

Validation (8 PASS/FAIL lines per the task spec):
  1. R1 + R2 meta.json + metrics.json
  2. submission.csv = 4277 lines
  3. header = PassengerId,Transported
  4. Transported ∈ {True, False}
  5. cv_auc(R2) > cv_auc(R1)
  6. agent_reviews has 1 row with verdict=approve, target_op=kaggle_submit
  7. kca decisions list --json → no pending items
  8. pytest 0 failures

Output "TC-3 SPACESHIP-TITANIC PASS" if all 8 pass.

Do NOT git add or commit. Report: all 8 checks.
```

---

## Loop Prompt 9 — M6 smoke tests (M6-T009)

```
Read:
1. docs/tasks/m6/M6-T009-m6-smoke-tests.md
2. tests/test_m5_smoke.py (style + env-scrub helpers)
3. src/worker/local_model.py, reviewer.py, telemetry.py, triage.py
4. tools/kca/local.py, review.py

Goal: tests/test_m6_smoke.py with 12–14 tests; all pass without local
endpoints, ANTHROPIC_API_KEY, KAGGLE_KEY, or SUPABASE_DB_URL (one DB test
skips cleanly when no DB).

Required tests (numbered list in M6-T009 spec; copy the names verbatim).

Verification:
  python -m pytest tests/test_m6_smoke.py -v   → all pass (1 SKIP no DB)
  python -m pytest tests/ -v                    → 0 failures

Do NOT git add or commit. Report: count + per-test status.
```

---

## Loop Prompt 10 — M6 exit criteria (M6-T010)

```
Goal: verify ALL M6 exit criteria. Gate before M6 is declared complete.

Run each and report PASS/FAIL/SKIP:

Schema + DB (requires SUPABASE_DB_URL):
 1. Migration 0006 idempotent (apply twice)
 2. agent_reviews table + columns
 3. agent_telemetry_spans table + columns
 4. agent_jobs has otel_trace_id + otel_root_span_id

Local-model layer:
 5. kca local list --json with default env.example → 0 endpoints
 6. kca local probe --json reports per-endpoint ok / latency when set
 7. kca local pick --json picks highest-priority reachable endpoint, or
    fallback when none
 8. routing returns served_model when reachable, fallback otherwise

Reviewer:
 9. kca review --help lists list / show / run
10. Reviewer(dry_run=True).review(...) returns verdict=approve
11. Reviewer gate fires on kaggle_submit + creates agent_reviews row
12. Reject path: escalates or fails depending on KCA_REVIEWER_ESCALATE_REJECT

OTEL:
13. KCA_OTEL_EXPORTERS=console: stderr span lines emitted
14. KCA_OTEL_EXPORTERS=sqlite: SQLite file has rows
15. KCA_OTEL_EXPORTERS=supabase + DB up: agent_telemetry_spans has rows
16. KCA_OTEL_ENABLED=0 → no output

TC-3:
17. TC-3 Spaceship Titanic 8/8 PASS

Tests:
18. python -m pytest tests/ -v (no DB) — 0 failures
19. python -m pytest tests/ -v (live DB) — 0 failures

Output:
  Print the validation matrix.
  If all non-SKIP pass: output "M6 EXIT CRITERIA MET".
  Create docs/milestones/m6/final-review.md (mirror docs/milestones/m5/final-review.md) with
  the M7 follow-ups list from the task spec.

Do NOT git add or commit. Report: full matrix, final status.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
pip install opentelemetry-sdk
pip install -e .   # picks up new optional deps if any

# DB DSN (M5-confirmed)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# Local endpoints — uncomment 0 + 1 (snorlax) in env.example, or:
export KCA_LOCAL_ENDPOINT_0_NAME=snorlax-vllm
export KCA_LOCAL_ENDPOINT_0_URL=http://192.168.18.66:8000/v1
export KCA_LOCAL_ENDPOINT_0_MODEL=rtx4090
export KCA_LOCAL_ENDPOINT_0_BACKEND=vllm
export KCA_LOCAL_ENDPOINT_0_API_KEY=local

# Verify M6 base
kca local probe --json     # snorlax should be ok; may will time out
kca review --help          # lists list / show / run
```

### Settings additions for autonomous M6 loop

Add to `.claude/settings.json` allow-list (extend M5):

```json
"Bash(kca local*)",
"Bash(kca review*)",
"Bash(python -m vllm*)",
"Bash(ollama *)",
"Bash(sqlite3 *)"
```

### Sandbox bypass

Two operations need `dangerouslyDisableSandbox: true` on every call:

1. DB calls — `psql`, `pytest` against `SUPABASE_DB_URL`, any `kca`
   subcommand that reaches Supabase.
2. Local-endpoint calls — `kca local probe`, `kca local triage`, and any
   worker job whose `model_for(...)` resolves to a `192.168.18.x` host.

Cloud LLM calls (Anthropic / OpenAI) still go through the proxy and stay
inside the sandbox.

### Full autonomous run

```bash
claude "
Execute M6 Loop Prompts 0 through 10 from docs/milestones/m6/loop-prompts.md in sequence.
Each prompt's acceptance checks must pass before moving to the next.
On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push.
Do not call the real Anthropic API or Kaggle API.
Use --dry-run for all worker tests.
For DB validation use SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
  (container IP; refresh via 'docker inspect supabase-db' if it changes).
DB and local-endpoint calls require dangerouslyDisableSandbox=true.
Report PASS/FAIL for each prompt's verification step inline.
"
```

### Closeout
让我们先review 下面的问题, 调整完所有 milestones 之后, 在执行 M7 的计划规划
- 每个milestone final review 之后, 标注为完成时别忘了更新PROJECT_STATE.md, README.md (Current milestone section), docs/milestones/README.md 等文档
- 因为 KCA 平台开始主要是 personal use, local first, 所以目前不需要 cloud deployment; 不过还是请添加 INSTALL.md 或者在 README.md 中添加 Install/Configure 部分, 描述 KCA 平台ready时如何在本地安装, 配置和运行; 并预留以后在 AWS/GCP 上部署的部分
- source of truth 是 GitHub repo + Claude Code + CI + Supabase migrations, Lovable 暂时不用, 请更新docs/milestones/README.md 及相关文档来继续在 Claude Code 中开发UI
- KCA Claude Code like CLI: 请将下面的需求添加到已有或者新增一个 milestone, details refer to temp/kca_cli.md

