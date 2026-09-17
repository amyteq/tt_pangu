---
name: kg-run
description: Initialize a run artifact directory under runs/<competition>/<run_id>/ and record metrics, via the kca CLI. Use when starting a new experiment.
---

# kg-run — experiment run artifact management

Use this skill when starting any experiment that needs a recorded baseline: hypothesis, metrics, logs, and output artifacts in one structured place.

## Layout

`kca run init` produces:

```
runs/<competition>/<run_id>/
  meta.json      ← competition, run_id, created_at, hypothesis, tags
  config.json    ← parameters/config snapshot (starts {})
  metrics.json   ← {"<key>": {"value": <float>, "recorded_at": "<iso>"}, ...}
  logs/          ← log files
  artifacts/     ← output files (predictions, weights, etc.)
```

`runs/` is in `.gitignore`. Never commit it.

## Commands

Initialize a run:

```
python tools/kca/kca.py run init --competition <slug> [--run-id <id>] \
  --hypothesis "<one-sentence hypothesis>" [--tag <tag> ...] --json
```

`run_id` defaults to UTC `YYYYMMDD_HHMMSS`.

Record a metric (after local validation, not before):

```
python tools/kca/kca.py run record-metric \
  --run-dir runs/<comp>/<run_id> --key cv_score --value 0.823 --json
```

List runs:

```
python tools/kca/kca.py run list [--competition <slug>] --json
```

## How to pick a hypothesis

A good hypothesis is one sentence that names the change and the expected effect.

- ✅ `"add target-encoded categorical features; expect +0.005 CV vs baseline"`
- ❌ `"try new features"` (too vague to compare against later)

## How to use the output

- `run_dir` is the path to record in experiment notes and Supabase later.
- Keep all `kca` and shell commands you ran inside `<run_dir>/logs/`.
- Drop submission files into `<run_dir>/artifacts/`.

## Safety

- Side effects: `LOCAL_WRITE` for `init` and `record-metric`; `READ_ONLY` for `list`.
- No network. Pure filesystem.
- Do not delete a run dir without human approval — runs are the audit trail.
