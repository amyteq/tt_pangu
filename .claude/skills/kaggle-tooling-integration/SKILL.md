---
name: kaggle-tooling-integration
description: Use when integrating or invoking Kaggle helper scripts such as notebook conversion, kernel push, competition submission, result retrieval, and experiment artifact recording.
---

# Kaggle Tooling Integration Skill

## Purpose
Use project-approved wrappers for Kaggle operations. Do not call ad hoc scripts directly unless the user explicitly asks and the command has been reviewed.

## Workflow
1. Identify the tool category: read-only, local-write, remote-write, or submission.
2. Prefer `kca ...` wrapper commands when available.
3. For remote-write or submission actions, prepare a human approval request instead of executing directly.
4. Record outputs into `runs/<competition_slug>/<run_id>/`.
5. Summarize result, metric, artifact paths, and next action.

## Required approval for submissions
Before a Kaggle submission, present:
- competition slug.
- file path.
- submission message.
- validation score and metric direction.
- daily submission count if known.
- expected risk or uncertainty.

Do not submit until explicit approval is given.

## Safety
Never print or read Kaggle credentials. Never commit API tokens. Never bypass daily submission limits or competition rules.
