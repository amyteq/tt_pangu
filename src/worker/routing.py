"""Per-job-type model routing (ADR-0010).

Override precedence: explicit ``override`` > MODEL_ROUTES table > default Sonnet.
"""

from __future__ import annotations


MODEL_ROUTES: dict[str, str] = {
    "research": "claude-haiku-4-5",
    "implement": "claude-sonnet-4-6",
    "experiment": "claude-sonnet-4-6",
    "eval": "claude-opus-4-7",
    "analysis": "claude-opus-4-7",
    "review": "claude-opus-4-7",
    # M6: local-model job types resolve to the LAN endpoints layer at call site.
    "log_triage": "local",
    "summarise": "local",
}

DEFAULT_MODEL = "claude-sonnet-4-6"
LOCAL_SENTINEL = "local"


def model_for(job_type: str, *, override: str | None = None) -> str:
    """Resolve the model id for a given job type.

    Args:
        job_type: One of MODEL_ROUTES keys (research/implement/experiment/eval/
            analysis/review/log_triage/summarise). Unknown values fall through
            to DEFAULT_MODEL.
        override: Explicit model id; if given, returned verbatim.

    Returns the literal string "local" for job types that should be served by
    the M6 local-endpoint layer; callers resolve via
    src.worker.local_model.pick_endpoint().
    """
    if override:
        return override
    return MODEL_ROUTES.get(job_type, DEFAULT_MODEL)


def resolve_local_or_fallback(
    job_type: str,
    *,
    override: str | None = None,
) -> tuple[str, "object | None"]:
    """Resolve a job_type to (model_id, endpoint_or_None).

    When the routing table says "local", probe and return either the
    served model id (with endpoint object) or the fallback model id (None).
    """
    model = model_for(job_type, override=override)
    if model != LOCAL_SENTINEL:
        return model, None
    from . import local_model

    ep = local_model.pick_endpoint()
    if ep is not None:
        return ep.model, ep
    return local_model.fallback_model(), None
