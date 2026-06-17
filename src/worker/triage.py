"""Local-model job types (M6-T006): triage_job_events + summarise_text.

Both compress long traces with a local LLM endpoint via LiteLLM. When
no local endpoint is reachable they fall back to the cloud
`KCA_LOCAL_FALLBACK_MODEL` (default `claude-haiku-4-5`) unless
`KCA_LOCAL_REQUIRE_LOCAL=1`.
"""

from __future__ import annotations

import json
import time
from typing import Any

from src.worker import local_model


_SUMMARY_SYSTEM_PROMPT = (
    "You are a sync log summariser. Compress the agent job log below "
    "into a faithful summary in 400 words or fewer. Preserve concrete "
    "tool names, file paths, error messages, and any failure causes. "
    "Do not invent details, do not editorialise. Return plain text only."
)


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... [truncated] ...\n" + text[-half:]


def _format_events(events: list[dict]) -> str:
    lines: list[str] = []
    for ev in events:
        et = ev.get("event_type", "?")
        tn = ev.get("turn_number")
        ed = ev.get("event_data")
        if isinstance(ed, str):
            try:
                ed = json.loads(ed)
            except Exception:
                ed = {"raw": ed}
        lines.append(f"[turn={tn} type={et}] {json.dumps(ed, default=str, ensure_ascii=False)}")
    return "\n".join(lines)


def _call_local(
    model: str,
    api_base: str | None,
    api_key: str | None,
    messages: list[dict],
    timeout_s: int = 60,
) -> tuple[str, dict]:
    """Run a LiteLLM completion against a local or cloud model. Returns (text, meta)."""
    started = time.monotonic()
    try:
        import litellm

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1024,
            "timeout": timeout_s,
        }
        if api_base is not None:
            kwargs["api_base"] = api_base
            kwargs["api_key"] = api_key or "local"
            kwargs["custom_llm_provider"] = "openai"
        resp = litellm.completion(**kwargs)
    except Exception as exc:
        return "", {"error": str(exc), "duration_s": time.monotonic() - started}
    text = resp.choices[0].message.content or ""
    cost = 0.0
    usage = getattr(resp, "usage", None)
    if usage is not None:
        cost = float(getattr(usage, "total_cost", 0.0) or 0.0)
    return text.strip(), {
        "duration_s": time.monotonic() - started,
        "cost_usd": cost,
    }


def _resolve_target(endpoint=None) -> tuple[str, dict | None]:
    """Return (model_id, kwargs|None) for the dispatch.

    None kwargs means "use cloud fallback".
    """
    if endpoint is None:
        endpoint = local_model.pick_endpoint()
    if endpoint is not None:
        return endpoint.model, local_model.litellm_kwargs_for(endpoint)
    if local_model.require_local():
        return "", None  # caller will short-circuit
    return local_model.fallback_model(), {}


def summarise_text(
    text: str,
    *,
    max_input_chars: int = 16000,
    endpoint=None,
) -> dict:
    """Generic text summariser via local or fallback model."""
    text = _trim(text or "", max_input_chars)
    model, kwargs = _resolve_target(endpoint)
    if kwargs is None:
        # require_local && no endpoint up
        return {
            "ok": False,
            "error": "no endpoint",
            "summary": "",
            "endpoint": None,
            "model": None,
            "cost_usd": 0.0,
        }
    api_base = kwargs.get("api_base") if kwargs else None
    api_key = kwargs.get("api_key") if kwargs else None
    endpoint_name = (
        endpoint.name
        if endpoint is not None
        else (local_model.pick_endpoint().name if api_base else f"fallback:{model}")
    )
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    summary, meta = _call_local(model, api_base, api_key, messages)
    if "error" in meta:
        return {
            "ok": False,
            "error": meta["error"],
            "summary": "",
            "endpoint": endpoint_name,
            "model": model,
            "cost_usd": 0.0,
        }
    return {
        "ok": True,
        "summary": summary,
        "endpoint": endpoint_name,
        "model": model,
        "cost_usd": meta.get("cost_usd", 0.0),
    }


def triage_job_events(
    job_id: str,
    *,
    endpoint=None,
    max_input_chars: int = 16000,
) -> dict:
    """Summarise a job's event trail using a local model."""
    # Strict-local short-circuit: if no endpoint is up and require_local=1,
    # do not bother touching the DB.
    if endpoint is None and local_model.require_local():
        if local_model.pick_endpoint() is None:
            return {
                "ok": False,
                "error": "no endpoint",
                "summary": "",
                "endpoint": None,
                "model": None,
            }
    # Lazy DB import; failure → ok=false, error
    try:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
        import db as _db
    except Exception as exc:
        return {
            "ok": False,
            "error": f"db import: {exc}",
            "summary": "",
            "endpoint": None,
            "model": None,
        }
    try:
        events = _db.list_job_events(job_id)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"db list_job_events: {exc}",
            "summary": "",
            "endpoint": None,
            "model": None,
        }
    if not events:
        return {
            "ok": False,
            "error": "job not found or has no events",
            "summary": "",
            "endpoint": None,
            "model": None,
        }
    formatted = _format_events(events)
    result = summarise_text(formatted, max_input_chars=max_input_chars, endpoint=endpoint)
    result["event_count"] = len(events)
    return result
