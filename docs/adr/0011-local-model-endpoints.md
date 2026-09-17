# ADR-0011: Local LLM endpoints

## Status
Accepted (M6).

## Context
We run two LAN GPU hosts (`snorlax` RTX 4090, `may` RTX 3090) with OpenAI-compatible vLLM or Ollama servers. Some M6 job types (`log_triage`, `summarise`) are routinely cheap and high-volume; routing them through Anthropic/OpenAI burns cash and adds latency. We want a thin layer that discovers configured local endpoints, probes their health on a TTL, and picks the highest-priority reachable one — with a graceful cloud fallback.

## Decision
Add `src/worker/local_model.py` with:

- `LocalEndpoint(name, url, model, backend, api_key)` — frozen dataclass.
- `load_endpoints()` — iterates `KCA_LOCAL_ENDPOINT_<n>_*` slots `0..9`, stopping at the first slot without a `_NAME`. Order is the configured slot order, which serves as the implicit priority.
- `probe(endpoint, timeout_s=2.0)` — `GET {url}/models` with bearer auth; returns `{ok, models, latency_ms, error}`. Never raises.
- `ProbeCache(ttl_s=KCA_LOCAL_PROBE_CACHE_TTL_S, default 60s)` — in-process, per-endpoint TTL cache so a job's many `pick_endpoint()` calls collapse into one probe.
- `pick_endpoint(priority, cache)` — walks the priority list and returns the first endpoint whose cached probe is `ok`. Priority resolution: explicit arg > `KCA_LOCAL_PRIORITY_ORDER` env > configured load order. Returns `None` when none are up.
- `litellm_kwargs_for(ep)` — `{model, api_base, api_key, custom_llm_provider: 'openai'}` for LiteLLM.

Routing in `src/worker/routing.py` adds `log_triage` and `summarise` → `"local"`. The sentinel string `"local"` instructs callers to resolve via `local_model.pick_endpoint()`, with `KCA_LOCAL_FALLBACK_MODEL` (default `claude-haiku-4-5`) when no endpoint is reachable. Setting `KCA_LOCAL_REQUIRE_LOCAL=1` flips this from "fall back" to "refuse".

## Consequences
- LAN endpoints stay opt-in; an empty configuration is a valid state.
- Probes are short (2s default) so a down host can't stall the worker.
- The fallback path keeps job types working even when both GPU hosts are off, at the cost of a cloud round-trip.
- Sandbox reach: 192.168.x hosts aren't in the proxy allow-list, so `kca local probe` and any worker turn that picks a local endpoint must run with `dangerouslyDisableSandbox=true`.
