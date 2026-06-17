"""Sync reviewer agent (M6-T004 / ADR-0012).

When the primary worker is about to call a high-stakes operation
(`kaggle_submit`, `supabase_migrate`, `git_force_push`, `dataset_upload`,
`delete_artifact`), the reviewer reads the job's event trail and final
plan, calls a reviewer model via LiteLLM, and returns a verdict
(`approve` | `reject` | `abstain`). Sync-only for M6.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


DEFAULT_REVIEWER_MODEL = "claude-opus-4-7"
DEFAULT_TRIGGER_OPS = (
    "kaggle_submit",
    "supabase_migrate",
    "git_force_push",
    "dataset_upload",
    "delete_artifact",
    # M11 (ADR-0017): CTF approval operations. The reviewer-gate is the
    # deny-default authority for these; the hook layer
    # (.claude/hooks/guard_tool.py) acts as a secondary defense for known-bad
    # paths/hosts even before the reviewer fires. An httpx-level interceptor
    # is out of scope for M11 (filed as a follow-up).
    "challenge_run",
    "flag_submit",
    "network_egress",
    # M14 (ADR-0020 §8): the goal-driven loop's stuck detector raises this
    # decision_type when N consecutive non-improving submissions coincide with
    # 0 fresh idea-sourcing candidates. It reuses the human_decisions /
    # Approval Inbox surface — the escalation payload is redacted via
    # tools/kca/stuck.redact_escalation_payload before it reaches any audit row.
    "kaggle.exploration_stuck",
)

# Flag-substring sentinels we MUST NOT render into the reviewer prompt for
# the flag_submit op. Kept narrow on purpose: the worker is expected to pass
# the flag value under the `tool_input["flag"]` key.
_FLAG_INPUT_KEYS = ("flag", "flag_value", "submission")


@dataclass
class ReviewRequest:
    job_id: str
    target_op: str
    tool_name: str
    tool_input: dict
    final_message: str | None = None
    event_trail: list[dict] = field(default_factory=list)


@dataclass
class ReviewVerdict:
    verdict: str
    rationale: str
    evidence: dict
    cost_usd: float
    reviewer_model: str


_REVIEWER_SYSTEM_PROMPT = (
    "You are a sync reviewer for a Kaggle/CTF code agent. The primary "
    "worker is about to invoke a high-stakes operation. Read the job "
    "context below and decide whether the call should proceed.\n\n"
    "Return STRICT JSON only (no prose, no markdown), exactly: "
    '{"verdict": "approve|reject|abstain", '
    '"rationale": "<one paragraph>", '
    '"evidence": {"key_signals": [...]}}\n\n'
    "Use approve when the plan and tool input clearly match the stated "
    "task and contain no destructive surprise. Use reject when the call "
    "would touch the wrong data, push the wrong file, leak secrets, or "
    "violate competition/CTF rules. Use abstain when context is too thin "
    "to decide; a human will be paged."
)


def _trim_event_trail(events: list[dict], max_events: int = 20) -> list[dict]:
    """Keep at most the most-recent max_events events, drop bulky fields."""
    if len(events) > max_events:
        events = events[-max_events:]
    pruned: list[dict] = []
    for ev in events:
        pruned.append(
            {
                "event_type": ev.get("event_type"),
                "turn_number": ev.get("turn_number"),
                "event_data": ev.get("event_data"),
            }
        )
    return pruned


_EVENT_TRAIL_TRIAGE_THRESHOLD = 8 * 1024  # 8 KB


def _redact_tool_input(target_op: str, tool_input: dict) -> dict:
    """Strip secret-shaped fields from the reviewer-rendered tool_input.

    M11 (ADR-0017): for `flag_submit` the flag value MUST NEVER appear in
    the reviewer prompt, agent_reviews.rationale, agent_job_events.event_data,
    or any audit row. The reviewer only needs the event slug, challenge slug,
    and the flag length to decide.
    """
    if not isinstance(tool_input, dict):
        return tool_input
    if target_op != "flag_submit":
        return tool_input
    redacted: dict[str, Any] = {}
    for k, v in tool_input.items():
        if k in _FLAG_INPUT_KEYS:
            try:
                length = len(v) if isinstance(v, (str, bytes, list, tuple)) else None
            except Exception:
                length = None
            redacted[k] = {"_redacted": True, "length": length}
        else:
            redacted[k] = v
    return redacted


def _goal_remaining_delta(req: ReviewRequest):
    """Lift goal_remaining_delta out of a kernel_push tool_input, else None.

    M14-T002 (ADR-0020 §1): the `kernel_push` gate prompt surfaces how far the
    push could move the active goal so the approver sees the goal context. This
    is a read-only enrichment — the caller (the loop) computes the delta via
    `kca goal show` / `tools/kca/goal.goal_remaining_delta` and threads it into
    `tool_input`; the reviewer never recomputes it and never blocks on it.
    Tolerates a missing key (M10 pushes had no goal) and a non-dict input.
    """
    if req.target_op != "kernel_push":
        return None
    if not isinstance(req.tool_input, dict):
        return None
    return req.tool_input.get("goal_remaining_delta")


def _render_prompt(req: ReviewRequest) -> str:
    trail = _trim_event_trail(req.event_trail)
    trail_json = json.dumps(trail, default=str, ensure_ascii=False)
    summary_block: str | None = None
    if len(trail_json) > _EVENT_TRAIL_TRIAGE_THRESHOLD:
        try:
            from src.worker import triage as _triage

            sresult = _triage.summarise_text(trail_json)
            if sresult.get("ok") and sresult.get("summary"):
                summary_block = (
                    f"(event_trail triaged to {sresult.get('endpoint')}:{sresult.get('model')})\n{sresult['summary']}"
                )
        except Exception:
            summary_block = None
    body = {
        "job_id": req.job_id,
        "target_op": req.target_op,
        "tool_name": req.tool_name,
        "tool_input": _redact_tool_input(req.target_op, req.tool_input),
        "final_message": req.final_message,
    }
    delta = _goal_remaining_delta(req)
    if delta is not None:
        # Surface the goal context for the kernel_push approver (M14-T002).
        body["goal_remaining_delta"] = delta
    if summary_block is not None:
        body["event_trail_summary"] = summary_block
    else:
        body["event_trail"] = trail
    rendered = json.dumps(body, default=str, ensure_ascii=False, indent=2)
    return f"REVIEW REQUEST:\n{rendered}\n\nReturn STRICT JSON only."


def _trigger_ops_from_env() -> set[str]:
    raw = os.environ.get("KCA_REVIEWER_TRIGGER_OPS", "")
    if not raw.strip():
        return set(DEFAULT_TRIGGER_OPS)
    return {p.strip() for p in raw.split(",") if p.strip()}


def should_consult_reviewer(operation: str) -> bool:
    """Return True if the given operation is in the configured trigger set."""
    return operation in _trigger_ops_from_env()


def run_review(req: ReviewRequest, *, dry_run: bool = True) -> ReviewVerdict:
    """Module-level convenience wrapper. Runs a Reviewer with the given
    request. Default to dry-run so callers from tests / smoke paths don't
    accidentally hit the LiteLLM endpoint."""
    reviewer = Reviewer(dry_run=dry_run)
    return reviewer.review(req)


def render_review_context(req: ReviewRequest) -> str:
    """Render the exact prompt body a live reviewer would see. Used by tests
    (and by future structured-audit code) to assert that the flag value never
    appears in the reviewer's context for `flag_submit`.
    """
    return _render_prompt(req)


def escalate_reject() -> bool:
    return os.environ.get("KCA_REVIEWER_ESCALATE_REJECT", "1").strip() == "1"


class Reviewer:
    """Sync reviewer. Calls LiteLLM unless dry_run=True."""

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int = 2048,
        timeout_s: int = 120,
        dry_run: bool = False,
        dry_verdict: str = "approve",
        dry_rationale: str = "dry-run reviewer auto-approve",
    ) -> None:
        self.model = model or os.environ.get("KCA_REVIEWER_MODEL") or DEFAULT_REVIEWER_MODEL
        try:
            self.max_tokens = int(os.environ.get("KCA_REVIEWER_MAX_TOKENS", max_tokens))
        except ValueError:
            self.max_tokens = max_tokens
        try:
            self.timeout_s = int(os.environ.get("KCA_REVIEWER_TIMEOUT_S", timeout_s))
        except ValueError:
            self.timeout_s = timeout_s
        self.dry_run = dry_run
        self.dry_verdict = dry_verdict
        self.dry_rationale = dry_rationale

    def review_dry_run(self) -> ReviewVerdict:
        return ReviewVerdict(
            verdict=self.dry_verdict,
            rationale=self.dry_rationale,
            evidence={"mode": "dry_run"},
            cost_usd=0.0,
            reviewer_model=self.model,
        )

    def review(self, req: ReviewRequest) -> ReviewVerdict:
        if self.dry_run:
            return self.review_dry_run()
        return self._review_live(req)

    def _review_live(self, req: ReviewRequest) -> ReviewVerdict:
        user_prompt = _render_prompt(req)
        messages = [
            {"role": "system", "content": _REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        started = time.monotonic()
        try:
            import litellm  # noqa: F401  (lazy import; only required when live)

            response = litellm.completion(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.0,
                timeout=self.timeout_s,
            )
        except Exception as exc:
            return ReviewVerdict(
                verdict="abstain",
                rationale=f"reviewer model error: {exc}",
                evidence={"error": str(exc), "duration_s": time.monotonic() - started},
                cost_usd=0.0,
                reviewer_model=self.model,
            )
        msg = response.choices[0].message
        text = (msg.content or "").strip()
        # Strip code fences if any.
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rstrip("`")
        verdict = "abstain"
        rationale = text
        evidence: dict[str, Any] = {}
        try:
            parsed = json.loads(text)
            v = str(parsed.get("verdict", "")).lower().strip()
            if v in {"approve", "reject", "abstain"}:
                verdict = v
            rationale = str(parsed.get("rationale", "") or rationale)
            ev = parsed.get("evidence")
            if isinstance(ev, dict):
                evidence = ev
        except Exception as exc:
            evidence = {"parse_error": str(exc), "raw": text[:500]}
        usage = getattr(response, "usage", None)
        cost_usd = 0.0
        if usage is not None:
            cost_usd = float(getattr(usage, "total_cost", 0.0) or 0.0)
        return ReviewVerdict(
            verdict=verdict,
            rationale=rationale,
            evidence=evidence,
            cost_usd=cost_usd,
            reviewer_model=self.model,
        )
