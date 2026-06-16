"""Verify the canonical reviewer/approval event-type literal set.

These tests pin the contract between docs/tasks/m9/M9-T003-reviewer-approval-gate.md
and src/worker/worker.py. If a literal is renamed in the worker, this test
catches the drift before it silently orphans the spec.

Run with:
    python -m pytest tests/test_worker_review_events.py -v
"""

from __future__ import annotations

from pathlib import Path

# Canonical reviewer + approval event types emitted via _append_event in
# src/worker/worker.py. Matches the AC wording in M9-T003 task spec.
REVIEWER_APPROVAL_EVENT_TYPES = frozenset(
    {
        "reviewer_abstain",   # LLM reviewer abstained → fall through to human
        "reviewer_reject",    # LLM reviewer rejected the gated operation
        "approval_pause",     # worker paused pending a human decision
        "approval_resume",    # reviewer auto-approved (source: reviewer)
    }
)

_WORKER_SRC = (
    Path(__file__).parent.parent / "src" / "worker" / "worker.py"
).read_text()


def test_canonical_event_types_present_in_worker_source():
    """Each documented reviewer/approval event type appears as a literal in worker.py."""
    for et in REVIEWER_APPROVAL_EVENT_TYPES:
        assert f'"{et}"' in _WORKER_SRC, (
            f"Reviewer/approval event type {et!r} not found as a string literal in "
            "src/worker/worker.py. "
            "Update REVIEWER_APPROVAL_EVENT_TYPES and "
            "docs/tasks/m9/M9-T003-reviewer-approval-gate.md if the literal was "
            "intentionally renamed."
        )


def test_reviewer_decision_literal_absent_from_worker():
    """The stale spec literal 'reviewer_decision' must not appear as an _append_event arg."""
    # The M9-T003 spec used to say event_type='reviewer_decision'; that literal
    # was never emitted. This test prevents the drift from reappearing.
    assert '"reviewer_decision"' not in _WORKER_SRC, (
        "Found '\"reviewer_decision\"' in src/worker/worker.py. "
        "If this is a new event type, add it to REVIEWER_APPROVAL_EVENT_TYPES "
        "and update docs/tasks/m9/M9-T003-reviewer-approval-gate.md."
    )
