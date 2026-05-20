"""Per-job-type model routing (ADR-0010).

Override precedence: explicit ``override`` > MODEL_ROUTES table > default Sonnet.
"""
from __future__ import annotations


MODEL_ROUTES: dict[str, str] = {
    "research":   "claude-haiku-4-5",
    "implement":  "claude-sonnet-4-6",
    "experiment": "claude-sonnet-4-6",
    "eval":       "claude-opus-4-7",
    "analysis":   "claude-opus-4-7",
    "review":     "claude-opus-4-7",
}

DEFAULT_MODEL = "claude-sonnet-4-6"


def model_for(job_type: str, *, override: str | None = None) -> str:
    """Resolve the model id for a given job type.

    Args:
        job_type: One of MODEL_ROUTES keys (research/implement/experiment/eval/
            analysis/review). Unknown values fall through to DEFAULT_MODEL.
        override: Explicit model id; if given, returned verbatim.
    """
    if override:
        return override
    return MODEL_ROUTES.get(job_type, DEFAULT_MODEL)
