# M1-T004: approval hooks for Kaggle remote-write and submission operations

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Add or strengthen Claude Code permissions/hooks so local `kca` wrappers are safe for agents to call, while dangerous Kaggle operations are blocked or require explicit human approval.

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `.claude/settings.json`
5. existing `.claude/hooks/*`
6. `docs/tooling/kca-side-effect-levels.md`
7. `docs/tooling/kca-command-spec.md`
8. `tools/legacy/TOOLS.md`
9. `tools/kca/` implementation

## Policy
Side-effect levels:

- `read-only`: safe to auto-run if it does not read secrets.
- `local-write`: safe to auto-run inside repo/temp workspace if paths are bounded.
- `remote-write`: requires human approval.
- `submission`: always requires human approval and should be blocked in automated tests.

## Commands that must never auto-run
Block or ask for explicit approval before commands matching these categories:

```text
kaggle competitions submit ...
kaggle kernels push ...
kaggle kernels output ...      # if it triggers remote execution or upload
kaggle datasets create ...
kaggle datasets version ...
kaggle models ...              # if uploading/updating remote resources
python tools/legacy/*submit* ...
python tools/legacy/*kernel*push* ...
python tools/legacy/*upload* ...
python -m tools.kca kaggle submit ...
python -m tools.kca kaggle kernel push ...
kca kaggle submit ...
kca kaggle kernel push ...
```

Read-only Kaggle commands such as list/files/status may be allowed if they do not expose secrets, but this task should be conservative.

## Implementation guidance
- Prefer a `PreToolUse` hook for `Bash` commands.
- Use hook JSON output with `permissionDecision: "ask"` for human approval where supported.
- Use deny/block for automated tests and obviously dangerous commands.
- Ensure `.claude/settings.json` also denies secrets reads:
  - `.env`
  - `secrets/**`
  - `~/.kaggle/kaggle.json`
- Add small hook unit tests or script-level tests by feeding sample JSON into the hook.

## Expected files to create or update
Adapt to existing structure:

- `.claude/settings.json`
- `.claude/hooks/guard_tool.py` or equivalent
- `tests/test_claude_hooks_guard_tool.py` or `tests/test_kca_guard_tool.py`
- `docs/tooling/kca-side-effect-levels.md`
- `docs/tooling/kaggle-approval-policy.md`

## Acceptance criteria
- A simulated `kaggle competitions submit ...` Bash tool call is blocked or requires approval.
- A simulated `kaggle kernels push ...` Bash tool call is blocked or requires approval.
- Local `python -m tools.kca notebook ...` commands are not blocked.
- Reading `.env` or known secret paths is denied.
- Tests pass.
- No real Kaggle command is executed during tests.

## Suggested tests
Use synthetic JSON input only. Example shape:

```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "kaggle competitions submit -c some-comp -f submission.csv -m test"
  }
}
```

Suggested shell pattern:

```bash
printf '%s\n' '<json here>' | python .claude/hooks/guard_tool.py
python -m pytest -q tests/test_kca_guard_tool.py
```

## Non-goals
- Do not build a UI approval queue yet.
- Do not integrate Supabase approval records yet.
- Do not make real Kaggle submissions.
- Do not bypass Claude permissions.

## Stop condition
Stop after 70 turns if existing hooks/settings are incompatible. Summarize exact blocker and leave the repo safer than before.
