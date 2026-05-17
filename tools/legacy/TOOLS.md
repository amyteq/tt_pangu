# Tool Contracts

This file documents stable local tool usage.
It does not grant permissions. It is guidance only.

## General rules

- Always prefer `--json` when available.
- Use exit code + JSON stdout only.
- Do not infer status from stderr.
- Do not guess paths when the tool returns a structured path or run_id.
- Persist run/task results to sqlite after each successful tool step.

## nb2test.py

Purpose:
- build or refresh a deterministic test notebook from a source notebook

Allowed patterns:
- `nb2test.py SOURCE.ipynb --json`
- `nb2test.py SOURCE.ipynb DEST.ipynb --json`
- `nb2test.py SOURCE.ipynb DEST.ipynb --json --dry-run`

Rules:
- prefer `--dry-run` before destructive or repeated refreshes
- trust JSON field `dst`
- do not construct destination paths manually
- remember: non-code, `stub`, `xtest`, `debug*` are dropped
- `head` cells stay in front
- same-source cells are replaced as a block

## jrun.py

Purpose:
- run test notebooks on the internal Jupyter/worker environment

Only allowed chain:
1. `jrun.py submit NOTEBOOK.ipynb --target HOST --json [artifact args]`
2. `jrun.py watch RUN_ID --json --bootstrap-timeout 30 --heartbeat-timeout 90 --timeout 0`
3. `jrun.py fetch RUN_ID --json`

Rules:
- do not implement custom sleep polling
- `watch` owns timeout/polling logic
- `fetch` only after `watch` exit code 0
- declare extra artifacts at submit time

Truth files:
- live: `.jrun/<run_id>/state.json`
- terminal: `.jrun/<run_id>/summary.json`

## kkr.py

Purpose:
- stage, push, watch, fetch, and submit Kaggle notebook runs

Allowed chains:
- remote smoke:
  1. `kkr.py push NAME --json`
  2. `kkr.py watch --run RUN_ID --json --interval 60`
  3. `kkr.py fetch --run RUN_ID --json`

- final submission:
  1. `kkr.py submit NAME --json --wait --interval 60`
  2. optional `kkr.py fetch --run RUN_ID --json`

Rules:
- `watch` is the only polling entrypoint
- always prefer `run_id`
- never guess next version label
- `list --refresh --json` before new GPU push/submit
- if queue is full, do local work instead of idling

Artifact truth source:
- `.kkr/<RUN_ID>/manifest.json`
- `.kkr/<RUN_ID>/state.json`
- `.kkr/<RUN_ID>/kkr_push.json`
- `.kkr/<RUN_ID>/kkr_watch.json`
- `.kkr/<RUN_ID>/kkr_fetch.json`
- `.kkr/<RUN_ID>/kkr_submit.json`
- `.kkr/<RUN_ID>/kkr_postprocess.json`

## nb2py.py / py2nb.py

Purpose:
- notebook round-trip editing

Policy:
- `.py` is the editable truth source
- `.ipynb` is an execution/submission artifact
- preserve stable cell markers, tags, and cell order
- never treat outputs as truth
- do not silently discard cell metadata required for downstream tools
