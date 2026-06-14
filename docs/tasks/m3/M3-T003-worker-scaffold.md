# M3-T003: Worker scaffold — `src/worker/` directory + tool definitions

## Milestone
M3: Python-first competition worker v0.

## Goal
Scaffold the `src/worker/` Python package with typed dataclasses, tool schema definitions,
a safe tool executor, and a budget tracker skeleton.
The `AgentWorker` class is a stub in this task; the loop is implemented in M3-T004.

## Read first
1. `docs/milestones/README.md` — M3 "Worker can call kca local tools"
2. `CLAUDE.md` — Operating principles 1 (untrusted data), 3 (side effects), 6 (approval gates)
3. `tools/kca/_util.py` — `SideEffect` enum for reference
4. `tools/kca/COMMANDS.md` — allowed tool patterns context

## Module layout

```
src/
  __init__.py        (empty)
worker/
  __init__.py        (empty)
  _types.py          dataclasses: JobPolicy, WorkerResult, ToolCallRecord
  tools.py           TOOL_SCHEMAS list + ToolExecutor class
  budget.py          BudgetTracker class
  worker.py          AgentWorker class (stub — full impl in M3-T004)
```

Place under `src/worker/`, not `tools/`. The worker is a runtime component, not a kca
wrapper.

## `src/worker/_types.py`

```python
from dataclasses import dataclass, field

@dataclass
class JobPolicy:
    # Budget limits — defaults are generous; narrow them per job if needed.
    # Research jobs are more expensive (more turns, more tokens).
    max_turns: int = 60
    max_cost_usd: float = 20.0
    max_runtime_s: int = 7200
    allowed_tool_patterns: list[str] = field(
        default_factory=lambda: ["kca *", "python -m pytest *", "pytest *"]
    )
    # LiteLLM model string — see ADR-0004 for per-job-type recommendations.
    model: str = "claude-sonnet-4-6"
    # Sampling params — see ADR-0004 table for per-job-type values.
    temperature: float = 0.2   # coding default; research jobs should use 0.8
    top_p: float = 0.90
    min_p: float | None = None  # provider-dependent; None = don't pass
    # Approval gates — see ADR-0006.
    approval_gates: dict = field(default_factory=lambda: {
        "kaggle_submit":    False,
        "kernel_push":      False,
        "git_push":         False,
        "dataset_upload":   True,
        "git_force_push":   True,
    })
    # Maximum side-effect level triggering ApprovalRequired in ToolExecutor.
    max_side_effect: str = "SUBMISSION"   # default: allow everything, gate via approval_gates

@dataclass
class WorkerResult:
    status: str          # done | failed | paused | budget_stop
    turns_used: int
    cost_usd: float
    duration_s: float
    final_message: str
    stop_reason: str     # end_turn | max_turns | max_cost_usd | max_runtime_s
                         # approval_required | tool_error | unexpected

@dataclass
class ToolCallRecord:
    tool_name: str
    tool_input: dict
    side_effect: str
    result_preview: str   # first 200 chars of result for event logging
```

## `src/worker/tools.py`

### TOOL_SCHEMAS

Five tool definitions (dict, matching Anthropic messages API `tools` format):

1. `read_file(path: str)` — READ_ONLY
2. `write_file(path: str, content: str)` — LOCAL_WRITE
3. `edit_file(path: str, old_string: str, new_string: str)` — LOCAL_WRITE
4. `run_bash(command: str, timeout_s: int = 60)` — side effect depends on command
5. `grep_workspace(pattern: str, path: str = ".")` — READ_ONLY

### ToolExecutor

```python
class ToolExecutor:
    def __init__(self, workspace: Path, policy: JobPolicy):
        ...

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool in workspace context. Returns serialised result string."""
        ...
```

Safety rules (enforced in `execute`, never skippable):

**Path traversal guard** (for `read_file`, `write_file`, `edit_file`):
- Resolve `workspace / path` with `.resolve()`.
- If the resolved path does not start with `workspace.resolve()`, return an error
  string: `"path traversal rejected: <path>"`. Do not raise; worker logs and continues.

**Bash allowlist** (for `run_bash`):
- Check command against `policy.allowed_tool_patterns` (glob-style, e.g. `"kca *"`).
- Hard-coded deny regardless of policy: `rm -rf`, `git push`, `kaggle submit`,
  `sudo`, any command containing `..`.
- If denied: return `{"stdout": "", "stderr": "command not in allowed_tool_patterns", "exit_code": 126}` as JSON string.
- If allowed: run `subprocess.run()` with `capture_output=True`, `timeout=timeout_s`,
  `cwd=workspace`.

**Side-effect classification**:
- `execute()` must determine the side_effect level of the call before executing.
- If `side_effect_level > policy.max_side_effect`:
  raise `ApprovalRequired(tool_name, tool_input, side_effect_level)`
- `ApprovalRequired` is a subclass of `Exception` defined in `tools.py`.

Side effect mapping:
| Tool | Side effect |
|---|---|
| read_file | READ_ONLY |
| write_file | LOCAL_WRITE |
| edit_file | LOCAL_WRITE |
| grep_workspace | READ_ONLY |
| run_bash with kca kaggle submit/push | SUBMISSION |
| run_bash with kca kaggle fetch/watch/list | READ_ONLY |
| run_bash with kca run * | LOCAL_WRITE |
| run_bash other allowed patterns | LOCAL_WRITE |

## `src/worker/budget.py`

```python
MODEL_PRICING = {
    'claude-sonnet-4-6': (3.0, 15.0),    # (input $/MTok, output $/MTok)
    'claude-opus-4-7':   (5.0, 25.0),
    'claude-haiku-4-5-20251001': (1.0, 5.0),
}

class BudgetTracker:
    def __init__(self, policy: JobPolicy, model: str = 'claude-sonnet-4-6',
                 started_at: float | None = None): ...

    def record_turn(self, input_tokens: int, output_tokens: int) -> None:
        """Increment turns, add token costs."""

    def check_limits(self) -> str | None:
        """Return None if within budget, or the exceeded limit name."""

    @property
    def summary(self) -> dict:
        """{"turns": ..., "input_tokens": ..., "output_tokens": ...,
            "cost_usd": ..., "elapsed_s": ...}"""
```

## `src/worker/worker.py` (stub only)

```python
class AgentWorker:
    """Competition agent worker. Full implementation in M3-T004."""

    def __init__(self, job_id: str, prompt: str, policy: JobPolicy,
                 workspace: Path, db_url: str | None = None,
                 model: str = 'claude-sonnet-4-6', dry_run: bool = False):
        raise NotImplementedError("implemented in M3-T004")

    def run(self) -> WorkerResult:
        raise NotImplementedError("implemented in M3-T004")
```

## Acceptance criteria
```bash
python -c "
from src.worker._types import JobPolicy, WorkerResult, ToolCallRecord
from src.worker.tools import TOOL_SCHEMAS, ToolExecutor, ApprovalRequired
from src.worker.budget import BudgetTracker

# Tool count
assert len(TOOL_SCHEMAS) == 5, len(TOOL_SCHEMAS)

# Path traversal rejected
import pathlib, tempfile
ws = pathlib.Path(tempfile.mkdtemp())
ex = ToolExecutor(ws, JobPolicy())
r = ex.execute('read_file', {'path': '../../../etc/passwd'})
assert 'path traversal' in r.lower(), r

# Bash deny list
r2 = ex.execute('run_bash', {'command': 'rm -rf /'})
import json; parsed = json.loads(r2)
assert parsed['exit_code'] == 126, parsed

# Budget stop at max_turns=1
bt = BudgetTracker(JobPolicy(max_turns=1))
bt.record_turn(100, 50)
assert bt.check_limits() == 'max_turns'

print('all ok')
"
```

## Stop condition
Stop after 30 turns. No real API calls in this task — everything is scaffolding.
