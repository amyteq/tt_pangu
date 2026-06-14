# M8-T003: Skill → worker wiring + `ToolSpec` enforcement

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 3; extracted here for the double-layer convention.

## Goal
Implement the M7 follow-ups #1 and #4 together — `kca skill run` without
`--dry-run` now drives an `AgentWorker` whose tool calls are gated by the
M7 permission policy and respect the ToolSpec metadata.

## Read first
1. `src/worker/worker.py` (`_tool_call`, AgentWorker loop)
2. `src/worker/_types.py` (`JobPolicy`, `approval_gates`)
3. `src/worker/tools.py` (current tool dispatch)
4. `tools/kca/skill.py` (kca skill run handler)
5. `tools/kca/agent/tool_registry.py` (`ToolSpec.timeout_s`, sandbox, approval_label)
6. `tools/kca/agent/permission_policy.py` (`resolve_for_skill`)
7. `docs/milestones/m7/final-review.md` (§ M8 follow-ups #1 and #4)

## Scope / Files / Implementation guidance

### Step 1 — `kca skill run <name> [--mode <mode>] --execute` (or drop --dry-run to keep the existing flag shape)
- Build a `JobPolicy`:
  ```python
  policy = JobPolicy(
      skill_name=name,
      allowed_tools=skill.meta.allowed_tools,
      approval_gates={
          tool: resolve_for_skill(skill.meta, tool, mode=args.mode)
          for tool in skill.meta.allowed_tools
      },
      max_turns=..., max_cost_usd=..., max_runtime_s=...,
  )
  ```
- Create the `agent_job` row via
  `tools/kca/db.create_agent_job(skill_name=name, policy=policy, rendered_prompt=rendered_body, …)`.
- Hand to `AgentWorker.run(job_id)`.

### Step 2 — In `src/worker/worker.py::_tool_call`
- Resolve the `ToolSpec` via `tool_registry.get_tool(tool_name)`.
- Enforce `ToolSpec.timeout_s` as a hard timeout (use `signal/alarm` or
  `subprocess.run` timeout depending on the tool implementation).
- Honour `ToolSpec.sandbox`:
    - `"sandboxed"` → run in current process (no extra escape).
    - `"unsandboxed"` → require `approval_label` resolved to `"allow"`
      OR a satisfied approval gate from policy.
    - `"isolated_workspace"` → `cwd` must be the job's workspace path.
- Cross-check `JobPolicy.approval_gates[tool_name]`:
    - `"allow"` → proceed.
    - `"ask"` → write `human_decisions` row + `agent_job_events("decision_pending")`
      + return a paused-job marker; do NOT execute.
    - `"deny"` → raise `PolicyViolation`, mark job failed.
- On any decision, call `audit.log_policy_decision(...)` so the
  `agent_tool_audit` table records the outcome.

### Step 3 — Tests
- Extend `tests/test_m7_smoke.py` (or add `tests/test_m8_worker_wiring.py`)
  with three tests:
    a) `approval_gate "allow"` → tool executes, audit row records "allow".
    b) `approval_gate "ask"`   → job pauses, `human_decisions` row created,
       audit row records "ask", no side effect.
    c) `approval_gate "deny"`  → job fails, no side effect, audit row "deny".
- Use a fake `ToolSpec` (`"noop_test_tool"`) wired into `TOOL_REGISTRY` behind
  a `_register_test_tool()` helper guarded by `pytest`-only import — do
  not pollute the production registry.

## Acceptance criteria
- `python -m pytest tests/test_m8_worker_wiring.py -v` → 3 passed
- `python -m pytest tests/ -v -m "not db"` → 0 failures
- End-to-end smoke with a benign skill (no real Kaggle / GH side effects):
  ```bash
  python tools/kca/kca.py skill run triage-log \
    --arg job_id=00000000-0000-0000-0000-000000000000 --execute --json
  ```
  → `ok=true`, `job_id` returned, audit rows present (verify via
  `python tools/kca/kca.py tool audit --limit 3 --json`)
- Deny path: try to run a skill whose policy resolves to deny (use
  `competition-runner` profile + an op that returns deny). Confirm job
  ends with `status="failed"` and `human_decisions` has the row.

Report: 3 wiring tests, audit rows, end-to-end smoke job ID + status.

## Stop condition
Stop after 30 turns.
