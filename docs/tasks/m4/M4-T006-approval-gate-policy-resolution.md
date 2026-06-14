# M4-T006: Approval gate policy resolution (ADR-0006 full implementation)

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Replace the hard-wired `KCA_ALLOW_REMOTE=1` env-var gate in `tools/kca/kg.py`
with the configurable per-project / per-competition / per-job policy from ADR-0006.
Wire the resolved policy into `src/worker/tools.py` (`ToolExecutor`) and
`scripts/run_job.py`.

## Read first
1. `docs/adr/0006-configurable-approval-gates.md` — policy schema and resolution order
2. `tools/kca/kg.py` — current `_gate()` function using `KCA_ALLOW_REMOTE`
3. `src/worker/tools.py` — `ToolExecutor`, `ApprovalRequired`
4. `src/worker/_types.py` — `JobPolicy` (currently has `allowed_tool_patterns`, `max_side_effect`)
5. `scripts/run_job.py` — `_build_policy(args)`

## Changes

### 1. `src/worker/_types.py` — add `approval_gates` to `JobPolicy`

```python
@dataclass
class JobPolicy:
    max_turns: int = 60
    max_cost_usd: float = 20.0
    max_runtime_s: int = 7200
    allowed_tool_patterns: list[str] = field(default_factory=lambda: ["kca *", "pytest *"])
    model: str = "claude-sonnet-4-6"
    max_side_effect: str = "SUBMISSION"
    approval_gates: dict = field(default_factory=lambda: {   # ADR-0006 defaults
        "kaggle_submit":    False,
        "kernel_push":      False,
        "dataset_upload":   True,
        "git_push":         False,
        "git_force_push":   True,
        "supabase_migrate": True,
        "delete_artifact":  True,
    })
```

### 2. `tools/kca/kg.py` — replace `_gate()` with policy-aware check

```python
OPERATION_DEFAULTS = {
    "kaggle_submit":    False,
    "kernel_push":      False,
    "dataset_upload":   True,
    "git_push":         False,
    "git_force_push":   True,
    "supabase_migrate": True,
    "delete_artifact":  True,
}

def _check_approval_gate(operation: str, policy: dict) -> None:
    """Raise ApprovalRequired if the operation requires human approval per policy."""
    from _types import ApprovalRequired   # or define locally
    gates = policy.get("approval_gates", {})
    requires = gates.get(operation, OPERATION_DEFAULTS.get(operation, True))
    # Emergency escape hatch: KCA_ALLOW_REMOTE=1 bypasses any gate (CI / scripted).
    if requires and not os.environ.get("KCA_ALLOW_REMOTE"):
        raise ApprovalRequired(operation, policy)
```

Keep `KCA_ALLOW_REMOTE` as a CI override but make it secondary to the policy dict.

### 3. Policy resolution in `scripts/run_job.py`

Add `_resolve_policy(args, project_row, competition_row)`:

```python
def _resolve_policy(args, project_row=None, competition_row=None) -> JobPolicy:
    """Merge: platform defaults ← project gates ← competition gates ← per-job override."""
    base = JobPolicy()   # platform defaults
    if project_row and project_row.get("approval_gates"):
        base.approval_gates.update(project_row["approval_gates"])
    if competition_row and competition_row.get("competition_policy", {}).get("approval_gates"):
        # Competition can only tighten, not loosen.
        comp_gates = competition_row["competition_policy"]["approval_gates"]
        for op, requires in comp_gates.items():
            if requires:   # can set True (require); cannot set False (skip)
                base.approval_gates[op] = True
    if args.require_approval:  # per-job override flag
        for op in args.require_approval:
            base.approval_gates[op] = True
    base.max_turns = args.max_turns
    base.max_cost_usd = args.max_cost_usd
    base.model = args.model
    return base
```

New CLI flag: `--require-approval <operation>` (nargs `+`).

### 4. `src/worker/tools.py` — pass policy into `ToolExecutor`

`ToolExecutor.__init__` already receives `policy: JobPolicy`. Add a call to
`_check_approval_gate` before executing any REMOTE_WRITE or SUBMISSION bash command.

```python
def _check_gate(self, operation: str) -> None:
    """Raise ApprovalRequired if this operation requires human approval."""
    from tools.kca import kg  # optional import — skip if not installed
    try:
        kg._check_approval_gate(operation, vars(self.policy))
    except ImportError:
        pass
```

Identify the operation from the bash command pattern (e.g., `kca kaggle submit` → `kaggle_submit`).

## Acceptance criteria
- Default policy: `kca kaggle submit` without `KCA_ALLOW_REMOTE=1` is NOT blocked
  (approval_gates.kaggle_submit = False by default per ADR-0006).
- `--require-approval kaggle_submit` in `run_job.py` sets the gate; worker pauses and
  records a `human_decisions` row.
- `KCA_ALLOW_REMOTE=1` still bypasses any gate (CI compatibility).
- `python -m pytest tests/ -v` — 0 failures (smoke tests cover gate logic).

## Stop condition
Stop after 40 turns. If circular imports between `tools.kca.kg` and `src.worker.tools`
occur, resolve by moving `ApprovalRequired` to `src/worker/_types.py` and importing
from there in both modules.
