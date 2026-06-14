# M6-T005: OTEL instrumentation (console + SQLite + Supabase)

## Milestone
M6.

## Goal
Wire OpenTelemetry spans through the worker per ADR-0007. Spans cover the
job, each turn, each tool call, each LLM call, each reviewer run, and each
local-endpoint probe. Three exporters: console (dev), SQLite (queryable
local history), and Supabase (`agent_telemetry_spans` from T000).

## Read first
1. `docs/adr/0007-otel-telemetry-strategy.md`.
2. `src/worker/worker.py` (`run` loop, `_append_event`).
3. `src/worker/budget.py` (per-turn cost / latency).
4. `docs/tasks/m6/M6-T000-migration-0006-reviews-spans.md`.
5. ADR-0013 — draft alongside as
   `docs/adr/0013-otel-console-sqlite-supabase.md`.

## Files

### New: `src/worker/telemetry.py`
- Imports `opentelemetry.sdk.trace`, configures a `TracerProvider` once.
- Reads `KCA_OTEL_EXPORTERS` (comma list); registers a `BatchSpanProcessor`
  for each.
- `ConsoleExporter`: stderr, one line per span: `kind name duration_ms attrs`.
- `SQLiteExporter`: appends to `KCA_OTEL_SQLITE_PATH` (default
  `.agent/telemetry.sqlite`). Schema mirrors `agent_telemetry_spans` plus
  a `created_at` autotimestamp.
- `SupabaseExporter`: best-effort `db.record_span(...)`; failures log to
  stderr and never raise into the worker.
- Helpers: `start_job_span(job_id, prompt) -> Span`,
  `with_turn_span(turn_n) -> contextmanager`,
  `with_tool_span(tool, input) -> contextmanager`,
  `with_review_span(target_op) -> contextmanager`,
  `with_probe_span(endpoint_name) -> contextmanager`.

### Update: `src/worker/worker.py`
- Wrap the entire `AgentWorker.run` body in `start_job_span` /
  `end_span`; assign `trace_id` + `root_span_id` to the job row via
  `db.set_job_trace(...)`.
- Each turn opens `with_turn_span(budget.turns)`; tool dispatch opens
  `with_tool_span(tc.function.name, tool_input)`. LiteLLM call latency is
  recorded as an attribute on the turn span.
- Reviewer + local-endpoint probe paths use the matching helpers from
  `telemetry.py`.

### Update: `pyproject.toml`
Add `opentelemetry-sdk` and `opentelemetry-exporter-otlp` to the runtime
deps (the OTLP exporter is optional; we import it lazily inside an
otlp-enabled branch so the install doesn't grow unnecessarily).

## Acceptance criteria
- With `KCA_OTEL_ENABLED=1 KCA_OTEL_EXPORTERS=console`, a dry-run job
  prints `job/turn/tool` lines to stderr.
- With `KCA_OTEL_EXPORTERS=sqlite`, the SQLite file exists after the run
  and has rows where `kind in ('job','turn','tool')`.
- With `KCA_OTEL_EXPORTERS=supabase` and DB up, `agent_telemetry_spans`
  has matching rows.
- With `KCA_OTEL_ENABLED=0` the worker has zero span output and zero new
  DB rows.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 30 turns. If the OTEL SDK install pulls in a transitive dep
that breaks an existing test, pin to the last-known-working version and
note the pin in `pyproject.toml`.
