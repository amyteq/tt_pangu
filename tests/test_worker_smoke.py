"""Worker smoke tests — all run without a real API key or live DB.

Run with:
    python -m pytest tests/test_worker_smoke.py -v
"""

from __future__ import annotations

import json


def test_budget_tracker_max_turns():
    from src.worker.budget import BudgetTracker
    from src.worker._types import JobPolicy

    bt = BudgetTracker(JobPolicy(max_turns=2), model="claude-sonnet-4-6")
    bt.record_turn(100, 50)
    assert bt.check_limits() is None
    bt.record_turn(100, 50)
    assert bt.check_limits() == "max_turns"


def test_budget_tracker_max_cost():
    from src.worker.budget import BudgetTracker
    from src.worker._types import JobPolicy

    bt = BudgetTracker(JobPolicy(max_cost_usd=0.000001), model="claude-sonnet-4-6")
    bt.record_turn(1000, 500)
    assert bt.check_limits() == "max_cost_usd"


def test_tool_executor_path_traversal_rejected(tmp_path):
    from src.worker.tools import ToolExecutor
    from src.worker._types import JobPolicy

    ex = ToolExecutor(tmp_path, JobPolicy())
    result = ex.execute("read_file", {"path": "../../../etc/passwd"})
    assert "path traversal" in result.lower()


def test_tool_executor_bash_allowlist(tmp_path):
    from src.worker.tools import ToolExecutor
    from src.worker._types import JobPolicy

    ex = ToolExecutor(tmp_path, JobPolicy(allowed_tool_patterns=["kca *"]))
    r = ex.execute("run_bash", {"command": "rm -rf /"})
    parsed = json.loads(r)
    assert parsed["exit_code"] == 126
    assert "allowed_tool_patterns" in parsed["stderr"]


def test_agent_worker_dry_run_succeeds(tmp_path):
    from src.worker.worker import AgentWorker
    from src.worker._types import JobPolicy

    (tmp_path / "README.md").write_text("hello world")
    worker = AgentWorker(
        job_id="smoke-dry",
        prompt="Read README.md and tell me what it says.",
        policy=JobPolicy(max_turns=5),
        workspace=tmp_path,
        dry_run=True,
    )
    result = worker.run()
    assert result.status == "done"
    assert result.turns_used == 2
    assert result.cost_usd > 0


def test_agent_worker_budget_stop(tmp_path):
    from src.worker.worker import AgentWorker, MockLiteLLMClient
    from src.worker._types import JobPolicy

    worker = AgentWorker(
        job_id="smoke-budget",
        prompt="loop forever",
        policy=JobPolicy(max_turns=1),
        workspace=tmp_path,
        dry_run=True,
    )
    worker._mock_client = MockLiteLLMClient(scenario="infinite_tool")
    result = worker.run()
    assert result.status == "budget_stop"
    assert result.turns_used == 1
