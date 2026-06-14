# M7-T009: Architecture doc

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 9; extracted here for the double-layer convention.

## Goal
Write `docs/architecture/kca-cli-architecture.md`.

## Read first
1. `docs/milestones/README.md`   (M7 section — full four-layer table + directory layout)
2. `docs/meeting-notes/2026-05-21-r1.md`   (§1–3)
3. `tools/kca/agent/skill_loader.py`   (SkillMeta fields)
4. `tools/kca/agent/tool_registry.py`   (ToolSpec fields)
5. `tools/kca/agent/permission_policy.py`   (PolicyRecord, PermissionPolicy)
6. `.kca/skills/run-milestone/SKILL.md`   (representative example)

## Scope / Files / Implementation guidance

Required sections:

### `## Overview`
One-paragraph product context. KCA CLI is the deterministic operator-facing
layer; skills are the agent-facing layer. Both share the same tool registry
and permission policy.

### `## Four layers`

Table: Layer | Implemented in | Invocation | Side-effect control
- Command: `tools/kca/*.py` | `kca <group> <cmd>` | `CommandSpec.side_effect`
- Skill: `.kca/skills/*/SKILL.md` | `kca skill run <name>` | `approval-policy` profile
- Tool: `tools/kca/agent/tool_registry.py` | called by agent worker | `ToolSpec.approval_label`
- Job: `src/worker/` + Supabase | `kca job run` | `JobPolicy` + budget tracker

### `## Skill format`
Document all YAML frontmatter fields with their types and defaults.
Show a minimal example.

### `## Tool registry`
List the fields of ToolSpec. Explain side_effect levels (READ_ONLY → SUBMISSION).
Note that SUBMISSION tools always default to "ask".

### `## Permission policy`
Explain the policy resolution priority:
```
deny > mode-specific allow > default_decision > ToolSpec.approval_label > "ask"
```
Show the PolicyRecord JSON example from `docs/milestones/README.md` M7.
Name the three shipped profiles: default, permissive-dev, competition-runner.

### `## Audit trail`
Explain `.agent/audit.jsonl` and how it relates to `agent_job_events`.
Note: `args_hash` not `args`, to avoid logging sensitive data.

### `## Decision gate UI flow`
Show the example from `docs/milestones/README.md` M7 / `docs/meeting-notes/2026-05-21-r1.md` §11:
"Agent reached decision gate: Submit run kca-run-123..."

### `## Directory layout`
Reproduce the layout table from `docs/milestones/README.md` M7.

### `## Adding a new command`
Step-by-step: create module → add CommandSpec to REGISTRY → add_parsers → done.

### `## Adding a new skill`
Step-by-step: `mkdir .kca/skills/<name>/` → write SKILL.md → `kca skill list` shows it.

### `## Adding a new tool`
Step-by-step: add ToolSpec to TOOL_REGISTRY → update permission policy if needed.

## Acceptance criteria

```
test -f docs/architecture/kca-cli-architecture.md
wc -l docs/architecture/kca-cli-architecture.md   → at least 80 lines
```

All section headings present:
```bash
for heading in "Overview" "Four layers" "Skill format" "Tool registry" \
               "Permission policy" "Audit trail" "Decision gate" \
               "Directory layout" "Adding a new command" "Adding a new skill" \
               "Adding a new tool"; do
  grep -q "$heading" docs/architecture/kca-cli-architecture.md \
    && echo "PASS $heading" || echo "FAIL $heading"
done
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: line count, section headings PASS/FAIL.

## Stop condition
Stop after 30 turns.
