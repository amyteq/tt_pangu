# ADR-0013: OTEL exporters — console, SQLite, Supabase

## Status
Accepted (M6).

## Context
ADR-0007 picked OpenTelemetry as the telemetry strategy: spans cover the job, each turn, each tool call, each LLM call, each reviewer run, and each local-endpoint probe. M6 needs the concrete exporter wiring.

We have three different consumers with three very different latency budgets:

- **Developers running a one-shot job** want spans printed inline so they can see what just happened without leaving the terminal.
- **Local audit / debugging across recent jobs** wants a queryable store that doesn't depend on a live Postgres connection.
- **Multi-host project memory** needs the same spans in Supabase alongside `agent_jobs` and `agent_reviews` so cross-job queries work.

## Decision
`src/worker/telemetry.py` ships three exporters; `KCA_OTEL_EXPORTERS` is a comma-separated list and any subset can be enabled.

1. **Console** — stderr line per finished span: `kind=<kind> name=<name> duration_ms=<n> status=<ok|error> attrs={…}`. Cheap, no IO beyond stderr, used by `--dry-run` and local CLI work.
2. **SQLite** — `KCA_OTEL_SQLITE_PATH` (default `.agent/telemetry.sqlite`). Schema mirrors `agent_telemetry_spans` plus a `created_at` autotimestamp; per-trace and per-kind indexes. No DB connection required; survives across runs.
3. **Supabase** — best-effort `db.record_span(...)` for each span. The helper from M6-T001 swallows DB-unavailable errors and returns `-1`, so a down Postgres cannot break the worker. The match with the SQLite schema is intentional: any local debugging query can run against either store with the same shape.

The full `opentelemetry-sdk` install is not required by this milestone. We ship a minimal Tracer/Span pair with the small slice of the OTEL API we use (start_span, end, attributes, context manager). Switching to the SDK later is a drop-in because the exporter contract — kind, name, attributes, started_at, ended_at, status — is identical. Adding `opentelemetry-sdk` and `opentelemetry-exporter-otlp` to `pyproject.toml` is deferred to M7, where we expect a real cluster-wide collector.

`KCA_OTEL_ENABLED=0` short-circuits all three exporters. The tracer still creates Span objects but `_export` is a no-op, so callers can keep their `with tracer.span(...)` blocks unconditional.

## Consequences
- Three exporters cover dev, local audit, and project memory without forcing a heavy dep on every install.
- Switching to the real OTEL SDK later does not change call sites.
- The SQLite exporter creates `.agent/` lazily; CI runs that don't set `KCA_OTEL_EXPORTERS` write nothing to disk.
- The Supabase exporter is best-effort; spans that fail to write are logged once to stderr but never crash the worker.
