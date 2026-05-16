# Testing and Smoke Checks

## Current status (M0 blocker)

No automated test suite exists yet.

- No `pyproject.toml` or `uv.lock` — Python project not initialized.
- `pytest` is not installed in the current environment.
- No `package.json` — Node/TypeScript project not initialized.
- No test files in `src/`, `tests/`, or `scripts/`.

Running test commands now will fail. This is expected and documented as a blocker for M1.

```bash
uv run pytest -q   # fails: no pyproject.toml
npm test           # fails: no package.json
```

## Available runtimes (as of 2026-05-16)

| Tool | Version |
|---|---|
| Python | 3.12.12 |
| uv | 0.11.14 |
| node | 24.14.0 |
| npm | 11.11.0 |
| pytest | not installed |
| pnpm | not installed |

## Planned test commands (M1+)

Once a Python project is initialized with `pyproject.toml`:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Once a Node/TypeScript project is initialized:

```bash
npm test
npm run lint
```

## Hook smoke check (available now)

The guard and audit hooks can be manually verified without a test suite:

```bash
python .claude/hooks/guard_tool.py
python .claude/hooks/audit_event.py
```

These hooks run automatically on every Claude Code tool call via `.claude/settings.json`. Audit output is written to `.agent/audit/tool-events.jsonl`.

## Tool-level smoke tests (M1 target)

After `tools/kca/` is created:

1. Convert a Python script to notebook and back — verify round-trip correctness.
2. Run a minimal script via the `kca` wrapper — verify exit code and artifact creation in `runs/`.
3. Verify that `kca submit` is blocked by the approval hook without explicit human confirmation.

## Competition-level regression tests (M4+)

See `docs/testing/competition-test-cases.md` for the full plan. Summary:

- **Level 0** — tool smoke tests (M1 target)
- **Level 1** — classic Kaggle tabular (Titanic, House Prices) — M4 target
- **Level 2** — notebook/kernel workflow dry run — M4 target
- **Level 3** — reasoning-heavy competition — M5+ target
- **Level 4** — authorized CTF sandbox — M8 target

A test case is considered passed only when the agent produces a run directory, recorded metrics or an explicit reason they are unavailable, an analysis note, a proposed next action, and no unapproved external side effects.
