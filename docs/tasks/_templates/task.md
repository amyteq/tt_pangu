---
id: <MILESTONE>-T<NNN>
title: <short title>
kind: claude-code-task
status: draft        # draft | ready | in-progress | done | deferred
milestone: <M{N} or category>
owner: human
created: <YYYY-MM-DD>
remote_side_effects: forbidden   # forbidden | requires-approval
---

# Task: <title>

## Mission

<One paragraph: what this task delivers and why.>

## Read first

- `CLAUDE.md`
- `docs/milestone-loop-protocol.md`
- <other files the executor must read before editing>

## Allowed paths

- <glob/**>

## Forbidden paths

- <glob/**>

## Allowed actions

- <what the executor may do>

## Forbidden actions

- <what the executor must not do>

## Acceptance criteria

This task is complete when all are true:

- <criterion 1>
- <criterion 2>

## Stop conditions

Stop and summarize blockers if:

- <condition 1>
- acceptance criteria are met.

## Validation commands

```bash
# lightweight checks the executor should run
```

## Final response requirements

Report: files created / moved / modified / deleted (with reasons), validation
results, whether acceptance criteria passed, risks, and recommended follow-ups.
