# KCA CLI Architecture

Status: M7 (2026-05-21).

## Overview

KCA (Kaggle / CTF Code Agent) exposes two operator interfaces over the same
core. The **CLI** (`kca …`) is the deterministic, scriptable surface humans
and CI use directly. **Skills** are the agent-facing surface: declarative
Markdown recipes with YAML frontmatter that the agent worker can render and
execute. Both layers share the same tool registry and permission policy, so a
human running `kca kaggle submit` and an agent executing the `prepare-submission`
skill go through identical approval gates and audit records. M7 ships the
inspectable scaffold for both; M8 wires skill execution through the worker.

## Four layers

| Layer | Implemented in | Invocation | Side-effect control |
|---|---|---|---|
| Command | `tools/kca/*.py` | `kca <group> <cmd>` | `CommandSpec.side_effect` |
| Skill | `.kca/skills/<name>/SKILL.md` | `kca skill run <name>` | `approval-policy` profile |
| Tool | `tools/kca/agent/tool_registry.py` | called by agent worker | `ToolSpec.approval_label` |
| Job | `src/worker/` + Supabase | `kca job run` (M8 wiring) | `JobPolicy` + budget tracker |

Each layer has narrow responsibilities. The Command layer never reaches inside
the agent loop; the Skill layer never executes shell directly — it always
goes through tools — and the Tool layer is the only place where real side
effects (filesystem writes, network, Kaggle submission) actually occur.

## Skill format

Skills live at `.kca/skills/<name>/SKILL.md`. The file is parsed as YAML
frontmatter followed by a Markdown body.

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | (required) | Slug used by `load_skill(name)`. Must match dir name. |
| `description` | string | (required) | One-line summary shown in `kca skill list`. |
| `version` | string | `"1.0"` | Free-form. |
| `argument-hint` | string | `""` | Human hint shown in CLI help. |
| `arguments` | list[string] | `[]` | Names of `$arg` tokens substituted into the body. |
| `allowed-tools` | list[string] | `[]` | Tool names from the tool registry. |
| `approval-policy` | string | `"default"` | Profile name in `.kca/permissions/`. |
| `disable-model-invocation` | bool | `false` | Reserved: prevent agent auto-invocation. |
| `tags` | list[string] | `[]` | Free-form labels for filtering. |

Body tokens of the form `$name` are substituted at render time. Undeclared
tokens are passed through verbatim. Declared arguments not provided at render
time raise `ValueError`.

Minimal example:

```
---
name: triage-log
description: Summarise a job's event log.
arguments:
  - job_id
allowed-tools:
  - read_file
  - litellm_call
approval-policy: permissive-dev
---
Triage job $job_id.
```

## Tool registry

`tools/kca/agent/tool_registry.py` exports `TOOL_REGISTRY: dict[str, ToolSpec]`.

`ToolSpec` fields:

| Field | Purpose |
|---|---|
| `name` | Unique tool identifier (e.g. `bash`, `kaggle_submit`). |
| `description` | One-line summary. |
| `side_effect` | `READ_ONLY` / `LOCAL_WRITE` / `REMOTE_WRITE` / `SUBMISSION`. |
| `approval_label` | Default policy decision: `allow` / `ask` / `deny`. |
| `timeout_s` | Default execution timeout. |
| `sandbox` | `sandboxed` / `unsandboxed` / `isolated_workspace`. |
| `tags` | Free-form labels (`filesystem`, `network`, `kaggle`, …). |
| `input_schema` | JSON-Schema fragment describing the tool's input. |

Side-effect ordering (least → most dangerous):
`READ_ONLY → LOCAL_WRITE → REMOTE_WRITE → SUBMISSION`.

Tools at the `SUBMISSION` level (`kaggle_submit`, `kaggle_push`) default to
`approval_label = "ask"`. Permission profiles can narrow this further but
should never unconditionally allow them.

## Permission policy

`tools/kca/agent/permission_policy.py` resolves an `allow | ask | deny`
decision for a given `(operation, mode)` pair. The resolution priority is:

1. **Explicit `deny`** in the policy record — never overridden by mode.
2. **`mode` in `allowed_in_modes`** for the operation → `allow`.
3. **`default_decision`** from the matching `PolicyRecord`.
4. **`ToolSpec.approval_label`** from the tool registry (if registered).
5. **`"ask"`** — the safe default.

A `PolicyRecord` (the JSON/YAML shape) looks like:

```json
{
  "operation": "kaggle_submit",
  "default_decision": "ask",
  "reason": "External leaderboard submission requires human approval.",
  "allowed_in_modes": ["competition-finalization", "human-approved"],
  "audit_required": true
}
```

Three profiles ship under `.kca/permissions/`:

- `default.yaml` — conservative. Submissions and remote-DB writes ask. Bash
  asks. Filesystem reads/writes allowed. Used by skills without an explicit
  `approval-policy`.
- `permissive-dev.yaml` — bash and routine git operations allowed. Submissions
  and merges still ask. Used by platform-dev skills like `run-milestone` and
  `review-pr`.
- `competition-runner.yaml` — `kaggle_submit` allowed only when `mode` is
  `competition-finalization` or `human-approved`. Includes a hard
  `budget_exceeded: deny` record so a paused-budget job can never resume into
  a submission.

## Audit trail

Every non-dry-run skill invocation records a JSONL line to `.agent/kca/audit.jsonl`
via `tools/kca/agent/audit.py`. An `AuditRecord` contains:

- `timestamp` (ISO 8601 UTC)
- `session_id` (UUID stable per process)
- `skill_name`
- `tool_name` / `operation`
- `decision` (`allow` / `ask` / `deny`)
- `mode` and `policy_profile`
- `audit_required` flag (mirrors the policy record)
- `args_hash` — SHA-256 of serialised args, **not the args themselves**, so
  sensitive values never enter the log.

When a DB is configured, the audit log also flows into the dedicated
`agent_tool_audit` table (migration `0007_m8_tool_audit.sql`, M8). The
view `v_agent_tool_audit_recent` returns the most recent 200 rows joined
against `agent_jobs` for operator queries. The M7-era best-effort write to
`agent_job_events` with `event_type="tool_audit"` is preserved for legacy
readers but is now deprecated — prefer the typed table.

Offline → DB backfill: `scripts/backfill_tool_audit.py` reads
`.agent/kca/audit.jsonl` and inserts missing rows into `agent_tool_audit`,
de-duplicating by `(session_id, ts, tool_name)`. Idempotent.

## Decision gate

When a tool resolves to `ask`, the agent writes a decision record and pauses.
The CLI surface for humans is:

```
Agent reached decision gate: Submit run kca-run-123 to Kaggle?
Operation: kaggle_submit
Skill: prepare-submission
Mode: competition-finalization
Audit: required
[approve] [deny] [explain]
```

A human responds via `kca decision approve <id>` / `deny <id>`, which appends
an `approval_resume` event and unblocks `scripts/run_job.py --job-id <uuid>`.

## Directory layout

```
.kca/
  skills/
    <name>/
      SKILL.md          # YAML frontmatter + body
  permissions/
    default.yaml
    permissive-dev.yaml
    competition-runner.yaml
.agent/
  audit.jsonl           # local audit log (gitignored)
tools/
  kca/
    kca.py              # CLI entry point; build_parser() uses REGISTRY
    agent/
      __init__.py
      command_registry.py
      skill_loader.py
      tool_registry.py
      permission_policy.py
      audit.py
    skill.py            # `kca skill list/show/run`
    tool.py             # `kca tool list/audit/doctor`
```

## Adding a new command

1. Write the module under `tools/kca/<name>.py` exposing `add_parsers(sub)`.
2. Register it in `command_registry._seed_registry()`:
   `REGISTRY.register(CommandSpec("<name>", "<desc>", side_effect, requires_db, mod.add_parsers))`.
3. `kca <name> --help` works immediately — `build_parser()` walks `REGISTRY`.
4. Add tests under `tests/` that exercise the JSON output path.

## Adding a new skill

1. `mkdir .kca/skills/<name>/` and write `SKILL.md` with frontmatter.
2. Declare `arguments`, `allowed-tools`, and an `approval-policy` profile.
3. Verify with `kca skill list` and
   `kca skill run <name> --arg key=value --dry-run --json`.
4. Add the skill name to any seed list in `docs/milestones/README.md`.

## Adding a new tool

1. Append a `_spec(...)` line to `_TOOLS` in
   `tools/kca/agent/tool_registry.py` with the correct `side_effect`,
   `approval_label`, `sandbox`, and `timeout_s`.
2. If the default `approval_label` is wrong for a given policy profile, add a
   `PolicyRecord` override in the relevant `.kca/permissions/<profile>.yaml`.
3. `kca tool doctor --json` must still return `issues: []`.
4. Add a registry-level test in `tests/test_m7_smoke.py`.
