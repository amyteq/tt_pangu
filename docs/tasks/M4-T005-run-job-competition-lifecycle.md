# M4-T005: `scripts/run_job.py` — competition repo lifecycle

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Update `scripts/run_job.py` to implement the full ADR-0009 competition-repo
worker lifecycle: load competition from DB, clone if needed, resolve experiment
branch, create worktree in competition repo, commit on success, clean up.

## Read first
1. `scripts/run_job.py` — current lifecycle (Steps 1–10)
2. `docs/adr/0009-competition-repo-strategy.md` — "Worker lifecycle with Approach B"
3. `tools/kca/db.py` — `get_competition_by_slug`, `update_competition` (M4-T002)
4. `tools/kca/workspace.py` — `cmd_init` with `--repo` (M4-T004)
5. `tools/kca/competition.py` — `cmd_clone` logic (M4-T003)

## Required changes

### New CLI flags

```
--competition-slug <slug>   # used to look up competition in DB
--branch <branch>           # experiment branch (default: auto from job payload)
--hypothesis "<text>"       # short slug for auto-generating branch name
```

### Updated worker lifecycle

Insert between Step 1 (parse args) and Step 3 (lease job):

**Step 1b — Resolve competition repo (when `--competition-slug` given)**

```python
def _resolve_competition_repo(slug: str, _db) -> tuple[str, str]:
    """Returns (local_clone_path, default_branch). Clones if needed."""
    comp = _db.get_competition_by_slug(slug)
    clone_path = comp.get("local_clone_path") or ...
    repo_url = comp.get("repo_url")
    if clone_path and not Path(clone_path).exists() and repo_url:
        subprocess.run(["git", "clone", repo_url, clone_path], check=True)
    return clone_path, comp.get("default_branch", "main")
```

**Step 1c — Resolve experiment branch**

```python
def _resolve_branch(args, job_row: dict | None) -> str | None:
    if args.branch:
        return args.branch
    payload = (job_row or {}).get("payload") or {}
    if payload.get("branch"):
        return payload["branch"]
    hypothesis = args.hypothesis or (payload.get("hypothesis") or "")
    if hypothesis:
        return "exp/" + _slugify(hypothesis)
    return None
```

**Step 4b — Use competition repo for workspace**

Replace the M3 `_workspace_init(job_id)` call with:

```python
if competition_repo_path:
    # Ensure experiment branch exists
    _ensure_branch(competition_repo_path, branch)
    # kca workspace init --job-id <id> --repo <path> --branch <branch>
    ws_path = _workspace_init_repo(job_id, competition_repo_path, branch)
else:
    # fallback: platform repo worktree (M3 behaviour)
    ws_path = _workspace_init(job_id)
```

**Step 7b — Commit on success (in competition repo)**

```python
if competition_repo_path and result.status == "done":
    _git_commit_workspace(workspace, job_id)
```

```python
def _git_commit_workspace(workspace: Path, job_id: str) -> None:
    """Stage all workspace changes and commit to the experiment branch."""
    subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=False)
    subprocess.run(
        ["git", "-C", str(workspace), "commit", "-m",
         f"job/{job_id[:8]}: agent changes"],
        check=False,
    )
```

### Dry-run compatibility

When `--dry-run` is set, skip competition clone and use tempdir workspace (unchanged).
`--competition-slug` in dry-run mode is logged but no git operations occur.

## Acceptance criteria
- `python scripts/run_job.py --prompt "test" --dry-run --json` still exits 0, status=done.
- `python scripts/run_job.py --prompt "test" --competition-slug titanic --dry-run --json`
  exits 0 (competition lookup skipped in dry-run).
- With a live DB and a registered competition, `--competition-slug <slug>` triggers
  repo clone + worktree in competition repo.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns. If `git clone` of a remote repo is flaky in tests, gate the
clone behind a `--no-clone` flag or mock subprocess in the test.
