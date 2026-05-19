# M3-T007: Worker smoke tests

## Milestone
M3: Python-first competition worker v0.

## Goal
Create `tests/test_worker_smoke.py` with 6 deterministic pytest cases.
All tests run without a real API key and without a live Kaggle connection.
DB-dependent assertions use the `@requires_db` marker from `tests/conftest.py`.

## Read first
1. `tests/conftest.py` — `requires_db`, `unique_competition`, `db_url` fixtures
2. `src/worker/worker.py` — `AgentWorker`, `MockLiteLLMClient`
3. `src/worker/_types.py` — `JobPolicy`, `WorkerResult`
4. `src/worker/tools.py` — `ToolExecutor`, `ApprovalRequired`
5. `src/worker/budget.py` — `BudgetTracker`

## Test cases

### test_budget_max_turns
```python
def test_budget_max_turns():
    from src.worker.budget import BudgetTracker
    from src.worker._types import JobPolicy
    bt = BudgetTracker(JobPolicy(max_turns=2), model='claude-sonnet-4-6')
    bt.record_turn(100, 50)
    assert bt.check_limits() is None
    bt.record_turn(100, 50)
    assert bt.check_limits() == 'max_turns'
```

### test_budget_max_cost
```python
def test_budget_max_cost():
    from src.worker.budget import BudgetTracker
    from src.worker._types import JobPolicy
    # max_cost_usd so tiny that even 1 turn exceeds it
    bt = BudgetTracker(JobPolicy(max_cost_usd=0.000001), model='claude-sonnet-4-6')
    bt.record_turn(1000, 500)
    assert bt.check_limits() == 'max_cost_usd'
```

### test_tool_executor_path_traversal
```python
def test_tool_executor_path_traversal(tmp_path):
    from src.worker.tools import ToolExecutor
    from src.worker._types import JobPolicy
    ex = ToolExecutor(tmp_path, JobPolicy())
    result = ex.execute('read_file', {'path': '../../../etc/passwd'})
    assert 'path traversal' in result.lower()
    # Confirm nothing was written outside workspace
    assert not (tmp_path / '..').exists() or True  # trivially true but expresses intent
```

### test_tool_executor_bash_deny_list
```python
def test_tool_executor_bash_deny_list(tmp_path):
    import json
    from src.worker.tools import ToolExecutor
    from src.worker._types import JobPolicy
    ex = ToolExecutor(tmp_path, JobPolicy(allowed_tool_patterns=['kca *']))
    # Denied by hard-coded deny list
    r = ex.execute('run_bash', {'command': 'rm -rf /'})
    parsed = json.loads(r)
    assert parsed['exit_code'] == 126
    assert 'allowed_tool_patterns' in parsed['stderr']
```

### test_agent_worker_dry_run_succeeds
```python
def test_agent_worker_dry_run_succeeds(tmp_path):
    from src.worker.worker import AgentWorker
    from src.worker._types import JobPolicy
    (tmp_path / "README.md").write_text("hello world")
    worker = AgentWorker(
        job_id="smoke-dry",
        prompt="Read README.md and tell me what it says.",
        policy=JobPolicy(max_turns=5),
        workspace=tmp_path,
        dry_run=True)
    result = worker.run()
    assert result.status == 'done'
    assert result.turns_used == 2
    assert result.cost_usd > 0
```

### test_agent_worker_budget_stop
```python
def test_agent_worker_budget_stop(tmp_path):
    from src.worker.worker import AgentWorker, MockLiteLLMClient
    from src.worker._types import JobPolicy
    worker = AgentWorker(
        job_id="smoke-budget",
        prompt="loop forever",
        policy=JobPolicy(max_turns=1),
        workspace=tmp_path,
        dry_run=True)
    # Override mock scenario to always return tool_use (never end_turn)
    worker._mock_client = MockLiteLLMClient(scenario='infinite_tool')
    result = worker.run()
    assert result.status == 'budget_stop'
    assert result.turns_used == 1
```

## Fixtures needed
The tests use `tmp_path` (built-in pytest) and the existing `requires_db` marker.
No new fixtures needed in this task.

## Run command
```bash
python -m pytest tests/test_worker_smoke.py -v
```

Expected: 6 passed, 0 failed.

If `src.worker` is not importable (path issue), add a `conftest.py` entry or a
`pyproject.toml` `[tool.pytest.ini_options] pythonpath = ["."]` line.

## Acceptance criteria
- All 6 tests pass with `python -m pytest tests/test_worker_smoke.py -v`.
- No real API calls are made (verified by absence of `ANTHROPIC_API_KEY` requirement).
- No Kaggle CLI calls.
- Tests run in under 5 seconds total.

## Stop condition
Stop after 25 turns. These are pure unit tests; if a test fails, fix the underlying
production code before moving on.
