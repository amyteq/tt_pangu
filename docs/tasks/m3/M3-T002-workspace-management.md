# M3-T002: Workspace management — `kca workspace` commands

## Milestone
M3: Python-first competition worker v0.

## Goal
Provide isolated per-job workspaces using `git worktree`. Each worker job gets its own
checkout so concurrent jobs (and debugging after failure) never share file state.

> **M3 interim note (ADR-0009):** In M3, worktrees are created inside the *platform repo*
> at `.workspaces/<job_id>/`. This is a deliberate simplification to get the worker
> skeleton working without introducing competition repo management yet.
> In M4, `kca workspace init` gains a `--repo <competition-clone-path>` flag and
> creates the worktree inside the competition repo instead. The command interface
> is designed to be backward-compatible with that change.

## Read first
1. `tools/kca/kca.py` — subcommand registration pattern
2. `tools/kca/_util.py` — `emit_json`, `run_cmd`, `SideEffect`
3. `tools/kca/db.py` — `update_job` (for recording workspace_path)
4. `docs/milestones/README.md` — M3 "Worker creates isolated workspace/worktree per job"

## Commands to implement

### `kca workspace init`
```
kca workspace init --job-id <id> [--branch <branch>] [--root .workspaces] [--json]
```

Side effect: `LOCAL_WRITE`

Logic:
1. `workspace_dir = Path(root) / job_id`
2. If `workspace_dir` already exists → `{"ok": false, "error": "workspace already exists"}`; exit 1.
3. Resolve `branch`: if not given, use `git rev-parse --abbrev-ref HEAD`.
4. Run `git worktree add <workspace_dir> <branch>`.
5. Create `<workspace_dir>/runs/` directory.
6. Best-effort DB update: `update_job(job_id, workspace_path=str(workspace_dir))`
   (skip silently if `SUPABASE_DB_URL` is unset — workspace init must work offline).
7. Emit `{"ok": true, "workspace_path": "...", "job_id": "...", "branch": "..."}`.

### `kca workspace clean`
```
kca workspace clean --job-id <id> [--root .workspaces] [--force] [--json]
```

Side effect: `LOCAL_WRITE`

Logic:
1. `workspace_dir = Path(root) / job_id`
2. If not exists → `{"ok": false, "error": "workspace not found"}`; exit 1.
3. Run `git worktree remove <workspace_dir> [--force]`.
4. Best-effort DB update: `update_job(job_id, finished_at=now())`.
5. Emit `{"ok": true, "removed": str(workspace_dir)}`.

### `kca workspace list`
```
kca workspace list [--root .workspaces] [--json]
```

Side effect: `READ_ONLY`

Logic:
1. Run `git worktree list --porcelain`, parse output.
2. Filter to paths under `root` (`.workspaces/` by default).
3. Emit `{"ok": true, "workspaces": [{path, branch, commit, job_id}, ...]}`.
   `job_id` is the directory name (last component of path).

## Module layout
- Create `tools/kca/workspace.py`.
- Register as subcommand group `workspace` in `tools/kca/kca.py`.
- Add entries to `tools/kca/COMMANDS.md`.

## .gitignore
Add `.workspaces/` to the root `.gitignore` if not already present.

## Design constraints
- `workspace init/clean` must work without a DB connection (offline mode).
- `git worktree add` fails informatively if the branch doesn't exist.
- Path must be validated: `workspace_dir` must stay under the project root.
- `git worktree remove` with no `--force` will fail if the workspace has uncommitted changes — surface the error clearly.

## Acceptance criteria
```bash
TEST_JOB="m3t002-$(date +%s)"

python tools/kca/kca.py workspace init --job-id $TEST_JOB --json
# → exit 0; workspace_path in JSON

ls .workspaces/$TEST_JOB/runs/
# → directory exists

python tools/kca/kca.py workspace list --json
# → exit 0; lists $TEST_JOB entry

python tools/kca/kca.py workspace clean --job-id $TEST_JOB --json
# → exit 0

git worktree list | grep $TEST_JOB
# → no output (worktree removed)

grep ".workspaces" .gitignore
# → present
```

## Stop condition
Stop after 20 turns. This is mechanical wiring; any `git worktree` failure should be
reported verbatim.
