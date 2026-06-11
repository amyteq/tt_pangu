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

## Kernel/version model, structure & concurrency
For code-competition (notebook/kernel) work, follow `docs/tooling/kaggle-kernel-ops.md`. Key rules:
- **Versions are latest-only via API** — `kaggle kernels output/status` expose only the latest run, and stale `-v` is unreliable. Submit the just-pushed (latest) version (omit `--version` in `kca kaggle submit --kernel …`).
- **Flat structure**: one kernel per candidate/direction (variant in the slug, e.g. `nemotron-cot-r32-s400`) so every candidate stays retrievable and can run in parallel. Single-kernel-many-versions is for throwaway iteration only.
- **Concurrency is per *account*, global**: ~1 concurrent GPU session + floating ~30 h/week quota (resets Sat 00:00 UTC). Submission limits are per competition team, per day. Maximise throughput with flat parallel kernels, bounded runs, keeping non-GPU work off the quota, and overflow compute (local 4090/3090 for models that fit; external GPU under evaluation).
- **Pre-push hygiene**: static lint (`kca kaggle push` gate / `validate_kernel.py`), a fail-fast eval preflight, and isolating non-essential steps — never waste a multi-hour GPU run on a typo.

## Safety
Never print or read Kaggle credentials. Never commit API tokens. Never bypass daily submission limits or competition rules.
