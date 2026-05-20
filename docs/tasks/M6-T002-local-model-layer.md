# M6-T002: Local-model endpoint layer + availability probe

## Milestone
M6.

## Goal
Add a provider abstraction over the user's local LLM endpoints (vLLM /
Ollama on `snorlax` and `may`) so the worker can dispatch summarisation
and triage jobs to them with a cheap probe-first availability check, and
fall back to a cloud model when none are reachable.

## Read first
1. `src/worker/routing.py` (M5 model routing).
2. `src/worker/_types.py` (`JobPolicy.model`).
3. ADR-0004 (LiteLLM provider layer).
4. ADR-0011 — will be drafted alongside this task as
   `docs/adr/0011-local-model-endpoints.md`.

## Files

### New: `src/worker/local_model.py`

```python
@dataclass
class LocalEndpoint:
    name: str               # snorlax-vllm, may-ollama, ...
    url: str                # http://host:port/v1
    model: str              # served model id
    backend: str            # vllm | ollama
    api_key: str            # "local" works for both

def load_endpoints() -> list[LocalEndpoint]:
    """Read KCA_LOCAL_ENDPOINT_<n>_* env vars; return list ordered by N."""

def probe(endpoint: LocalEndpoint, *, timeout_s: float = 2.0) -> dict:
    """GET {url}/models. Return {"ok": bool, "models": [...], "latency_ms": ..., "error": ...}."""

class ProbeCache:
    """In-process TTL cache keyed by endpoint name; TTL from
    KCA_LOCAL_PROBE_CACHE_TTL_S (default 60)."""

def pick_endpoint(priority: list[str] | None = None,
                  cache: ProbeCache | None = None) -> LocalEndpoint | None:
    """Walk priority list, return first endpoint whose cached probe is ok.
    None if all are down or no endpoints configured."""

def litellm_kwargs_for(ep: LocalEndpoint) -> dict:
    """Return {model, api_base, api_key, custom_llm_provider='openai'} for
    LiteLLM completion()."""
```

### Update: `src/worker/routing.py`
- Add `"log_triage"` and `"summarise"` keys to `MODEL_ROUTES`; their value
  is the sentinel `"local"`.
- When `model_for(job_type)` returns `"local"`, resolve at call site via
  `local_model.pick_endpoint()` → real model id; if no endpoint is up,
  fall back to `os.environ["KCA_LOCAL_FALLBACK_MODEL"]` (default
  `claude-haiku-4-5`).

### New: `tools/kca/local.py`
- `kca local list` — print configured endpoints (no probe).
- `kca local probe [--name <ep>]` — run probes, print JSON
  `{ok_count, endpoints: [...]}`.
- `kca local pick` — print the endpoint that would be chosen now, or
  `{ok: false, reason: "no endpoint available", fallback: <model>}`.
- All subcommands `--json`.

### Update: `tools/kca/kca.py`
Register the `local` subparser.

## Acceptance criteria
- `python -c "from src.worker.local_model import load_endpoints; print([e.name for e in load_endpoints()])"`
  with the env example loaded prints `['snorlax-vllm', 'snorlax-ollama', 'may-vllm', 'may-ollama']`.
- `kca local probe --json` returns ok per endpoint with latency; unreachable
  hosts show `ok=false` with a short error (timeout / DNS).
- `kca local pick --json` returns the first reachable endpoint by priority.
- Routing returns `"rtx4090"` for `job_type=summarise` when snorlax-vllm
  is the first reachable endpoint, and `claude-haiku-4-5` when none are.
- `python -m pytest tests/ -v` — 0 failures (smoke covered in T009).

## Stop condition
Stop after 25 turns. If `KCA_LOCAL_ENDPOINTS` slot parsing gets ambiguous,
just iterate `KCA_LOCAL_ENDPOINT_<n>_NAME` for `n=0..9` and stop at the
first gap.
