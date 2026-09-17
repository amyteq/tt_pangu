---
name: kg-run
description: Initialize a run artifact directory under runs/<competition>/<run_id>/ and record metrics via the kca CLI, so that one execution attempt is one Run record. Use when starting or recording an experiment execution.
---

# kg-run — the run directory **is** the `Run` record

A mechanical wrapper around `kca run`, not a loop stage. `kg-run-experiment` owns `IMPLEMENT` → `TRAIN_VALIDATE` → `EVALUATE` and calls this skill to write the record; use this one directly only when you need the run directory without the surrounding stage — recording an ad-hoc execution, or listing what already exists.

**A run directory is a `Run` record, not a scratch folder.** `Experiment` is the design; `Run` is one execution attempt (ADR-0023 / issue #191). A retry is a **new** `run_id` and never overwrites the failed one, because the failure history is evidence. One experiment holds several runs — folds, seeds, resource configurations.

Until ADR-0023 merges, the directory below **is** the phase-1 serialization of that entity, and `meta.json` / `config.json` / `metrics.json` are where its fields live. Do not invent a second shape for the same record; when the contract lands, this layout is what gets mapped onto it.

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | Competition slug, a one-sentence hypothesis, optional tags and an optional explicit `run_id`. For `record-metric`: an existing run directory, a metric key and a value. |
| **Output schema** | `runs/<competition>/<run_id>/` with `meta.json` (competition, run id, created at, hypothesis, tags), `config.json` (parameters snapshot, starts `{}`), `metrics.json` (`{"<key>": {"value": <float>, "recorded_at": "<iso>"}}`), `logs/` and `artifacts/`. The caller adds the fields the ledger needs and the CLI does not write: `code_commit`, `data_version`, `config_hash`, `split_id`, seeds, the exact command, runtime and resource cost. |
| **State transition** | None of its own — it is a helper, not a stage. It is called from within `IMPLEMENT` / `TRAIN_VALIDATE`. |
| **Allowed tools** | Bash, for the three `kca run` subcommands. `local-write` for `init` and `record-metric`, `read-only` for `list`. No network. Pure filesystem. |
| **Budget** | None. Writing a record spends no ADR-0022 §6 dimension. |
| **Prerequisite approvals** | None. |
| **Idempotency** | `init` with an explicit `run_id` is safe to re-run against a fresh id and must not be pointed at an existing run to "reuse" it — that overwrites history. `record-metric` is last-write-wins per key, so a corrected metric replaces the value and its `recorded_at`; record it only after local validation finishes, never before. `list` is read-only. |
| **Failure classes** | Target run directory missing → `FAILED` naming the path, never a silent create. Malformed `--value` → `FAILED`; do not coerce. A CLI error is reported with its stderr, not retried blindly. |
| **Acceptance tests** | The directory exists with all five entries. `metrics.json` parses and every key carries a value and a `recorded_at`. The hypothesis in `meta.json` names a change and an expected effect. A failed run's directory still exists. |

## Commands

Initialize a run:

```
python tools/kca/kca.py run init --competition <slug> [--run-id <id>] \
  --hypothesis "<one-sentence hypothesis>" [--tag <tag> ...] --json
```

`run_id` defaults to UTC `YYYYMMDD_HHMMSS`.

Record a metric — after local validation, not before:

```
python tools/kca/kca.py run record-metric \
  --run-dir runs/<comp>/<run_id> --key cv_score --value 0.823 --json
```

List runs:

```
python tools/kca/kca.py run list [--competition <slug>] --json
```

## How to pick a hypothesis

One sentence that names the change and the expected effect.

- ✅ `"add target-encoded categorical features; expect +0.005 CV vs baseline"`
- ❌ `"try new features"` — nothing later can be compared against it

## How to use the output

- Keep every `kca` and shell command you ran inside `<run_dir>/logs/`, so the run is reproducible from its own record.
- Drop submission candidates into `<run_dir>/artifacts/`; `kg-submit` dispatches from there and hashes what it sends.
- Cite `run_dir` from the experiment record and from the tracking narrative. In phase 2 the same payload lands in Supabase; the path is what links the two.

## Safety

- `runs/` is gitignored and stays out of git (`CLAUDE.md` principle 7): the record is local, its *path* is what gets committed.
- Do not delete a run directory without human approval — runs are the audit trail, and irreversible deletion is an always-human item.
