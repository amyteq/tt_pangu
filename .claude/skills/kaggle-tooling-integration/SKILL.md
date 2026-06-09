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

## Kaggle in-kernel data mount paths
Inside a Kaggle kernel, **do not hardcode** the input mount. Since ~Feb 2026 Kaggle
adds a slug chunk to the path, so the same competition data may appear under either
form depending on the kernel's attached sources:

- Competition data: `/kaggle/input/competitions/<competition-slug>/` (newer) or
  `/kaggle/input/<competition-slug>/` (older).
- Datasets / models: `/kaggle/input/<owner>/<dataset-slug>/` (and utility-script /
  model mounts under `/kaggle/usr/lib/...` with the slug **slugified to underscores**,
  e.g. `nvidia-utility-script` → `nvidia_utility_script`).

Resolve robustly with a glob rather than a literal path, e.g.:

```python
import glob
cands = (glob.glob("/kaggle/input/competitions/*/train.csv")
         + glob.glob("/kaggle/input/*/train.csv")
         + glob.glob("/kaggle/input/**/train.csv", recursive=True))
train_csv = cands[0]  # raise if empty; print cands for diagnostics
```

A battle-tested resolver lives in `experiments/tpu-getting-started/baseline-tl/baseline.py`
(`_resolve_kaggle_input_path`): try `/kaggle/input/<slug>` then
`/kaggle/input/competitions/<slug>`, and on miss, list `/kaggle/input` contents so the
failure shows the real layout instead of an opaque "not found".

## Safety
Never print or read Kaggle credentials. Never commit API tokens. Never bypass daily submission limits or competition rules.
