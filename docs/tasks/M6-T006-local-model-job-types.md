# M6-T006: Wire local-model job types into the worker

## Milestone
M6.

## Goal
Use the local-endpoint layer (T002) for two new job types — `log_triage`
and `summarise` — so long `agent_job_events` / `tool_result` traces are
compressed by the local model before they reach Opus/Sonnet, and provide a
CLI surface (`kca local triage --job-id <uuid>`) that fronts the worker.

## Read first
1. `src/worker/local_model.py` (from T002).
2. `src/worker/routing.py` updates from T002.
3. `tools/kca/db.py::list_job_events` (M5).
4. `src/worker/_types.py` (`JobPolicy`).

## Files

### New: `src/worker/triage.py`
```python
def triage_job_events(job_id: str, *, endpoint=None,
                       max_input_chars: int = 16000) -> dict:
    """Summarise a job's event trail using a local model.

    Behaviour:
      1. db.list_job_events(job_id) → trim to max_input_chars
      2. local_model.pick_endpoint() (or `endpoint` arg)
      3. LiteLLM completion with a strict prompt: 'Summarise in <=400 words'
      4. Return {"ok": bool, "summary": str, "endpoint": name,
                 "model": served_model, "cost_usd": <est>,
                 "span_id": <otel id from telemetry.with_local_call_span>}
      5. On no endpoint reachable + KCA_LOCAL_REQUIRE_LOCAL=1 → {"ok": false,
         "error": "no endpoint"}; else fall back to KCA_LOCAL_FALLBACK_MODEL.
    """

def summarise_text(text: str, *, max_input_chars: int = 16000,
                    endpoint=None) -> dict:
    """Generic text summariser — used by reviewer to compress long traces."""
```

### Update: `tools/kca/local.py`
Add subcommands:
- `kca local triage --job-id <uuid> [--endpoint <name>] [--json]`
- `kca local summarise --file <path> [--endpoint <name>] [--json]`

### Update: `src/worker/reviewer.py` (from T004)
Before invoking the reviewer model, if the event trail exceeds 8 KB,
call `triage.summarise_text(event_trail)` and substitute the summary into
the reviewer prompt.

## Acceptance criteria
- `kca local triage --job-id <uuid> --json` (with at least one local
  endpoint up) returns `{ok: true, summary: ..., endpoint: ...}` and
  records a `local_call` span in telemetry.
- With every local endpoint unreachable and
  `KCA_LOCAL_REQUIRE_LOCAL=0`, the same command returns `{ok: true,
  summary: ..., endpoint: "fallback:claude-haiku-4-5"}`.
- With `KCA_LOCAL_REQUIRE_LOCAL=1` and no endpoint up:
  `{ok: false, error: "no endpoint"}` and exit code 1.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 25 turns. If LiteLLM rejects the model id for vLLM (
`openai/<served_model>` is the working form), surface the exact LiteLLM
error in the test output rather than silently routing to the fallback.
