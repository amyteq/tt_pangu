"""Route enum + resolver for the M13 eval harness.

Five canonical routes:

- ``mocked`` — ``litellm.mock_completion`` with fixture text. Allowed
  in any mode (no remote, no key, no budget).
- ``local_vllm`` — LAN-hosted vLLM / Ollama via
  ``src/worker/local_model.py``. Needs the LAN-host sandbox bypass
  but NOT ``KCA_ALLOW_REMOTE``.
- ``claude_haiku_4_5`` — ``anthropic/claude-haiku-4-5-20251001`` via
  ``litellm``. Needs ``KCA_ALLOW_REMOTE=1`` AND ``ANTHROPIC_API_KEY``.
- ``claude_sonnet_4_6`` — ``anthropic/claude-sonnet-4-6`` via
  ``litellm``. Same gating as Haiku.
- ``gpt_4o`` — ``openai/gpt-4o`` via ``litellm``. Needs
  ``KCA_ALLOW_REMOTE=1`` AND ``OPENAI_API_KEY``.

``resolve(route, *, allow_remote, env) -> RouteSpec`` is the single
entry point. It NEVER reads an API key, NEVER probes a live endpoint,
NEVER makes a network call. The local-vllm endpoint probe is a
separate ``probe_local_vllm()`` helper so the refusal layer can run
BEFORE any LAN write.

The resolver returns:

- ``ok=True`` for routes that are usable in the given environment.
- ``ok=False`` with a stable ``error`` code:
  - ``REMOTE_NOT_APPROVED`` — paid route without ``KCA_ALLOW_REMOTE=1``.
  - ``MISSING_API_KEY:<KEY_NAME>`` — paid route, allow_remote=True,
    but the corresponding API key env var is missing.
  - ``NO_LIVE_LOCAL_ENDPOINT`` — only emitted by ``probe_local_vllm``,
    NOT by ``resolve``. ``resolve`` returns ``ok=True`` for local_vllm
    so the caller can decide whether to probe.

Cost coefficients are recorded but not used by ``resolve`` itself;
the per-suite runner and the route-compare driver consult them when
maintaining the per-route cost ledger.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Route table.
# ---------------------------------------------------------------------------

# Canonical route keys. Ordered: cheap → expensive, mocked first.
ROUTE_KEYS: tuple[str, ...] = (
    "mocked",
    "local_vllm",
    "claude_haiku_4_5",
    "claude_sonnet_4_6",
    "gpt_4o",
)

# Per-route metadata. ``provider_model`` is the litellm-style model id.
# ``requires_remote`` triggers the REMOTE_NOT_APPROVED gate.
# ``api_key_env`` is the env var name the resolver checks.
# Cost coefficients are USD per 1M tokens (approximate as of M13;
# baselined values, NOT a SLA — the harness uses litellm's own cost
# tracking when available, and falls back to these defaults).
ROUTE_TABLE: dict[str, dict[str, Any]] = {
    "mocked": {
        "provider_model": "mock/mocked",
        "requires_remote": False,
        "requires_local_lan": False,
        "api_key_env": None,
        "cost_per_1m_input_usd": 0.0,
        "cost_per_1m_output_usd": 0.0,
        "description": "litellm.mock_completion with fixture text",
    },
    "local_vllm": {
        "provider_model": "openai/local-vllm",  # actual model resolved at probe
        "requires_remote": False,
        "requires_local_lan": True,
        "api_key_env": None,
        "cost_per_1m_input_usd": 0.0,
        "cost_per_1m_output_usd": 0.0,
        "description": "LAN-hosted vLLM / Ollama via OpenAI-compatible API",
    },
    "claude_haiku_4_5": {
        "provider_model": "anthropic/claude-haiku-4-5-20251001",
        "requires_remote": True,
        "requires_local_lan": False,
        "api_key_env": "ANTHROPIC_API_KEY",
        "cost_per_1m_input_usd": 1.00,
        "cost_per_1m_output_usd": 5.00,
        "description": "Anthropic Claude Haiku 4.5 via litellm",
    },
    "claude_sonnet_4_6": {
        "provider_model": "anthropic/claude-sonnet-4-6",
        "requires_remote": True,
        "requires_local_lan": False,
        "api_key_env": "ANTHROPIC_API_KEY",
        "cost_per_1m_input_usd": 3.00,
        "cost_per_1m_output_usd": 15.00,
        "description": "Anthropic Claude Sonnet 4.6 via litellm",
    },
    "gpt_4o": {
        "provider_model": "openai/gpt-4o",
        "requires_remote": True,
        "requires_local_lan": False,
        "api_key_env": "OPENAI_API_KEY",
        "cost_per_1m_input_usd": 2.50,
        "cost_per_1m_output_usd": 10.00,
        "description": "OpenAI GPT-4o via litellm",
    },
}


# ---------------------------------------------------------------------------
# RouteSpec dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteSpec:
    """Result of ``resolve(route, ...)``.

    ``ok`` distinguishes "usable" (True) from "refused" (False).
    The downstream caller MUST check ``ok`` before attempting any
    network or model call. ``error`` carries a stable refusal code.
    """

    route: str
    ok: bool
    provider_model: str
    requires_remote: bool
    requires_local_lan: bool
    api_key_env: str | None
    cost_per_1m_input_usd: float
    cost_per_1m_output_usd: float
    description: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "ok": self.ok,
            "provider_model": self.provider_model,
            "requires_remote": self.requires_remote,
            "requires_local_lan": self.requires_local_lan,
            "api_key_env": self.api_key_env,
            "cost_per_1m_input_usd": self.cost_per_1m_input_usd,
            "cost_per_1m_output_usd": self.cost_per_1m_output_usd,
            "description": self.description,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Resolver.
# ---------------------------------------------------------------------------


class UnknownRouteError(ValueError):
    """Raised when ``route`` is not in ROUTE_KEYS."""


def resolve(
    route: str,
    *,
    allow_remote: bool | None = None,
    env: dict[str, str] | None = None,
) -> RouteSpec:
    """Resolve a route key against the current environment.

    ``allow_remote`` defaults to ``env.get("KCA_ALLOW_REMOTE") == "1"``.
    ``env`` defaults to ``os.environ``.

    Refusal logic (in order):

    1. Unknown route key → raises ``UnknownRouteError``.
    2. Remote-required route + ``allow_remote=False`` → ``ok=False``
       with ``error="REMOTE_NOT_APPROVED"``. **The API key env is NOT
       read here.** This guarantees the refusal fires before any
       secret is touched.
    3. Remote-required route + ``allow_remote=True`` + API key missing
       → ``ok=False`` with ``error="MISSING_API_KEY:<KEY_NAME>"``.
    4. Otherwise → ``ok=True``.

    The ``local_vllm`` route is NOT probed here; ``probe_local_vllm()``
    is the dedicated probe entry point. ``resolve("local_vllm", ...)``
    always returns ``ok=True``; the caller decides whether to probe
    before each case.
    """
    if route not in ROUTE_TABLE:
        raise UnknownRouteError(f"unknown route {route!r}; expected one of {ROUTE_KEYS}")
    if env is None:
        env = dict(os.environ)
    if allow_remote is None:
        allow_remote = env.get("KCA_ALLOW_REMOTE") == "1"

    meta = ROUTE_TABLE[route]
    spec_kwargs: dict[str, Any] = {
        "route": route,
        "provider_model": meta["provider_model"],
        "requires_remote": meta["requires_remote"],
        "requires_local_lan": meta["requires_local_lan"],
        "api_key_env": meta["api_key_env"],
        "cost_per_1m_input_usd": float(meta["cost_per_1m_input_usd"]),
        "cost_per_1m_output_usd": float(meta["cost_per_1m_output_usd"]),
        "description": meta["description"],
    }

    if meta["requires_remote"] and not allow_remote:
        return RouteSpec(ok=False, error="REMOTE_NOT_APPROVED", **spec_kwargs)

    if meta["requires_remote"] and meta["api_key_env"]:
        key_name = meta["api_key_env"]
        if not env.get(key_name):
            return RouteSpec(ok=False, error=f"MISSING_API_KEY:{key_name}", **spec_kwargs)

    return RouteSpec(ok=True, error=None, **spec_kwargs)


# ---------------------------------------------------------------------------
# Local endpoint probe (separate from resolve to keep resolve side-effect-free).
# ---------------------------------------------------------------------------


def probe_local_vllm(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Probe LAN-hosted endpoints via src/worker/local_model.pick_endpoint.

    Returns a dict with at least ``{"ok": bool, "endpoint": str | None,
    "error": str | None}``. ``ok=False`` carries ``error="NO_LIVE_LOCAL_ENDPOINT"``
    so the route-compare driver can mark cases ``status="skip"`` with
    ``error_text="NO_LIVE_LOCAL_ENDPOINT"`` uniformly.

    The probe imports lazily so callers in restricted environments
    (CI without ``src/worker`` on the path) can still resolve mocked
    / paid routes without pulling in the LAN probe layer.
    """
    if env is not None:
        # Allow callers to inject an explicit env for testing without
        # mutating the global state. Restore on exit.
        saved = {}
        for k in list(os.environ.keys()):
            if k.startswith("KCA_LOCAL_"):
                saved[k] = os.environ.pop(k)
        for k, v in env.items():
            if k.startswith("KCA_LOCAL_"):
                os.environ[k] = v
        try:
            return _probe_local_vllm_inner()
        finally:
            for k in list(os.environ.keys()):
                if k.startswith("KCA_LOCAL_"):
                    del os.environ[k]
            os.environ.update(saved)
    return _probe_local_vllm_inner()


def _probe_local_vllm_inner() -> dict[str, Any]:
    try:
        # Lazy import — keeps the eval CLI usable when worker layer
        # is not on sys.path.
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        worker_dir = repo_root / "src"
        if str(worker_dir) not in sys.path:
            sys.path.insert(0, str(worker_dir))
        from worker import local_model  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "ok": False,
            "endpoint": None,
            "error": "NO_LIVE_LOCAL_ENDPOINT",
            "reason": f"local_model import failed: {type(exc).__name__}: {exc}",
        }

    try:
        picked = local_model.pick_endpoint()
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "ok": False,
            "endpoint": None,
            "error": "NO_LIVE_LOCAL_ENDPOINT",
            "reason": f"pick_endpoint raised: {type(exc).__name__}: {exc}",
        }

    if picked is None:
        return {
            "ok": False,
            "endpoint": None,
            "error": "NO_LIVE_LOCAL_ENDPOINT",
            "reason": "no reachable endpoint",
        }
    return {
        "ok": True,
        "endpoint": picked.name,
        "url": picked.url,
        "model": picked.model,
        "error": None,
    }


__all__ = [
    "ROUTE_KEYS",
    "ROUTE_TABLE",
    "RouteSpec",
    "UnknownRouteError",
    "probe_local_vllm",
    "resolve",
]
