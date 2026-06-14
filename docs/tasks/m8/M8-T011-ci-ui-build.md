# M8-T011: CI — UI build + live-db fork gating

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 11; extracted here for the double-layer convention.

## Goal
Extend CI so PRs run the UI build/lint/typecheck job; the live-db job no
longer runs on forks but DOES run on push to main with secrets.

## Read first
1. `.github/workflows/test.yml` (existing no-db / live-db / lint)
2. `docs/milestones/m7/final-review.md` (§ M8 follow-up #6 — confirm secret wiring +
   gate forks)
3. `ui/package.json` (lint, build, typecheck scripts)

## Scope / Files / Implementation guidance

### Step 1 — Add a `ui` job to `.github/workflows/test.yml`
```yaml
ui:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: pnpm/action-setup@v3
      with: { version: 9 }
    - uses: actions/setup-node@v4
      with: { node-version: 20, cache: pnpm, cache-dependency-path: ui/pnpm-lock.yaml }
    - run: pnpm -C ui install --frozen-lockfile
    - run: pnpm -C ui lint
    - run: pnpm -C ui typecheck
    - run: pnpm -C ui build
    - run: pnpm -C ui test -- --run
```

### Step 2 — Gate the `live-db` job
```yaml
jobs.live-db.if: |
  github.event_name == 'push' && github.ref == 'refs/heads/main'
  || (github.event_name == 'pull_request'
      && github.event.pull_request.head.repo.full_name == github.repository)
```

Add a step that asserts `secrets.SUPABASE_DB_URL` is non-empty; if it's
empty (fork PR), skip with a clear log line rather than failing.

### Step 3 — Add a `python-lint-strict` step
Runs `ruff check --select=ALL --ignore=...` using the existing ruff config
(no new rules — just confirm the existing ruleset).

## Acceptance criteria
- Workflow shape check:
  ```python
  import yaml
  d = yaml.safe_load(open('.github/workflows/test.yml'))
  jobs = d['jobs']
  assert 'ui' in jobs, jobs.keys()
  assert 'if' in jobs['live-db'], jobs['live-db']
  print('PASS workflow shape')
  ```
- Local equivalent of the UI job:
  - `pnpm -C ui install --frozen-lockfile` → 0 errors
  - `pnpm -C ui lint` → 0 issues
  - `pnpm -C ui typecheck` → 0 errors
  - `pnpm -C ui build` → 0 errors
  - `pnpm -C ui test -- --run` → all pass
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: jobs in workflow, live-db gating expression, all local mirror
steps green.

## Stop condition
Stop after 30 turns.
