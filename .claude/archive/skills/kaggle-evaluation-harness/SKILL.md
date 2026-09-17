---
name: kaggle-evaluation-harness
description: Use when creating, running, or improving validation/evaluation loops for Kaggle competitions and competition-like benchmarks.
---

> **Archived (issue #192) — not loaded by any harness.** Retired in favour of `kg-audit`, which carries the same leakage / split / metric / reproducibility / rules review with the tool calls and repo paths this checklist never had. Kept as history: read it as a record of what the project once instructed, not as instruction. See `.claude/archive/skills/README.md`.

# Kaggle Evaluation Harness Skill

## Goal
Create reliable local validation before public leaderboard submissions.

## Checklist
- Read metric definition and direction.
- Confirm train/test split and leakage risks.
- Establish a reproducible baseline.
- Save configuration and seed.
- Run one controlled experiment at a time.
- Record metrics and artifacts.
- Compare against baseline.
- Decide whether to iterate or request human review.

## Run output
Each experiment should produce:
- `config.yaml`
- `metrics.json`
- `log.txt`
- `notes.md`
- optional `submission.csv`
- optional `code_snapshot.patch`

## Anti-patterns
- Optimizing only to public leaderboard.
- Changing multiple variables without recording them.
- Reusing test labels or leaked artifacts.
- Submitting without a local validation rationale.
