# M5-T007: CI GitHub Actions workflow

## Milestone
M5: research and browser workflow (M4 follow-up #3).

## Goal
Wire `.github/workflows/test.yml` so every PR runs the no-DB and (optionally)
live-DB test suites that we currently only run locally.

## Read first
1. `Makefile` — `supabase-up / supabase-reset / test*` targets
2. `tests/test_kca_smoke.py`, `tests/test_m4_smoke.py` — no-DB tests
3. `tests/test_kca_db_smoke.py` — `@requires_db`
4. `docs/tooling/env-configuration.md`

## Workflow design

### Job 1 — `no-db`
- Trigger: pull_request, push to `main`.
- Steps:
  - `actions/checkout@v4`
  - `actions/setup-python@v5` (3.12)
  - `pip install -e .[dev]`
  - `python -m pytest tests/ -v -m "not requires_db"` (or rely on
    `@requires_db` skip behaviour when no env is set).

### Job 2 — `live-db` (optional)
- Trigger: `if: github.event.pull_request.head.repo.full_name == github.repository`
  (no secrets in fork PRs).
- Service container: `postgres:15` on port `5432` with password `postgres`.
- Apply migrations 0001..0005 via `psql`.
- Run `python -m pytest tests/ -v` with `SUPABASE_DB_URL` + `KCA_DB_TARGET=local`.

### Job 3 — `lint`
- `ruff check .` and `ruff format --check .`.

## Acceptance criteria
- `.github/workflows/test.yml` present.
- `act -W .github/workflows/test.yml -j no-db` (or remote PR) reaches a
  passing `pytest`.
- The workflow does not call the real Anthropic / Kaggle APIs.
- A failing test surfaces as a failed check.

## Stop condition
Stop after 25 turns. Document any unavoidable network limitations in
`docs/tooling/ci-notes.md`.
