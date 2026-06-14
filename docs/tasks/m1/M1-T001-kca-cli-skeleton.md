# M1-T001: build `tools/kca/` CLI skeleton

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Create a minimal, local-first `kca` CLI skeleton that AI agents can call safely. The CLI should expose stable command names while keeping implementation small and reviewable.

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md`
5. `docs/tooling/legacy-tool-inventory.md`
6. `docs/tooling/kca-command-spec.md`
7. `docs/tooling/kca-side-effect-levels.md`
8. `tools/legacy/TOOLS.md`

## Design constraints
- Prefer Python stdlib `argparse` unless the repo already uses Click/Typer.
- Prefer `python -m tools.kca ...` as the first stable invocation.
- Add a console script entry point named `kca` only if project packaging already supports it cleanly.
- Keep wrappers local-first and deterministic.
- Do not change runtime competition agent architecture yet.

## Minimum command surface
Implement enough skeleton to support:

```bash
python -m tools.kca --help
python -m tools.kca version
python -m tools.kca tools list --json
python -m tools.kca tools describe <tool-name>
python -m tools.kca runs init --competition <slug> --run-id <run_id> [--root runs]
```

Command names reserved for the next task:

```bash
python -m tools.kca notebook to-ipynb <script.py> --output <notebook.ipynb>
python -m tools.kca notebook to-script <notebook.ipynb> --output <script.py>
```

## Expected files to create or update
Adapt paths to repo conventions, but prefer:

- `tools/kca/__init__.py`
- `tools/kca/__main__.py`
- `tools/kca/cli.py`
- `tools/kca/registry.py`
- `tools/kca/runs.py`
- `tests/test_kca_cli.py`
- `docs/tooling/kca-command-spec.md`

## Artifact layout created by `runs init`
For `competition=smoke-test` and `run_id=test-run-001`, create:

```text
runs/smoke-test/test-run-001/
  run.json
  README.md
  inputs/
  src/
  notebooks/
  outputs/
  submissions/
  metrics/
  logs/
  research/
  analysis/
  approvals/
```

`run.json` should include at least:

```json
{
  "competition": "smoke-test",
  "run_id": "test-run-001",
  "created_by": "kca",
  "schema_version": 1,
  "side_effect_level": "local-write"
}
```

## Non-goals
- Do not wrap legacy conversion scripts yet unless trivial.
- Do not add Supabase integration.
- Do not add Claude Agent SDK runtime.
- Do not run real Kaggle commands.
- Do not create or require Kaggle credentials.

## Acceptance criteria
- `python -m tools.kca --help` exits successfully.
- `python -m tools.kca tools list --json` exits successfully and returns valid JSON.
- `python -m tools.kca runs init --competition smoke-test --run-id test-run-001 --root <tmpdir>` creates the expected directory structure.
- `pytest` smoke tests pass, or the repo's documented test command passes.
- No remote side effects are possible from the implemented commands.

## Suggested tests
Prefer temporary directories; do not write to real competition run directories during tests.

```bash
python -m tools.kca --help
python -m tools.kca version
python -m tools.kca tools list --json
python -m pytest -q tests/test_kca_cli.py
```

## Stop condition
Stop after 80 turns if packaging or test infrastructure is unclear. Summarize exactly what was implemented, what failed, and the next smallest patch.
