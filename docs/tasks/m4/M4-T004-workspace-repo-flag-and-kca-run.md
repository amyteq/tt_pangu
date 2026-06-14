# M4-T004: `kca workspace init --repo` flag + `kca run` subcommands

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Two related changes:

1. `kca workspace init` gains a `--repo <path>` flag so the worktree is created
   *inside* the competition repo (not the platform repo) per ADR-0009.
2. `kca run init`, `kca run record-metric`, and `kca run list` are implemented or
   confirmed working for competition-repo context.

## Read first
1. `tools/kca/workspace.py` — existing `cmd_init`, `cmd_clean`, `cmd_list`
2. `docs/adr/0009-competition-repo-strategy.md` — worker lifecycle, worktree path
3. `docs/testing/competition-test-cases.md` — `kca run init` and `record-metric` usage
4. `tools/kca/db.py` — `create_run`, `record_metric` (from M4-T002)

## 1. `kca workspace init --repo <path>` flag

### Current behaviour (M3)
```
kca workspace init --job-id <uuid>
→ git worktree add --detach <platform_root>/.workspaces/<uuid>
```

### M4 behaviour with `--repo`
```
kca workspace init --job-id <uuid> --repo <competition_clone_path> [--branch <branch>]
→ git -C <competition_clone_path> worktree add --detach jobs/<uuid>
→ returns {"ok": true, "workspace_path": "<competition_clone_path>/jobs/<uuid>"}
```

### Changes to `tools/kca/workspace.py`

- Add `--repo` argument to `p_init` parser.
- In `cmd_init`: if `args.repo` is set, use `args.repo` as the git root; worktree
  path becomes `Path(args.repo) / "jobs" / job_id`.
- If `--branch` is provided: `git -C <repo> checkout -b <branch>` before
  creating the worktree (skip if branch already exists).
- Fallback (no `--repo`): existing platform-repo `.workspaces/<job_id>` behaviour.

## 2. `kca run` subcommands

Check whether M2-T004 already implemented these. If so, confirm they work with the
new `experiment_runs` DB table from M4-T001. If not, implement them.

### `kca run init`

```
kca run init --competition <slug> --hypothesis "<text>" [--experiment-id <uuid>] [--json]
```

- Create directory `runs/<slug>/<run_id>/` relative to cwd.
- Write `meta.json`:
  ```json
  {"run_id": "...", "competition": "...", "hypothesis": "...", "started_at": "..."}
  ```
- If DB available: call `db.create_run(experiment_id=..., run_dir=...)`.
- Output: `{"ok": true, "run_dir": "runs/<slug>/<run_id>", "run_id": "..."}`.
- Side effect: `LOCAL_WRITE`.

### `kca run record-metric`

```
kca run record-metric --run-dir <path> --key <name> --value <float> [--json]
```

- Read `runs/<run_dir>/meta.json` to get `run_id`.
- Merge `{key: value}` into `runs/<run_dir>/metrics.json`.
- If DB available: call `db.record_metric(run_id, key, value)`.
- Output: `{"ok": true, "key": "...", "value": ...}`.
- Side effect: `LOCAL_WRITE`.

### `kca run list`

```
kca run list [--competition <slug>] [--limit 10] [--json]
```

- List `runs/<slug>/*/meta.json` on disk (no DB required).
- If DB available, merge DB metrics for richer output.
- Side effect: `READ_ONLY`. Exit 0 even without DB.

## Acceptance criteria
- `kca workspace init --job-id test-job-1 --repo /tmp/test-repo --json` produces
  `{"ok": true, "workspace_path": "/tmp/test-repo/jobs/test-job-1"}`.
- `kca run init --competition titanic --hypothesis "logistic regression baseline" --json`
  creates `runs/titanic/<run_id>/meta.json` and exits 0.
- `kca run record-metric --run-dir runs/titanic/<run_id> --key cv_accuracy --value 0.82 --json`
  writes to `metrics.json` and exits 0.
- `kca run list --competition titanic --json` lists the run.
- Existing workspace tests still pass (no `--repo` path unaffected).
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns. If the `--repo` worktree init fails because the competition
repo is not a valid git repo, report the error message and propose using a bare
repo fixture in tests.
