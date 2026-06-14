# M7-T003: Tool registry

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 3; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/agent/tool_registry.py` — tool metadata (schema,
side-effect level, approval label, sandbox metadata) and policy-gated lookup.

## Read first
1. `tools/kca/agent/skill_loader.py`   (SkillMeta.allowed_tools)
2. `tools/kca/agent/command_registry.py`   (CommandSpec.side_effect pattern)
3. `docs/milestones/README.md`   (M7 — Tool layer description + permission policy design)
4. `docs/meeting-notes/2026-05-21-r1.md`   (§2 tools/kca/agent/tool_executor.py sketch)
5. `src/worker/worker.py`   (existing tool call pattern in the agent loop)

## Scope / Files / Implementation guidance

```python
@dataclass
class ToolSpec:
    name: str              # e.g. "bash", "read_file", "edit_file", "kaggle_submit"
    description: str
    side_effect: str       # READ_ONLY | LOCAL_WRITE | REMOTE_WRITE | SUBMISSION
    approval_label: str    # "allow" | "ask" | "deny" — default when no policy overrides
    timeout_s: int         # default execution timeout
    sandbox: str           # "sandboxed" | "unsandboxed" | "isolated_workspace"
    tags: list[str]        # e.g. ["filesystem", "network", "kaggle"]
    input_schema: dict     # minimal JSON Schema for the tool's input

TOOL_REGISTRY: dict[str, ToolSpec]
```

Populate TOOL_REGISTRY with at minimum these tools:
```
bash              LOCAL_WRITE  ask     30s  unsandboxed
read_file         READ_ONLY    allow   5s   sandboxed
edit_file         LOCAL_WRITE  allow   10s  sandboxed
write_file        LOCAL_WRITE  allow   10s  sandboxed
web_fetch         READ_ONLY    allow   30s  sandboxed
web_search        READ_ONLY    allow   30s  sandboxed
git_commit        LOCAL_WRITE  allow   30s  sandboxed
git_push          REMOTE_WRITE ask     30s  unsandboxed
gh_pr_create      REMOTE_WRITE allow   30s  unsandboxed
gh_pr_merge       REMOTE_WRITE ask     30s  unsandboxed
kaggle_submit     SUBMISSION   ask     60s  unsandboxed
kaggle_push       SUBMISSION   ask     60s  unsandboxed
supabase_migrate  REMOTE_WRITE ask     60s  unsandboxed
run_tests         LOCAL_WRITE  allow   120s sandboxed
litellm_call      LOCAL_WRITE  allow   120s sandboxed
create_artifact   LOCAL_WRITE  allow   10s  sandboxed
```

Helper functions:
```python
def get_tool(name: str) -> ToolSpec | None
def list_tools(*, side_effect: str | None = None, tag: str | None = None) -> list[ToolSpec]
def default_decision(tool_name: str) -> str   # returns approval_label or "ask" for unknowns
```

## Acceptance criteria

```python
from tools.kca.agent.tool_registry import TOOL_REGISTRY, get_tool, default_decision
assert get_tool('kaggle_submit').side_effect == 'SUBMISSION'
assert get_tool('read_file').approval_label == 'allow'
assert default_decision('kaggle_submit') == 'ask'
assert default_decision('__unknown__') == 'ask'
print(f'PASS: {len(TOOL_REGISTRY)} tools registered')
```

```python
from tools.kca.agent.tool_registry import list_tools
submissions = list_tools(side_effect='SUBMISSION')
assert len(submissions) >= 2
print(f'PASS: {[t.name for t in submissions]} are SUBMISSION tools')
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: registry count, SUBMISSION tools, test results.

## Stop condition
Stop after 30 turns.
