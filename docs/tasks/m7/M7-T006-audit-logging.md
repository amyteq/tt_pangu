# M7-T006: Audit logging

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 6; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/agent/audit.py` — records policy decisions for tool
executions, outside the worker agent loop (M7 scope: CLI-level audit).

## Read first
1. `tools/kca/agent/permission_policy.py`   (resolve, PolicyRecord)
2. `tools/kca/agent/tool_registry.py`   (ToolSpec.audit_required equivalent: approval_label != "allow")
3. `tools/kca/db.py`   (append_job_event pattern)
4. `src/worker/telemetry.py`   (OTEL span structure from M6)
5. `tools/kca/agent/skill_loader.py`   (SkillMeta.approval_policy)

## Scope / Files / Implementation guidance

AuditRecord:
```
timestamp: str (ISO 8601)
session_id: str (uuid4, stable per kca process invocation)
skill_name: str | None
tool_name: str
operation: str
decision: str   # allow | ask | deny
mode: str
policy_profile: str
audit_required: bool
args_hash: str  # sha256 of serialised args, not the args themselves
```

AuditLogger:
```
backend: "file" | "db" | "both"
file_path: Path (default: .agent/audit.jsonl)
db_available: bool

def record(self, rec: AuditRecord) -> None
  - Appends a JSON line to file_path (never raises; on error: stderr warning).
  - If db_available: append_job_event(job_id=None, event_type="tool_audit",
      event_data=rec.__dict__) — best-effort.

def log_policy_decision(self, *, tool: str, operation: str, decision: str,
                         skill_name: str | None = None, mode: str = "default",
                         policy_profile: str = "default",
                         args: dict | None = None) -> AuditRecord
```

Wire into `kca skill run` (non-dry-run path only):
- For each tool in `allowed_tools`: `log_policy_decision(...)`.
- Write `.agent/audit.jsonl` line.

Provide a CLI view:
```
kca tool audit [--limit 20] [--json]
```

Add "tool" group to `kca.py`:
```
kca tool list [--tag <tag>] [--json]       → TOOL_REGISTRY contents
kca tool audit [--limit 20] [--json]       → last N lines of .agent/audit.jsonl
kca tool doctor [--json]                   → check all tools in TOOL_REGISTRY have
                                              valid side_effect, timeout_s, sandbox
```

## Acceptance criteria

Trigger a skill run (non-dry-run) to produce an audit record:
```
python tools/kca/kca.py skill run _test_fixture \
  --arg task_path=docs/tasks/m7/M7-T001.md --json
  → ok + note about M7 non-execution
```

Audit log produced:
```python
test -f .agent/audit.jsonl
import json
lines = open('.agent/audit.jsonl').readlines()
assert len(lines) >= 1
rec = json.loads(lines[-1])
assert rec['tool_name'] in ('read_file', 'bash')
assert rec['decision'] in ('allow', 'ask', 'deny')
print('PASS audit record:', rec['tool_name'], rec['decision'])
```

```
python tools/kca/kca.py tool list --json
  → {"ok": true, "tools": [...], "side_effect": "READ_ONLY"}

python tools/kca/kca.py tool doctor --json
  → {"ok": true, "tools_checked": <N>, "issues": []}

python tools/kca/kca.py tool audit --json
  → {"ok": true, "records": [...], "side_effect": "READ_ONLY"}
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: audit.jsonl content + tool subcommands.

## Stop condition
Stop after 30 turns.
