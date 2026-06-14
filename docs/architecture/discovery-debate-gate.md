# Discovery / Debate Gate

_Status: M9.4 ships the gate (this doc + protocol §7 + the three agents). The
`.claude/skills/design-archaeology/SKILL.md` orchestration the gate
references is owned by M9.3; M9.3-T001 must land that skill before §7
becomes fully enforceable end-to-end._

## What this is

The Discovery / Debate Gate is the M9.4-shipped guardrail that turns
"please be more proactive in plan / design / architect mode" into a
**checkable artefact**. Three role-isolated subagents run before any
implementation work begins on an architecture-shaped or
legacy-migration-shaped task. Each agent has a canonical acceptance
line that the parent session verifies; the three lines together form
the gate.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 — the observation
that the original `tools/legacy/kkr.py` migration missed
multi-Kaggle-account / owner / env semantics because no agent role
was responsible for surfacing them.

## Agents

| Agent | File | Phase | Reads | Emits |
|---|---|---|---|---|
| `legacy-archaeologist` | `.claude/agents/legacy-archaeologist.md` | 1 of 3 | legacy artefacts (read-only) | 10-section archaeology report |
| `requirements-skeptic` | `.claude/agents/requirements-skeptic.md` | 2 of 3 | proposed task spec + archaeology report | numbered question list across 5 categories + `explicit_unknowns:` |
| `design-red-team` | `.claude/agents/design-red-team.md` | 3 of 3 | proposed design + archaeology + skeptic reports | ≥3 alternatives, dropped-capability evidence, 4 cost axes, open disagreements |

Hand-off order is **archaeology → skepticism → red-team**. Skipping a
phase is not allowed when the gate is mandatory (see §"When the gate
fires" below). The orchestration mechanism is
`.claude/skills/design-archaeology/SKILL.md` (owned by M9.3); until
that skill file is on disk, the gate runs by direct subagent
invocation against this doc.

## Acceptance lines (verbatim — union of all three agents)

A parent session verifies these three lines, byte-for-byte, against
the three agents' outputs. Failing any one of them means the gate
did not pass.

> Output MUST contain ≥5 questions spread across ≥3 categories, and
> an `explicit_unknowns:` section listing things the agent could not
> answer without human input.

> Output MUST cover all 10 sections; ≥5 distinct legacy behavior
> dimensions must be named explicitly, including any multi-account /
> owner / env mapping the legacy artefact encodes.

> Output MUST include ≥3 alternatives, ≥1 dropped capability with
> file:line evidence, all four long-term-cost axes, and ≥1
> actionable `open_disagreements` entry.

## When the gate fires

The gate is **mandatory** for any task whose spec carries one of the
two task tags in its `## Milestone` line, first heading, or front-matter:

- `arch:` — the task introduces or substantially revises an
  architectural primitive (worker, runner, sandbox, queue, telemetry
  pipeline, schema dimension, permission policy).
- `legacy-migration:` — the task migrates, rewrites, replaces, or
  takes over a legacy tool / config / notebook.

Routine tasks (bug fixes, doc edits, dependency bumps, small
refactors inside an existing primitive) do **not** trigger the gate.
The tag is added by the human authoring the task spec, not inferred
by an agent.

When the gate fires, the executing session MUST:

1. Invoke `legacy-archaeologist` first if the task touches any legacy
   artefact. (Skip for greenfield `arch:` tasks with no legacy code
   in scope.)
2. Invoke `requirements-skeptic` next, regardless.
3. Invoke `design-red-team` last, regardless.
4. Attach the three reports to the task closeout under
   `docs/evidence/<milestone>/<task>/discovery/`:
   - `legacy-archaeologist.md` (skip allowed only with explicit note)
   - `requirements-skeptic.md`
   - `design-red-team.md`
5. Verify all three acceptance lines (above) byte-for-byte against
   the reports. Failure to verify is a task-spec FAIL — not a vibe.

## Task tag convention

Tag placement options (any of these is acceptable; the parent session
should grep all three):

```markdown
## Milestone
M11.3: arch: new sandbox runner

# legacy-migration: M9.4-T002 legacy-archaeologist agent scaffold
```

or in YAML front-matter:

```yaml
tags: [arch, sandbox]
```

The tag is **opt-in by the task author** and reviewed by the human
who approves the task spec. M9.4 does not auto-attach tags.

## Closeout evidence path

```
docs/evidence/<milestone>/<task>/discovery/
  legacy-archaeologist.md
  requirements-skeptic.md
  design-red-team.md
```

`<milestone>` follows the existing convention (`m9_4`, `m10`, `m11_3`).
`<task>` follows the existing task-id convention
(`M9_4-T005-kkr-replay-and-smoke`, etc).

## Relationship to M9.3's `design-archaeology` skill

The skill in M9.3 encodes a 10-section archaeology *template* that any
session can run inline. The `legacy-archaeologist` agent in M9.4
emits the same 10-section report shape but in a role-isolated subagent
context: read-only tools, `permissionMode: plan`, no shell. Use the
skill for lightweight inline analysis; use the agent (via this gate)
when the task is large enough to warrant a separate subagent and a
gate-level acceptance check.

The two are deliberately compatible: the agent's output schema is a
strict subset of the skill's template, so a parent session can swap
between them without rewriting downstream consumers.

## Non-enforcement (M9.4 scope boundary)

M9.4 enforces the gate via **acceptance criteria** in task specs and
the milestone-loop-protocol §7 wording — not via tool-level denials
or hook-based blocks. Hook-based enforcement (e.g. a PreToolUse hook
that refuses `Edit` on `src/**` when an `arch:` task has no
`discovery/` evidence) is a deferred follow-up. File it as a separate
issue if you want it built.

## Cross-references

- Milestone protocol additive section: `docs/milestone-loop-protocol.md` §7.
- M9.4 planning: `docs/milestones/m9_4/loop-prompts.md`.
- M9.3 skill (sibling milestone): `docs/milestones/m9_3/loop-prompts.md`,
  `.claude/skills/design-archaeology/SKILL.md` (M9.3-T001).
- Origin observation: `docs/meeting-notes/2026-05-24-r3.md` §6.
