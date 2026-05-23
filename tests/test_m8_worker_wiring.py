"""M8 worker-wiring tests — JobPolicy.tool_decisions + ToolSpec enforcement.

Three approval paths: allow / ask / deny. Each runs the worker against a
mocked LiteLLM client so no real network or model calls happen, and asserts
the matching audit JSONL line plus the worker's stop_reason.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.worker._types import JobPolicy  # noqa: E402
from src.worker.worker import AgentWorker, MockLiteLLMClient  # noqa: E402


def _single_call_client(tool_name: str, tool_input: dict) -> MockLiteLLMClient:
    """LiteLLM mock that emits one tool call then stops."""

    client = MockLiteLLMClient(scenario="two_turns")
    turn = {"n": 0}

    def completion(**_kwargs):
        turn["n"] += 1
        if turn["n"] == 1:
            tc = types.SimpleNamespace(
                id="call_x",
                type="function",
                function=types.SimpleNamespace(
                    name=tool_name,
                    arguments=json.dumps(tool_input),
                ),
            )
            msg = types.SimpleNamespace(content=None, tool_calls=[tc])
            choice = types.SimpleNamespace(message=msg, finish_reason="tool_calls")
            return types.SimpleNamespace(
                choices=[choice],
                usage=types.SimpleNamespace(prompt_tokens=20, completion_tokens=10),
            )
        msg = types.SimpleNamespace(content="done", tool_calls=None)
        choice = types.SimpleNamespace(message=msg, finish_reason="stop")
        return types.SimpleNamespace(
            choices=[choice],
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )

    client.completion = completion  # type: ignore[method-assign]
    return client


def _build_worker(
    tmp_path: Path,
    tool_decisions: dict,
    audit_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AgentWorker:
    """Construct a worker with the audit path redirected into the test dir."""
    # Redirect the audit file to the per-test path so tests are isolated.
    monkeypatch.setenv("KCA_SESSION_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("KCA_AUDIT_PATH", str(audit_path))

    policy = JobPolicy(
        skill_name="_test_fixture",
        policy_profile="permissive-dev",
        mode="default",
        tool_decisions=tool_decisions,
    )
    (tmp_path / "hello.txt").write_text("hello world", encoding="utf-8")
    worker = AgentWorker(
        job_id="00000000-0000-0000-0000-000000000000",
        prompt="read the file",
        policy=policy,
        workspace=tmp_path,
        db_url=None,
        dry_run=True,
    )
    worker._mock_client = _single_call_client("read_file", {"path": "hello.txt"})
    return worker


def _audit_lines(audit_path: Path) -> list[dict]:
    if not audit_path.is_file():
        return []
    return [json.loads(line) for line in audit_path.read_text().splitlines() if line]


def test_worker_tool_call_allow_path(tmp_path, monkeypatch):
    audit = tmp_path / "audit.jsonl"
    worker = _build_worker(
        tmp_path,
        tool_decisions={"read_file": "allow"},
        audit_path=audit,
        monkeypatch=monkeypatch,
    )
    result = worker.run()
    assert result.status == "done", result
    assert result.stop_reason == "end_turn"
    rows = _audit_lines(audit)
    allow_rows = [r for r in rows if r["tool_name"] == "read_file"]
    assert allow_rows, "expected at least one read_file audit row"
    assert allow_rows[-1]["decision"] == "allow"


def test_worker_tool_call_ask_path(tmp_path, monkeypatch):
    audit = tmp_path / "audit.jsonl"
    worker = _build_worker(
        tmp_path,
        tool_decisions={"read_file": "ask"},
        audit_path=audit,
        monkeypatch=monkeypatch,
    )
    result = worker.run()
    assert result.status == "paused", result
    assert result.stop_reason == "approval_required"
    rows = _audit_lines(audit)
    ask_rows = [r for r in rows if r["decision"] == "ask"]
    assert ask_rows, "expected an audit row with decision=ask"
    # File should not have been mutated, and the worker should never have hit
    # the "tool_result" path. (Tool ran but produced no side effect for read.)


def test_worker_tool_call_deny_path(tmp_path, monkeypatch):
    audit = tmp_path / "audit.jsonl"
    worker = _build_worker(
        tmp_path,
        tool_decisions={"read_file": "deny"},
        audit_path=audit,
        monkeypatch=monkeypatch,
    )
    result = worker.run()
    assert result.status == "failed", result
    assert result.stop_reason == "policy_violation"
    rows = _audit_lines(audit)
    deny_rows = [r for r in rows if r["decision"] == "deny"]
    assert deny_rows, "expected an audit row with decision=deny"
