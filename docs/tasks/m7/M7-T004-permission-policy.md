# M7-T004: Permission policy layer

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 4; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/agent/permission_policy.py` — resolves `allow | ask | deny`
for any `(operation, mode)` pair from a structured YAML/JSON policy file. Same
semantics as Claude Code's `settings.json` but product-level and data-driven.

## Read first
1. `tools/kca/agent/tool_registry.py`   (ToolSpec.approval_label, TOOL_REGISTRY)
2. `tools/kca/agent/skill_loader.py`   (SkillMeta.approval_policy)
3. `docs/milestones/README.md`   (M7 — permission policy design block)
4. `docs/meeting-notes/2026-05-21-r1.md`   (§2 permissions/ layout, §11 policy JSON)
5. `tools/kca/kg.py`   (_check_approval_gate pattern for comparison)

## Scope / Files / Implementation guidance

PolicyRecord (maps to a JSON policy record per docs/milestones/README.md M7):
```
operation: str
default_decision: str      # "allow" | "ask" | "deny"
reason: str
allowed_in_modes: list[str]
audit_required: bool
```

PermissionPolicy:
- Loaded from a YAML file (e.g. `.kca/permissions/default.yaml`).
- Each policy file is a list of PolicyRecord objects.
- `resolve(operation, mode="default") -> str`
  Returns "allow", "ask", or "deny". Priority:
  1. Explicit deny in policy → "deny" (never overridden by mode).
  2. `operation in allowed_in_modes` for the given mode → "allow".
  3. `default_decision` from matching PolicyRecord.
  4. `ToolSpec.approval_label` for the operation name (if registered).
  5. "ask" (safe default).

Also write three seed policy YAML files:

`.kca/permissions/default.yaml`:
- All SUBMISSION operations: ask
- git_push, gh_pr_create: allow
- gh_pr_merge: ask
- supabase_migrate: ask
- bash: ask
- All filesystem read/write within workspace: allow

`.kca/permissions/permissive-dev.yaml`:
- kaggle_submit, kaggle_push: ask (still gated, even in dev)
- supabase_migrate (remote): ask
- gh_pr_merge: ask
- Everything else normally covered by default: allow

`.kca/permissions/competition-runner.yaml`:
- kaggle_submit in mode competition-finalization: allow
- kaggle_submit in mode human-approved: allow
- All other submission ops: ask
- budget_exceeded: deny

Helpers:
```python
def load_policy(profile: str, *, permissions_root: Path | None = None) -> PermissionPolicy
def resolve_for_skill(skill_meta: SkillMeta, operation: str, mode: str = "default") -> str
```

## Acceptance criteria

```python
from tools.kca.agent.permission_policy import load_policy, resolve_for_skill
from tools.kca.agent.skill_loader import load_skill

# default policy
p = load_policy('default')
assert p.resolve('kaggle_submit') == 'ask', p.resolve('kaggle_submit')
assert p.resolve('read_file') == 'allow', p.resolve('read_file')
assert p.resolve('gh_pr_merge') == 'ask', p.resolve('gh_pr_merge')
print('PASS default policy')

# permissive-dev: bash allowed
pd = load_policy('permissive-dev')
assert pd.resolve('bash') == 'allow', pd.resolve('bash')
assert pd.resolve('kaggle_submit') == 'ask'
print('PASS permissive-dev policy')

# competition-runner: submit allowed in competition-finalization mode
cr = load_policy('competition-runner')
assert cr.resolve('kaggle_submit', mode='competition-finalization') == 'allow'
assert cr.resolve('kaggle_submit', mode='default') == 'ask'
print('PASS competition-runner policy')
```

`resolve_for_skill` reads the skill's `approval-policy` field:
```python
from tools.kca.agent.permission_policy import resolve_for_skill
from tools.kca.agent.skill_loader import load_skill
s = load_skill('_test_fixture')   # has approval-policy: permissive-dev
assert resolve_for_skill(s.meta, 'bash') == 'allow'
print('PASS resolve_for_skill')
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: all policy assertions + test results.

## Stop condition
Stop after 30 turns.
