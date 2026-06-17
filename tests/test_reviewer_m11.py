"""Tests for M11-T002 reviewer-gate wiring of new CTF approval ops.

Covers:
- `should_consult_reviewer` returns True for `challenge_run`, `flag_submit`,
  `network_egress`.
- `run_review` for `flag_submit` does NOT include the flag value in the
  rendered context.
- Permission policy resolution per profile (default vs. permissive-dev vs.
  competition-runner).

No DB, no network. Pure-Python tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# 1. should_consult_reviewer returns True for the three new ops
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operation",
    ["challenge_run", "flag_submit", "network_egress"],
)
def test_should_consult_reviewer_new_ops(operation, monkeypatch):
    # Force default trigger set (no env override).
    monkeypatch.delenv("KCA_REVIEWER_TRIGGER_OPS", raising=False)
    from src.worker.reviewer import should_consult_reviewer

    assert should_consult_reviewer(operation) is True


def test_should_consult_reviewer_legacy_ops_still_trigger(monkeypatch):
    """Regression: M6 / M9 ops must still be in the default trigger set."""
    monkeypatch.delenv("KCA_REVIEWER_TRIGGER_OPS", raising=False)
    from src.worker.reviewer import should_consult_reviewer

    assert should_consult_reviewer("kaggle_submit") is True
    assert should_consult_reviewer("supabase_migrate") is True
    assert should_consult_reviewer("git_force_push") is True


def test_should_consult_reviewer_unknown_op_returns_false(monkeypatch):
    monkeypatch.delenv("KCA_REVIEWER_TRIGGER_OPS", raising=False)
    from src.worker.reviewer import should_consult_reviewer

    assert should_consult_reviewer("read_file") is False
    assert should_consult_reviewer("not_a_real_op") is False


# ---------------------------------------------------------------------------
# 2. run_review / rendered prompt for flag_submit redacts the flag value
# ---------------------------------------------------------------------------


_SECRET_FLAG = "picoCTF{n3v3r_l34k_th15_t0_th3_r3v13w3r}"


def _flag_submit_request():
    from src.worker.reviewer import ReviewRequest

    return ReviewRequest(
        job_id="job-m11-t002",
        target_op="flag_submit",
        tool_name="flag_submit",
        tool_input={
            "event_slug": "picoctf-2025",
            "challenge_slug": "web-1",
            "flag": _SECRET_FLAG,
        },
        final_message="solver recovered flag locally; submitting now",
        event_trail=[],
    )


def test_render_prompt_for_flag_submit_redacts_flag_value():
    from src.worker.reviewer import render_review_context

    req = _flag_submit_request()
    rendered = render_review_context(req)

    # The flag string itself must NOT appear anywhere in the prompt.
    assert _SECRET_FLAG not in rendered
    # The redaction sentinel must appear.
    assert "_redacted" in rendered
    # Event + challenge slug remain — the reviewer needs them to decide.
    assert "picoctf-2025" in rendered
    assert "web-1" in rendered
    # Length is exposed so the reviewer can sanity-check shape.
    assert str(len(_SECRET_FLAG)) in rendered


def test_redact_tool_input_only_redacts_flag_submit():
    """challenge_run / network_egress / unknown ops must NOT touch tool_input."""
    from src.worker.reviewer import _redact_tool_input

    payload = {"flag": "abc", "url": "https://x"}
    # Non-flag_submit ops pass through unchanged.
    assert _redact_tool_input("challenge_run", payload) == payload
    assert _redact_tool_input("network_egress", payload) == payload
    assert _redact_tool_input("kaggle_submit", payload) == payload
    # flag_submit redacts the flag key.
    redacted = _redact_tool_input("flag_submit", payload)
    assert redacted["flag"] == {"_redacted": True, "length": 3}
    assert redacted["url"] == "https://x"


def test_run_review_dry_run_for_flag_submit_does_not_leak_flag():
    """The dry-run reviewer must approve without ever rendering the flag."""
    from src.worker.reviewer import run_review

    req = _flag_submit_request()
    verdict = run_review(req, dry_run=True)
    assert verdict.verdict == "approve"
    # Dry-run rationale is canned; sanity-check the flag is not in it.
    assert _SECRET_FLAG not in verdict.rationale
    assert _SECRET_FLAG not in json.dumps(verdict.evidence)


# ---------------------------------------------------------------------------
# 3. Permission policy resolution per profile
# ---------------------------------------------------------------------------


def _load_policy(profile: str) -> list[dict]:
    path = REPO_ROOT / ".kca" / "permissions" / f"{profile}.yaml"
    with path.open() as f:
        return list(yaml.safe_load_all(f))[0]


def _find_op(policy: list[dict], op_name: str) -> dict | None:
    for row in policy:
        if isinstance(row, dict) and row.get("operation") == op_name:
            return row
    return None


@pytest.mark.parametrize(
    "profile,operation,expected_decision",
    [
        ("default", "challenge_run", "ask"),
        ("default", "flag_submit", "ask"),
        ("default", "network_egress", "deny"),
        ("permissive-dev", "challenge_run", "ask"),
        ("permissive-dev", "flag_submit", "ask"),
        ("permissive-dev", "network_egress", "deny"),
        ("competition-runner", "challenge_run", "ask"),
        ("competition-runner", "flag_submit", "ask"),
        ("competition-runner", "network_egress", "deny"),
    ],
)
def test_policy_default_decision(profile, operation, expected_decision):
    policy = _load_policy(profile)
    row = _find_op(policy, operation)
    assert row is not None, f"{operation} missing from {profile}.yaml"
    assert row["default_decision"] == expected_decision


def test_policy_audit_required_flag():
    """All three M11 ops must have audit_required=True in every profile."""
    for profile in ("default", "permissive-dev", "competition-runner"):
        policy = _load_policy(profile)
        for op in ("challenge_run", "flag_submit", "network_egress"):
            row = _find_op(policy, op)
            assert row is not None
            assert row.get("audit_required") is True, f"{profile}.yaml::{op} must have audit_required: true"


def test_competition_runner_challenge_run_conditional_allow():
    """competition-runner is the ONLY profile where challenge_run carries
    conditional_allow.when_in_scope: allow."""
    policy = _load_policy("competition-runner")
    row = _find_op(policy, "challenge_run")
    assert row is not None
    conditional = row.get("conditional_allow") or {}
    assert conditional.get("when_in_scope") == "allow"


def test_flag_submit_never_has_conditional_allow_to_allow():
    """flag_submit is the highest-blast-radius op. No profile may give it
    a conditional_allow path to `allow`."""
    for profile in ("default", "permissive-dev", "competition-runner"):
        policy = _load_policy(profile)
        row = _find_op(policy, "flag_submit")
        assert row is not None
        conditional = row.get("conditional_allow") or {}
        for key, val in conditional.items():
            assert val != "allow", f"{profile}.yaml::flag_submit must not allow via conditional_allow.{key}"


def test_network_egress_conditional_allow_is_ask_or_deny():
    """network_egress is deny-default. The only relaxation is to `ask`
    when in scope — never `allow`."""
    for profile in ("default", "permissive-dev", "competition-runner"):
        policy = _load_policy(profile)
        row = _find_op(policy, "network_egress")
        assert row is not None
        conditional = row.get("conditional_allow") or {}
        for key, val in conditional.items():
            assert val in {"ask", "deny"}, (
                f"{profile}.yaml::network_egress conditional_allow.{key} must be ask or deny, got {val}"
            )


# ---------------------------------------------------------------------------
# 4. Worker tool_name → target_op mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_name,expected_target_op",
    [
        # CTF synthetic / wrapper tool names map to operation strings.
        ("kca_ctf_solver_run", "challenge_run"),
        ("ctf_solver_run", "challenge_run"),
        ("challenge_run", "challenge_run"),
        ("kca_ctf_flag_submit", "flag_submit"),
        ("ctf_flag_submit", "flag_submit"),
        ("flag_submit", "flag_submit"),
        ("http_request", "network_egress"),
        ("network_egress", "network_egress"),
        # Legacy ops: identity (target_op == tool_name).
        ("kaggle_submit", "kaggle_submit"),
        ("kernel_push", "kernel_push"),
        ("supabase_migrate", "supabase_migrate"),
    ],
)
def test_resolve_target_op(tool_name, expected_target_op):
    from src.worker.worker import _resolve_target_op

    assert _resolve_target_op(tool_name) == expected_target_op
