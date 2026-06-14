# M7-T000: CI repair (.github/workflows audit)

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 0; extracted here for the double-layer convention.

## Goal
Make the GitHub Actions `no-db` and `lint` jobs pass on the current main branch
without requiring a live DB, Kaggle credentials, or GPU endpoints. The `live-db`
job is allowed to skip on forks; it must pass on push to main.

## Read first
1. `.github/workflows/test.yml`
2. `pyproject.toml`   (dev extras, entry points)
3. `python -m pytest tests/ -v --tb=short 2>&1 | tail -40`   (current local state)
4. `docs/milestones/README.md`   (M7 section)

## Scope / Files / Implementation guidance

Step 1 — run the test suite locally and catalogue every failure:
```
python -m pytest tests/ -v --tb=short 2>&1 | grep -E "FAILED|ERROR|error" | head -30
```

Step 2 — run ruff and capture failures:
```
ruff check . --output-format=concise 2>&1 | head -30
ruff format --check . 2>&1 | head -20
```

Step 3 — fix each failure in turn:
- If a test imports a missing module: add the module stub or fix the import.
- If a test calls a missing function: add the function or mark as xfail with a clear message.
- If ruff reports lint errors: fix them (prefer ruff --fix for style-only issues).
- If ruff reports format issues: run ruff format . (not --check).
- If a test requires a real DB and is not marked @pytest.mark.db: add the mark
  and confirm it skips when SUPABASE_DB_URL is unset.

Step 4 — validate the workflow file itself:
```
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); print('YAML ok')"
```

Step 5 — final local simulation:
```
python -m pytest tests/ -v -m "not db"   → 0 failures, 0 errors
ruff check .                              → 0 issues
ruff format --check .                    → 0 issues
```

## Acceptance criteria
- `python -m pytest tests/ -v -m "not db"` → 0 failures, 0 errors.
- `ruff check .` → 0 issues.
- `ruff format --check .` → 0 issues.
- `.github/workflows/test.yml` parses as valid YAML.
- Report: count of failures before/after, list of fixes applied, final pytest + ruff results.

## Stop condition
Stop after 30 turns.
