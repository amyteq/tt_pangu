"""Local LLM endpoint layer (M6-T002 / ADR-0011).

Provides a tiny provider abstraction over LAN-hosted vLLM / Ollama
servers. The layer is opt-in: configuring zero endpoints in the
environment yields an empty list and a None pick, which the caller
treats as "fall back to the cloud default".
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


_DEFAULT_PRIORITY_ENV = "KCA_LOCAL_PRIORITY_ORDER"
_PROBE_TIMEOUT_ENV = "KCA_LOCAL_PROBE_TIMEOUT_S"
_CACHE_TTL_ENV = "KCA_LOCAL_PROBE_CACHE_TTL_S"
_FALLBACK_MODEL_ENV = "KCA_LOCAL_FALLBACK_MODEL"
_REQUIRE_LOCAL_ENV = "KCA_LOCAL_REQUIRE_LOCAL"

_MAX_SLOT = 10  # KCA_LOCAL_ENDPOINT_0..9


@dataclass(frozen=True)
class LocalEndpoint:
    name: str
    url: str
    model: str
    backend: str
    api_key: str


def load_endpoints() -> list[LocalEndpoint]:
    """Iterate KCA_LOCAL_ENDPOINT_<n>_* slots until the first gap."""
    out: list[LocalEndpoint] = []
    for n in range(_MAX_SLOT):
        name = os.environ.get(f"KCA_LOCAL_ENDPOINT_{n}_NAME")
        if not name:
            break
        url = os.environ.get(f"KCA_LOCAL_ENDPOINT_{n}_URL", "")
        model = os.environ.get(f"KCA_LOCAL_ENDPOINT_{n}_MODEL", "")
        backend = os.environ.get(f"KCA_LOCAL_ENDPOINT_{n}_BACKEND", "vllm")
        api_key = os.environ.get(f"KCA_LOCAL_ENDPOINT_{n}_API_KEY", "local")
        out.append(
            LocalEndpoint(
                name=name,
                url=url,
                model=model,
                backend=backend,
                api_key=api_key,
            )
        )
    return out


def probe(endpoint: LocalEndpoint, *, timeout_s: float | None = None) -> dict:
    """Probe an endpoint's OpenAI-compatible /models route. Never raises."""
    if timeout_s is None:
        try:
            timeout_s = float(os.environ.get(_PROBE_TIMEOUT_ENV, "2"))
        except ValueError:
            timeout_s = 2.0
    url = endpoint.url.rstrip("/") + "/models"
    started = time.monotonic()
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {endpoint.api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        import json as _json

        try:
            payload = _json.loads(body)
            models = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict)]
        except Exception:
            models = []
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "name": endpoint.name,
            "models": models,
            "latency_ms": latency_ms,
            "error": None,
        }
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "name": endpoint.name,
            "models": [],
            "latency_ms": latency_ms,
            "error": f"http {exc.code}",
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "name": endpoint.name,
            "models": [],
            "latency_ms": latency_ms,
            "error": str(exc),
        }


class ProbeCache:
    """In-process TTL cache keyed by endpoint name."""

    def __init__(self, ttl_s: float | None = None) -> None:
        if ttl_s is None:
            try:
                ttl_s = float(os.environ.get(_CACHE_TTL_ENV, "60"))
            except ValueError:
                ttl_s = 60.0
        self.ttl_s = ttl_s
        self._entries: dict[str, tuple[float, dict]] = {}

    def get(self, endpoint: LocalEndpoint) -> dict:
        now = time.monotonic()
        cached = self._entries.get(endpoint.name)
        if cached and (now - cached[0]) < self.ttl_s:
            return cached[1]
        result = probe(endpoint)
        self._entries[endpoint.name] = (now, result)
        return result

    def invalidate(self, name: str | None = None) -> None:
        if name is None:
            self._entries.clear()
        else:
            self._entries.pop(name, None)


def _priority_order() -> list[str]:
    raw = os.environ.get(_DEFAULT_PRIORITY_ENV, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def pick_endpoint(
    priority: list[str] | None = None,
    cache: ProbeCache | None = None,
) -> LocalEndpoint | None:
    """Return the highest-priority reachable endpoint, or None.

    Priority order: explicit ``priority`` arg > KCA_LOCAL_PRIORITY_ORDER env >
    configured order from load_endpoints().
    """
    endpoints = load_endpoints()
    if not endpoints:
        return None
    by_name = {ep.name: ep for ep in endpoints}
    order_names = priority if priority is not None else _priority_order()
    if order_names:
        ordered = [by_name[n] for n in order_names if n in by_name]
        # Append any configured endpoints not mentioned in priority list.
        for ep in endpoints:
            if ep.name not in order_names:
                ordered.append(ep)
    else:
        ordered = list(endpoints)
    cache = cache or ProbeCache()
    for ep in ordered:
        result = cache.get(ep)
        if result.get("ok"):
            return ep
    return None


def litellm_kwargs_for(ep: LocalEndpoint) -> dict:
    """Build the kwargs dict passed to litellm.completion(...)."""
    return {
        "model": ep.model,
        "api_base": ep.url,
        "api_key": ep.api_key,
        "custom_llm_provider": "openai",
    }


def fallback_model() -> str:
    return os.environ.get(_FALLBACK_MODEL_ENV, "claude-haiku-4-5")


def require_local() -> bool:
    return os.environ.get(_REQUIRE_LOCAL_ENV, "0").strip() == "1"
