# M4-T002: DB layer — competition, experiment, run, submission functions

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Extend `tools/kca/db.py` with the DB functions needed by M4 commands:
`kca competition register/clone`, `kca run init/record-metric`, and the
competition-aware `scripts/run_job.py` lifecycle.

## Read first
1. `tools/kca/db.py` — existing `__all__`, `_with_conn`, pattern for parameterised SQL
2. `supabase/migrations/0004_m4_competition_repo.sql` — schema from M4-T001
3. `docs/adr/0005-job-taxonomy.md` — definitions of competition/experiment/run/submission
4. `docs/adr/0009-competition-repo-strategy.md` — worker lifecycle

## Functions to add

Add to `__all__` and implement each. Follow the same patterns as existing db.py:
- No async. Parameterised SQL only (no f-string interpolation of user data).
- Lazy connection via `_with_conn`.
- Importable without a live DB.

### Competition functions

```python
def get_competition_by_slug(slug: str) -> dict:
    """Fetch one competitions row by slug. Raises KeyError if not found."""

def update_competition(
    competition_id: str,
    *,
    repo_url: str | None = None,
    default_branch: str | None = None,
    local_clone_path: str | None = None,
    competition_policy: dict | None = None,
) -> None:
    """Partial update of competitions columns. Only non-None kwargs are set."""
```

### Experiment functions

```python
def create_experiment(
    competition_id: str,
    hypothesis: str,
    job_id: str | None = None,
    branch: str | None = None,
    config: dict | None = None,
) -> str:
    """Insert a new experiments row. Returns experiment_id (uuid str)."""

def get_experiment(experiment_id: str) -> dict:
    """Fetch one experiments row. Raises KeyError if not found."""

def list_experiments(competition_id: str, status: str | None = None) -> list[dict]:
    """List experiments for a competition, newest first."""
```

### Run functions

```python
def create_run(
    experiment_id: str,
    job_id: str | None = None,
    run_dir: str | None = None,
    command: str | None = None,
) -> str:
    """Insert a new experiment_runs row with status='running'. Returns run_id."""

def update_run(
    run_id: str,
    *,
    status: str | None = None,
    metrics: dict | None = None,
    artifact_paths: list | None = None,
    analysis: str | None = None,
    finished_at=None,
) -> None:
    """Partial update of experiment_runs. Only non-None kwargs are set."""

def record_metric(run_id: str, key: str, value: float) -> None:
    """Merge {key: value} into experiment_runs.metrics jsonb for run_id."""
    # Implementation: UPDATE experiment_runs
    #   SET metrics = metrics || jsonb_build_object($1, $2)
    #   WHERE id = $3

def list_runs(
    experiment_id: str | None = None,
    competition_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List experiment_runs. Filter by experiment or competition, newest first."""
```

### Submission functions

```python
def create_submission(
    competition_id: str,
    file_path: str,
    run_id: str | None = None,
    job_id: str | None = None,
    cv_score: float | None = None,
    note: str | None = None,
) -> str:
    """Insert a prepared submissions row. Returns submission_id."""

def update_submission(
    submission_id: str,
    *,
    public_lb_score: float | None = None,
    status: str | None = None,
    submitted_at=None,
) -> None:
    """Update submission after Kaggle response."""
```

## Design constraints
- `record_metric` must use a single parameterised SQL UPDATE with `jsonb_build_object`
  — do not read-modify-write in Python (race condition risk).
- All functions follow the same error-surface pattern as existing db.py.
- `KCA_DB_TARGET=remote` without `KCA_ALLOW_REMOTE=1` still raises `RemoteOperationBlocked`
  (unchanged from existing behaviour).

## Acceptance criteria
- `python -c "from tools.kca import db; print([f for f in dir(db) if 'competition' in f or 'experiment' in f or 'run' in f or 'submission' in f])"` lists all new symbols.
- Run against a live DB: `create_experiment → create_run → record_metric('cv_score', 0.83) → get_experiment(id)` produces consistent rows.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns. If the jsonb merge UPDATE for `record_metric` is rejected by
Postgres, fall back to a read-modify-write with an explicit transaction and document
the compromise.
