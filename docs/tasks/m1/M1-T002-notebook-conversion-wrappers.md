# M1-T002: wrap legacy Python/IPython notebook conversion tools

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Register 1-2 existing helper scripts from `tools/legacy/` behind stable `kca notebook` commands, prioritizing Python/IPython notebook conversion.

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/tooling/legacy-tool-inventory.md`
5. `docs/tooling/kca-command-spec.md`
6. `tools/legacy/TOOLS.md`
7. selected legacy conversion scripts
8. `tools/kca/` implementation from M1-T001

## Stable commands
Implement or finalize:

```bash
python -m tools.kca notebook to-ipynb <script.py> --output <notebook.ipynb>
python -m tools.kca notebook to-script <notebook.ipynb> --output <script.py>
```

Optional flags if supported safely:

```bash
--force       # overwrite output path
--dry-run     # validate inputs and print planned action without writing
--metadata    # include/update notebook metadata only if legacy tool already supports it
```

## Implementation guidance
- Prefer calling existing legacy scripts rather than rewriting their logic.
- If a legacy script has a stable function API, import it.
- If a legacy script only has CLI behavior, wrap it via `subprocess.run` with explicit argument lists, not shell strings.
- Validate paths and create parent directories as needed.
- Never call remote Kaggle APIs from notebook conversion commands.
- If a legacy conversion script has hidden remote behavior, do not wrap it; document the blocker.

## Expected files to create or update
Adapt to repo conventions, but likely:

- `tools/kca/notebook.py`
- `tools/kca/registry.py`
- `tests/test_kca_notebook_conversion.py`
- `tests/fixtures/notebooks/` or `tests/fixtures/kca/`
- `docs/tooling/kca-command-spec.md`
- `docs/tooling/legacy-tool-inventory.md`

## Test fixtures
Create tiny deterministic fixtures only:

```text
tests/fixtures/kca/hello.py
tests/fixtures/kca/hello.ipynb
```

The fixture should not import Kaggle, pandas, torch, or heavy dependencies.

## Acceptance criteria
- `to-ipynb` converts a tiny Python script to a notebook file in a temp directory.
- `to-script` converts a tiny notebook to a Python script in a temp directory.
- Commands fail with a clear error for missing inputs.
- Commands do not read credentials or invoke Kaggle.
- Tests pass.

## Suggested tests

```bash
python -m tools.kca notebook to-ipynb tests/fixtures/kca/hello.py --output /tmp/kca-hello.ipynb --force
python -m tools.kca notebook to-script /tmp/kca-hello.ipynb --output /tmp/kca-hello.py --force
python -m pytest -q tests/test_kca_notebook_conversion.py
```

## Non-goals
- No notebook execution runner yet.
- No Kaggle kernel push yet.
- No real competition submission.
- No Supabase integration.

## Stop condition
Stop after 80 turns if the existing legacy scripts are incompatible with safe wrappers. Document the incompatibility and propose the smallest adapter patch.
