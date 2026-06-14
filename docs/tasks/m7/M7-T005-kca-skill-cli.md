# M7-T005: `kca skill list/show/run` CLI

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 5; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/skill.py` with `list`, `show`, and `run` subcommands;
register with `kca.py`.

## Read first
1. `tools/kca/agent/skill_loader.py`   (load_skill, list_skills, render_skill)
2. `tools/kca/agent/permission_policy.py`   (resolve_for_skill, load_policy)
3. `tools/kca/agent/tool_registry.py`   (list_tools, default_decision)
4. `tools/kca/kca.py`   (build_parser, add_parsers pattern)
5. `tools/kca/decisions.py`   (--json output style)

## Scope / Files / Implementation guidance

`kca skill list [--json] [--tag <tag>]`
- Output: list of `{name, description, version, approval_policy, tags}` dicts.
- Human format: table with name | description | policy.

`kca skill show <name> [--json]`
- Output: full parsed metadata dict + rendered frontmatter fields + body
  (body not rendered — raw SKILL.md body).

`kca skill run <name> [--arg key=value ...] [--mode <mode>] [--dry-run] [--json]`
Workflow:
1. `load_skill(name)`
2. Parse `--arg` pairs into a dict; validate all declared arguments are present.
   If a declared argument is missing: error, list required args.
3. `render_skill(skill, arg_dict)` → `rendered_body`
4. For each tool in `SkillMeta.allowed_tools`:
   ```
   decision = resolve_for_skill(skill.meta, tool, mode=args.mode)
   record: {tool, decision, reason}
   ```
5. `--dry-run` output (`--json`):
   ```json
   {
     "ok": true,
     "dry_run": true,
     "skill": "<name>",
     "mode": "<mode>",
     "args": {},
     "tool_permissions": [{"tool": "<t>", "decision": "<d>", "reason": "<r>"}],
     "rendered_prompt": "<rendered_body>",
     "side_effect": "READ_ONLY"
   }
   ```
6. Without `--dry-run`: print rendered_body and tool_permissions, then emit
   `{"ok": true, "dry_run": false, "note": "actual execution not implemented in M7 — use kca job run"}`
   (Actual job execution is M8 scope; M7 delivers the CLI surface only.)

Parsers:
```
sub.add_parser("skill")  → skill_parser with subparsers: list / show / run
```

Register in `kca.py`:
```python
import skill as skill_mod
skill_mod.add_parsers(sub)
```

## Acceptance criteria

```
python tools/kca/kca.py skill list
  → prints table with at least _test_fixture row (created in T001)

python tools/kca/kca.py skill list --json
  → {"ok": true, "skills": [...], "side_effect": "READ_ONLY"}

python tools/kca/kca.py skill show _test_fixture
  → prints name, description, allowed-tools, approval-policy, body

python tools/kca/kca.py skill show _test_fixture --json
  → {"ok": true, "skill": {"name": "_test_fixture", ...}, "side_effect": "READ_ONLY"}

python tools/kca/kca.py skill run _test_fixture \
  --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json
  → {
      "ok": true, "dry_run": true, "skill": "_test_fixture",
      "tool_permissions": [{"tool": "read_file", ...}, {"tool": "bash", ...}],
      "rendered_prompt": "Run task at docs/tasks/m7/M7-T001.md.\nCheck output.",
      "side_effect": "READ_ONLY"
    }

# Missing required arg → error
python tools/kca/kca.py skill run _test_fixture --dry-run --json
  → exit code != 0 or {"ok": false, "error": "missing argument: task_path"}
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: each verification, exit code behaviour.

## Stop condition
Stop after 30 turns.
