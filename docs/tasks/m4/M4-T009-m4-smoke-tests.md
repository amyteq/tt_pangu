# M4-T009: M4 smoke tests

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Add `tests/test_m4_smoke.py` covering all new M4 commands and the competition
repo lifecycle. All tests must pass without a live DB, Kaggle credentials, or
real LLM API calls.

## Read first
1. `tests/test_worker_smoke.py` — M3 smoke test style (MockLiteLLMClient, tempdir)
2. `tools/kca/competition.py` — M4-T003
3. `tools/kca/workspace.py` — `cmd_init` with `--repo` flag (M4-T004)
4. `tools/kca/kg.py` — dry-run and gate checks (M4-T006, M4-T007)
5. `scripts/run_job.py` — dry-run competition-slug path (M4-T005)

## Test cases

### Competition commands (no DB required)

```python
def test_competition_list_no_db():
    """kca competition list exits 0 with empty list when DB unavailable."""

def test_competition_register_missing_slug(tmp_path):
    """kca competition register without --slug exits non-zero."""
```

### Workspace --repo flag

```python
def test_workspace_init_with_repo(tmp_path):
    """kca workspace init --repo <bare git repo> creates worktree at jobs/<job_id>."""
    # Setup: bare git repo in tmp_path
    subprocess.run(["git", "init", str(tmp_path / "repo")], check=True)
    subprocess.run(["git", "-C", str(tmp_path / "repo"), "commit",
                    "--allow-empty", "-m", "init"], check=True)
    result = subprocess.run(
        ["python", "tools/kca/kca.py", "workspace", "init",
         "--job-id", "test-m4-1", "--repo", str(tmp_path / "repo"), "--json"],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    assert data["ok"]
    assert Path(data["workspace_path"]).exists()
```

### kca run commands

```python
def test_run_init_creates_meta(tmp_path, monkeypatch):
    """kca run init creates runs/<slug>/<run_id>/meta.json."""
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        ["python", str(REPO_ROOT / "tools/kca/kca.py"), "run", "init",
         "--competition", "titanic", "--hypothesis", "baseline", "--json"],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    assert data["ok"]
    meta = json.loads((tmp_path / data["run_dir"] / "meta.json").read_text())
    assert meta["competition"] == "titanic"

def test_run_record_metric(tmp_path, monkeypatch):
    """kca run record-metric writes key/value to metrics.json."""
    # First init a run, then record a metric.

def test_run_list_no_db(tmp_path, monkeypatch):
    """kca run list exits 0 with empty list when no runs/ dir exists."""
```

### Kaggle gate checks

```python
def test_kaggle_push_dry_run(tmp_path):
    """kca kaggle push --dry-run exits 0 without credentials."""
    # Create minimal kernel-metadata.json
    (tmp_path / "kernel-metadata.json").write_text('{"id": "user/test", "title": "test"}')
    result = subprocess.run(
        ["python", ..., "kca.py", "kaggle", "push",
         "--kernel-dir", str(tmp_path), "--dry-run", "--json"],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    assert data["ok"]
    assert data["dry_run"]

def test_kaggle_submit_no_credentials():
    """kca kaggle submit without KAGGLE_USERNAME exits non-zero with clear error."""

def test_approval_gate_blocks_submit():
    """kaggle_submit gate=True raises ApprovalRequired."""
    from src.worker._types import JobPolicy
    policy = JobPolicy(approval_gates={"kaggle_submit": True})
    with pytest.raises(Exception, match="ApprovalRequired|approval"):
        ...  # call _check_approval_gate("kaggle_submit", vars(policy))
```

### run_job.py with competition-slug (dry-run)

```python
def test_run_job_competition_slug_dry_run(tmp_path):
    """run_job.py --dry-run --competition-slug titanic exits 0."""
    result = subprocess.run(
        ["python", "scripts/run_job.py",
         "--prompt", "test", "--competition-slug", "titanic",
         "--max-turns", "2", "--dry-run", "--json"],
        capture_output=True, text=True,
        env={**os.environ, "SUPABASE_DB_URL": ""},  # no DB
    )
    data = json.loads(result.stdout)
    assert data["status"] == "done"
```

## Target: all tests pass, no API key, no DB

```
python -m pytest tests/test_m4_smoke.py -v
```

Expected: 8–12 tests, all pass in < 10 seconds.

## Acceptance criteria
- All tests in `test_m4_smoke.py` pass.
- No test requires `ANTHROPIC_API_KEY`, `SUPABASE_DB_URL`, or `KAGGLE_KEY`.
- `python -m pytest tests/ -v` — 0 failures (M3 suite still passes).

## Stop condition
Stop after 40 turns. If a test depends on a git worktree operation that hangs,
replace with a subprocess mock and note the limitation.
