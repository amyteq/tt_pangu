# M3-T004: AgentWorker core loop + budget enforcement

## Milestone
M3: Python-first competition worker v0.

## Goal
Implement `AgentWorker.run()` — the agentic tool loop that drives the Claude API,
executes tools in the workspace, tracks budget, and records every turn to the DB.
Provide a `MockLiteLLMClient` for deterministic testing without API calls.

## Read first
1. `src/worker/_types.py` — `JobPolicy`, `WorkerResult`
2. `src/worker/tools.py` — `TOOL_SCHEMAS`, `ToolExecutor`, `ApprovalRequired`
3. `src/worker/budget.py` — `BudgetTracker`
4. `tools/kca/db.py` — `append_job_event`, `update_job` signatures
5. `docs/milestones/README.md` — M3 exit criteria

## Worker runtime choice

Use **LiteLLM** (`litellm.completion()`) as the unified LLM call layer (ADR-0004).
This replaces the earlier `anthropic.Anthropic()` plan and avoids provider lock-in.

```python
import litellm

response = litellm.completion(
    model=self.policy.model,           # "claude-sonnet-4-6" | "gpt-4o" | "ollama/qwen2.5"
    messages=messages,
    tools=TOOL_SCHEMAS,                # OpenAI tool schema format
    temperature=self.policy.temperature,
    top_p=self.policy.top_p,
    **({"min_p": self.policy.min_p} if self.policy.min_p is not None else {}),
    max_tokens=8192,
)
```

LiteLLM returns OpenAI-format responses for all providers. Access tokens via
`response.usage.prompt_tokens` / `response.usage.completion_tokens`.
Access cost via `litellm.completion_cost(completion_response=response)`.

The worker does NOT call `claude` CLI as a subprocess. The CLI is for interactive
development; the worker is the production runtime.

## `AgentWorker` implementation

```python
import litellm, time
from pathlib import Path
from src.worker._types import JobPolicy, WorkerResult
from src.worker.tools import TOOL_SCHEMAS, ToolExecutor, ApprovalRequired
from src.worker.budget import BudgetTracker

class AgentWorker:
    def __init__(self, job_id, prompt, policy: JobPolicy, workspace: Path,
                 db_url=None, dry_run=False):
        self.job_id    = job_id
        self.prompt    = prompt
        self.policy    = policy   # policy.model holds the litellm model string
        self.workspace = workspace
        self.db_url    = db_url
        self.dry_run   = dry_run

    def run(self) -> WorkerResult:
        client   = MockLiteLLMClient() if self.dry_run else None  # None = use real litellm
        budget   = BudgetTracker(self.policy)
        executor = ToolExecutor(self.workspace, self.policy)
        messages = [{"role": "user", "content": self.prompt}]
        start    = time.monotonic()

        while True:
            # 1. Pre-turn budget check
            stop_reason = budget.check_limits()
            if stop_reason:
                self._update_status('failed', error=stop_reason, budget=budget)
                return WorkerResult(
                    status='budget_stop', turns_used=budget.turns,
                    cost_usd=budget.cost_usd,
                    duration_s=time.monotonic() - start,
                    final_message='', stop_reason=stop_reason)

            # 2. LiteLLM call (provider-agnostic; mock used in dry_run)
            extra = {} if self.policy.min_p is None else {"min_p": self.policy.min_p}
            call_fn = client.completion if client else litellm.completion
            response = call_fn(
                model=self.policy.model, max_tokens=8192,
                tools=TOOL_SCHEMAS, messages=messages,
                temperature=self.policy.temperature,
                top_p=self.policy.top_p, **extra)

            # 3. Record turn (litellm cost via completion_cost())
            budget.record_turn(response)
            self._append_event('turn_start', budget.turns,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=budget.cost_usd,
                event_data={'stop_reason': response.stop_reason})

            # 4. end_turn → done
            if response.stop_reason == 'end_turn':
                final = next(
                    (b.text for b in response.content if hasattr(b, 'text')), '')
                self._update_status('succeeded', budget=budget)
                return WorkerResult(
                    status='done', turns_used=budget.turns,
                    cost_usd=budget.cost_usd,
                    duration_s=time.monotonic() - start,
                    final_message=final, stop_reason='end_turn')

            # 5. tool_use → execute tools
            if response.stop_reason == 'tool_use':
                tool_results = []
                for block in response.content:
                    if block.type != 'tool_use':
                        continue
                    self._append_event('tool_call', budget.turns,
                        event_data={'tool': block.name, 'input': block.input})
                    try:
                        result = executor.execute(block.name, block.input)
                    except ApprovalRequired as exc:
                        # Handled in M3-T005; for now propagate as paused.
                        raise
                    self._append_event('tool_result', budget.turns,
                        event_data={'tool': block.name,
                                    'result_preview': str(result)[:200]})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)})

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user",      "content": tool_results})
                continue

            # 6. Unexpected stop_reason
            self._update_status('failed',
                error=f"unexpected stop_reason={response.stop_reason}", budget=budget)
            return WorkerResult(
                status='failed', turns_used=budget.turns,
                cost_usd=budget.cost_usd,
                duration_s=time.monotonic() - start,
                final_message='', stop_reason='unexpected')

    # --- private helpers ---

    def _append_event(self, event_type, turn_number, *, input_tokens=None,
                      output_tokens=None, cost_usd=None, event_data=None):
        """Write to DB if db_url set; otherwise no-op."""
        if not self.db_url:
            return
        try:
            from tools.kca import db
            db.append_job_event(
                self.job_id, event_type, turn_number=turn_number,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost_usd, event_data=event_data or {})
        except Exception:
            pass  # never crash the worker loop on DB write failure

    def _update_status(self, status, *, error=None, budget=None):
        if not self.db_url:
            return
        try:
            import datetime
            from tools.kca import db
            db.update_job(self.job_id, status=status, error=error,
                          turns_used=budget.turns if budget else None,
                          cost_usd=budget.cost_usd if budget else None,
                          finished_at=datetime.datetime.utcnow())
        except Exception:
            pass
```

## `MockLiteLLMClient`

Scripted response sequence for tests. Place in `src/worker/worker.py` or a
separate `src/worker/_mock.py`.

```python
class MockLiteLLMClient:
    """Deterministic fake for dry-run tests. Never calls the Anthropic API."""

    def __init__(self, scenario='two_turns'):
        self._turn = 0
        self._scenario = scenario

    def messages(self):
        return self  # support client.messages.create()

    def create(self, **kwargs):
        self._turn += 1
        if self._scenario == 'two_turns':
            return self._two_turns_response()
        if self._scenario == 'infinite_tool':
            return self._infinite_tool_response()
        raise ValueError(f"unknown scenario: {self._scenario}")

    def _two_turns_response(self):
        """Turn 1: read_file. Turn 2: end_turn."""
        if self._turn == 1:
            return _make_tool_use_response('read_file', {'path': 'README.md'}, 50, 20)
        return _make_end_turn_response('dry run complete', 30, 10)

    def _infinite_tool_response(self):
        """Always returns tool_use (for budget-stop tests)."""
        return _make_tool_use_response('read_file', {'path': 'README.md'}, 100, 50)
```

Helper builders for response objects must match the real `anthropic.types.Message`
shape closely enough that `AgentWorker` can use them:
- `.stop_reason: str`
- `.content: list` of objects with `.type` and `.text` or `.id`, `.name`, `.input`
- `.usage.input_tokens`, `.usage.output_tokens`

Use `types.SimpleNamespace` or small dataclasses — no anthropic dependency in mock.

## Acceptance criteria

```bash
# No API key needed — dry_run mode only
python - <<'EOF'
import pathlib, tempfile
from src.worker._types import JobPolicy
from src.worker.worker import AgentWorker

ws = pathlib.Path(tempfile.mkdtemp())
(ws / "README.md").write_text("hello world")

# Normal dry run
w = AgentWorker("t1", "Read README.md", JobPolicy(max_turns=5), ws, dry_run=True)
r = w.run()
assert r.status == 'done', r
assert r.turns_used == 2, r.turns_used
assert r.cost_usd > 0, r.cost_usd
print(f"PASS: done in {r.turns_used} turns, ${r.cost_usd:.6f}")

# Budget stop
w2 = AgentWorker("t2", "loop", JobPolicy(max_turns=1), ws, dry_run=True,
                 model='claude-sonnet-4-6')
# Use infinite_tool scenario so turn 1 returns tool_use, then budget fires.
w2._mock_scenario = 'infinite_tool'
r2 = w2.run()
assert r2.status == 'budget_stop', r2
print(f"PASS: budget stop at turn {r2.turns_used}")
EOF
```

Both assertions must pass. No network calls.

## Stop condition
Stop after 50 turns. If the mock client shape causes AttributeError, adjust the
dataclass/SimpleNamespace structure and document the deviation.
