---
name: kg-run-experiment
description: Use to execute one planned competition experiment — implement the change, run training and local validation, capture metrics and artifacts, and compare against the baseline under the same split_id.
---

# kg-run-experiment — one execution attempt, recorded whether it works or not

Use this on entry to `IMPLEMENT`: an accepted plan from `kg-plan-experiment` exists. This skill carries `IMPLEMENT` → `TRAIN_VALIDATE` → `EVALUATE` and produces a **`Run`** — one execution attempt.

**`Experiment` is not `Run`** (ADR-0023 / issue #191). The experiment is the design; a run is one attempt at it. A retry creates a **new** run and never overwrites the failed one, because the failure history is evidence: three runs that died at the same step say something one surviving run does not. One experiment may hold several runs across folds, seeds and resource configurations.

Supersedes `kg-run` as the stage entry point. `kg-run` stays as the mechanical `kca run` wrapper this skill calls — run directories, metric records, listing.

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | The accepted `Experiment` record, the frozen validation protocol and its `split_id`, the baseline and current best under that same `split_id`, the data at its resolved mount path, and the budget envelope. |
| **Output schema** | One `Run` record per execution attempt (ADR-0023 / issue #191 defines the entity; until it merges the run directory **is** the record, and `kg-run` is how it is written): `runs/<competition>/<run_id>/` with `meta.json` (competition, run id, created at, hypothesis, tags), `config.json`, `metrics.json`, `logs/` and `artifacts/`. Every run also records `code_commit`, `data_version`, `config_hash`, `split_id`, seeds, the exact command, runtime and resource cost, and the artifact paths. The experiment's result fields (`cv_mean`, `cv_std`, and later `public_lb`) are filled from its runs. |
| **State transition** | `EXPERIMENT_PLAN` → `IMPLEMENT` → (`INDEPENDENT_AUDIT` via `kg-audit`) → `TRAIN_VALIDATE` → `EVALUATE` → `SUBMISSION_ELIGIBILITY`. The audit sits between implementation and the expensive run on purpose: a leak found after eight GPU-hours cost eight GPU-hours. |
| **Allowed tools** | Read, Write, Edit, Glob, Grep, Bash for training and validation, `kca run init` / `record-metric` via `kg-run`, `kca nb to-ipynb` via `kg-nb` where the run executes as a kernel. `local-write`, rising to `remote-write` when the run executes on Kaggle (`kaggle kernels push`). A kernel push is **not** a leaderboard submission (issue #77); submitting is `kg-submit`'s. |
| **Budget** | Spends `budget.compute.max_gpu_hours_per_cycle` and one of `budget.experiments.max_per_cycle`, against the cost the plan declared. Check before starting, not after overrunning. A `null` cap blocks: `PAUSED_BUDGET`, `resume_state: IMPLEMENT`. Consecutive failures count against `budget.failures.pause_after_consecutive_failures`. |
| **Prerequisite approvals** | The plan is accepted, and `kg-audit` has passed on the implementation where the run is expensive or the pipeline changed. Running on data beyond the competition's own is an always-human item and is not decided here. On the **Claude Code harness**, pushing a kernel spends the human's Kaggle account quota, so ask before the push — the same rule as "the harness still asks for paid-API/credential use", and it binds a Codex session identically. For the **KCA product agent** the push is governed by its competition's `autonomy` block (the file `competition.yaml:autonomy_config` names) plus ADR-0022 §5's activation conditions A1-A7; `kg-submit` states where that currently stands, and this skill does not restate it. |
| **Idempotency** | **Resumable, not repeatable.** Re-running the local half recomputes from the recorded command, seed and `split_id` — that reproducibility is what the run record is for. Re-running the *remote* half is a second push: check whether the kernel is already running or COMPLETE before pushing again, and never treat a lost response as a failed push. A retry after a real failure is a new `run_id`; the failed one stays. |
| **Failure classes** | Training crash, OOM, or an accelerator time-cap overrun → `FAILED` for that run, cause recorded, and the experiment may spawn a new run with a narrower config. Transient platform error or rate limit → `RETRY_AT` with the deadline. Kernel pushed and the response lost → `NEEDS_RECONCILIATION`: query Kaggle for the kernel's state before any second push — never a blind retry. Budget exhausted mid-cycle → `PAUSED_BUDGET`. Result uninterpretable (the split moved, a variable other than the planned one changed) → `FAILED`, `state_reason: comparison invalid`; do not report the number. |
| **Acceptance tests** | The run directory exists with `meta.json`, `config.json`, `metrics.json`, `logs/` and `artifacts/` populated. The recorded command, seed and `split_id` reproduce the recorded metric. The metric is compared against baseline and best **under the same `split_id`**. A failed run is recorded, not deleted. `competition.yaml:best` is updated only when the new score genuinely beats the old one on the same ruler. |

## Steps

1. **`kca run init`** first, via `kg-run`, with the hypothesis from the plan. The run directory exists before the work does, so a crash still leaves a record.
   ```
   python tools/kca/kca.py run init --competition <slug> --hypothesis "<one sentence>" --json
   ```
2. **Implement the one planned change.** If implementing it reveals that a second variable must move, stop and go back to `kg-plan-experiment` — that is a new plan, not a bigger run.
3. **Audit before the expensive part** (`kg-audit`), whenever the pipeline, the split or the features changed.
4. **Run**, capturing into the run directory: the exact command, config, seeds, runtime, resource cost, stdout/stderr under `logs/`, outputs under `artifacts/`. For kernels, `kg-nb` converts the authored `.py` into the `.ipynb` that is pushed, and `docs/tooling/kaggle-kernel-ops.md` §5 is the pre-push checklist — a typo that surfaces at run time costs the whole GPU run.
5. **Record the metric** when local validation finishes, not before:
   ```
   python tools/kca/kca.py run record-metric --run-dir runs/<comp>/<run_id> --key cv_score --value 0.823 --json
   ```
6. **Compare under the same `split_id`** against baseline and current best, and state plainly whether the result supports the hypothesis, contradicts it, or is inconclusive. Inconclusive is a real answer and is more useful than a rounded one.
7. **Write the experiment's result fields** from its runs, update `competition.yaml:best` only on a genuine improvement, and set `state: SUBMISSION_ELIGIBILITY`. Whether the result deserves a slot is `kg-submit`'s question.

## Safety

- `runs/` is gitignored and stays that way: weights, predictions and logs never enter git (`CLAUDE.md` principle 7). Commit the code and the paths, not the outputs.
- Do not delete a run directory without human approval — runs are the audit trail, and irreversible deletion is an always-human item.
- Resolve data mounts with a glob, never a literal path (`docs/tooling/kaggle-kernel-ops.md` §6).
