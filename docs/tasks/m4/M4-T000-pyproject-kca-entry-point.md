# M4-T000: pyproject.toml — pip-installable kca entry point

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Make `kca` pip-installable from the platform repo so that competition repo
workers can call `kca` without PYTHONPATH hacks.  This is the ADR-0009
prerequisite for all M4 competition-repo work.

## Read first
1. `pyproject.toml` — existing `[tool.pytest.ini_options]` section
2. `tools/kca/kca.py` — current CLI entry point (`main()` function)
3. `docs/adr/0009-competition-repo-strategy.md` — "How platform tools reach the competition repo"

## Changes required

### `pyproject.toml`

Add a proper package declaration and console script before the existing
`[tool.pytest.ini_options]` block:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "tt-pangu"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "psycopg[binary]>=3.1",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
llm = ["litellm>=1.40"]
dev = ["pytest>=8", "ruff>=0.4"]

[project.scripts]
kca = "tools.kca.kca:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["tools*", "src*"]

[tool.setuptools.package-dir]
"" = "."
```

### `tools/kca/kca.py`

Confirm `main()` is the module-level entry point (no `if __name__ == "__main__":` guard
that would break the script).  If needed, expose it:

```python
def main():
    ...

if __name__ == "__main__":
    sys.exit(main())
```

## Verification

```bash
pip install -e .
kca --help               # shows kca subcommands
kca nb to-py --help      # nb subcommand still works
python -m pytest tests/ -v   # existing suite still passes
```

## Acceptance criteria
- `pip install -e .` exits 0 with no errors.
- `kca --help` is available on PATH after install.
- `python -m pytest tests/ -v` — 0 failures.
- `pyproject.toml` still includes `[tool.pytest.ini_options]` with `pythonpath = ["."]`.

## Stop condition
Stop after 20 turns. This task is purely configuration — if setuptools raises an
unexpected error, document it and propose a fix rather than trying multiple
alternative build backends.
