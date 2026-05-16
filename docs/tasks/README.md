# Task Specs

This directory contains task specification files for the `kaggle-code-agent` project.

Each file defines a discrete unit of work: goal, acceptance criteria, rules, expected output, and stop conditions.

## Naming convention

```
<milestone>-<sequence>-<short-description>.md
```

Example: `M0-T001-project-baseline.md`

## Current tasks

| File | Milestone | Status | Description |
|---|---|---|---|
| `M0-T001-project-baseline.md` | M0 | in progress | Repository baseline: docs, vocabulary, safety rules, test commands |
| `M1-T001.md` | M1 | proposed | Local Kaggle tooling wrapper skeleton (`tools/kca/`) |

## How to use these files

1. Read the task spec before starting any work.
2. Follow the "Read these files first" list in the spec.
3. Return a plan and wait for human approval before editing any files.
4. Record results and blockers in the post-edit summary.
5. Update the task status when complete.

## Source of truth

Task specs live in this repository. They are the authoritative scope definition for any Claude Code session, ChatGPT session, Cursor session, or other AI tool working on this project. Hidden AI memory does not override the task spec.

## Related docs

- `docs/milestones.md` — high-level product plan (M0 through M10) with suggested task sequencing
- `docs/architecture/platform-vs-runtime-agents.md` — terminology: two meanings of "code agent"
- `AGENTS.md` — cross-tool development rules
- `CLAUDE.md` — Claude Code-specific rules and safety boundaries
