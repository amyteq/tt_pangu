# M1-T005: final integration review for local Kaggle tooling wrapper baseline

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Review the full M1 implementation, run smoke tests, ensure docs match behavior, and prepare a clean PR summary.

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md`
5. all `docs/tasks/m1/M1-*.md`
6. `docs/tooling/*.md`
7. `tools/kca/`
8. `tools/legacy/TOOLS.md`
9. tests added in M1
10. `.claude/settings.json` and `.claude/hooks/*`

## Tasks
1. Run the documented smoke tests.
2. Verify `kca` command docs match actual CLI behavior.
3. Verify side-effect policy docs match hooks/permissions.
4. Verify no test or code path performs a real Kaggle remote write or submission.
5. Verify no secrets or credential paths are read or committed.
6. Produce a PR-ready summary.

## Required checks
Adapt command names if repo conventions differ:

```bash
git status --short
python -m tools.kca --help
python -m tools.kca tools list --json
python -m tools.kca runs init --competition smoke-test --run-id test-run-001 --root /tmp/kca-runs
python -m tools.kca notebook to-ipynb tests/fixtures/kca/hello.py --output /tmp/kca-hello.ipynb --force
python -m tools.kca notebook to-script /tmp/kca-hello.ipynb --output /tmp/kca-hello.py --force
python -m pytest -q
```

If the repo uses `uv`, prefer:

```bash
uv run pytest -q
```

## Acceptance criteria
- M1 exit criteria are satisfied:
  - Claude Code can safely call local `kca` wrappers.
  - dangerous remote operations are blocked or require approval.
  - local run artifacts are structured and testable.
- Docs include side-effect levels.
- Tests pass or blockers are documented with exact commands and error output.
- PR summary includes files changed, behavior added, tests run, risks, and follow-up tasks.

## Non-goals
- No autonomous competition agent loop.
- No Supabase integration.
- No real Kaggle submission.
- No remote kernel push/upload.

## Stop condition
Stop after 50 turns if tests cannot pass. Summarize blockers, likely root cause, and a suggested next patch.
