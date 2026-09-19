# ADR-0007: Observability — OpenTelemetry and telemetry strategy

Status: accepted (strategy); implementation deferred to M3/M4  
Date: 2026-05-19  
Decided in: `docs/meeting-notes/2026-05-19-r1.md`

---

## Context

The platform runs multi-turn agent jobs that call LLMs, execute tools, read/write files, and interact with Kaggle APIs. Without structured observability:
- It is hard to know which tool calls are slow.
- Cost per job type is estimated, not measured.
- Performance regressions across platform versions are invisible.
- Comparing model providers (Claude vs GPT-4o vs local) requires manual log parsing.

## Decision

Adopt **OpenTelemetry (OTEL)** as the instrumentation standard for the platform.

### What to instrument

| Signal | Granularity | Examples |
|---|---|---|
| Traces | Per job | One root span per `AgentWorker.run()` |
| Spans | Per turn | `agent.turn` span: turn_number, stop_reason, input/output tokens |
| Spans | Per tool call | `tool.read_file`, `tool.run_bash`, etc. |
| Metrics | Per job | `job.turns_used`, `job.cost_usd`, `job.duration_s` |
| Metrics | Per tool | `tool.latency_ms`, `tool.error_rate` |
| Logs | Per event | Structured log attached to each span |

### Key attributes to capture on every span

```
job.id
job.type
job.model
competition.slug
session.id
tool.name
tool.side_effect
turn.number
turn.input_tokens
turn.output_tokens
turn.cost_usd
provider.name    (anthropic | openai | ollama | ...)
```

### LiteLLM integration

LiteLLM supports OTEL natively via its callback system:

```python
import litellm
litellm.success_callback = ["otel"]
litellm.failure_callback = ["otel"]
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
```

This automatically exports per-call spans with token counts and cost estimates.

### Backend options

| Option | When to use | Notes |
|---|---|---|
| Local Jaeger (Docker) | Development, debugging | Free, easy; `docker run jaegertracing/all-in-one` |
| Grafana + Tempo | Production self-hosted | Pairs with existing Grafana dashboards |
| Honeycomb.io | Production SaaS | Free tier up to 20M events/month |
| Supabase logs | Light fallback | Already available; no OTEL but queryable |

For M3/M4: start with local Jaeger. Defer SaaS selection to M7.

### Structured event log (no-OTEL fallback)

Before OTEL is wired up, `agent_job_events` in Postgres serves as a structured audit trail. Every turn, tool call, and result is already recorded there. OTEL adds real-time visibility and cross-job aggregation on top of this.

## Implementation plan

### M3 (minimal)
- Add OTEL spans to `AgentWorker.run()`: one root span, one child span per turn.
- Enable LiteLLM OTEL callback if `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- No hard dependency; graceful no-op if OTEL SDK not installed.

```python
try:
    from opentelemetry import trace
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
```

### M4
- Add spans to `ToolExecutor.execute()`: one span per tool call.
- Add `job.cost_usd` and `job.turns_used` as OTEL metrics at job end.
- Provide a `make otel-up` target (Jaeger via Docker Compose).

### M5+
- Add browser/research tool spans.
- Dashboard: cost per job_type, model comparison, slow-tool P95 latency.
- Regression comparison: compare average CV improvement per job type across platform versions.

## Use cases enabled by OTEL

1. **Model comparison:** same job prompt, different models → compare cost, turns, final CV score.
2. **Tool latency profiling:** identify if `kaggle watch` polling dominates wall time.
3. **Cost forecasting:** actual vs estimated cost per job type → improve budget defaults.
4. **Platform regression:** new platform version → run the 4 test competitions → compare trace metrics.
5. **Debugging paused jobs:** trace shows exactly which tool triggered ApprovalRequired.

## Dependencies

- `opentelemetry-api` + `opentelemetry-sdk` + `opentelemetry-exporter-otlp`
- Or: rely entirely on LiteLLM's built-in OTEL callback (no direct OTEL import needed in worker)

The LiteLLM OTEL callback covers the LLM call span. Manual spans are needed for tool execution and the overall job root span.

## Consequences

- **Positive:** End-to-end visibility without changing the core worker logic significantly.
- **Positive:** LiteLLM handles the LLM-call spans automatically.
- **Positive:** Deferred to M3/M4 — does not block M3 MVP.
- **Negative:** Adds `opentelemetry-*` packages (~15 transitive deps); acceptable.
- **Mitigation:** Graceful no-op if OTEL env vars not set; zero cost for users who skip it.
