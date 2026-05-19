# M4-T003: `kca competition` subcommands — register, clone, list

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Implement `kca competition register`, `kca competition clone`, and
`kca competition list` so that the platform can create and manage competition
repos per ADR-0009.

## Read first
1. `tools/kca/kca.py` — `build_parser()` and how submodules are registered
2. `tools/kca/decisions.py` — reference pattern for a new subcommand module
3. `tools/kca/db.py` — `get_competition_by_slug`, `update_competition` (from M4-T002)
4. `docs/adr/0009-competition-repo-strategy.md` — naming convention, branch convention
5. `supabase/migrations/0001_init.sql` — `competitions` table (slug, platform, etc.)

## New file: `tools/kca/competition.py`

```python
"""kca competition: register, clone, and list competition repos."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return exit_code


def _load_db():
    import db as _db
    return _db
```

### `cmd_register`

```
kca competition register --slug <slug> --repo-url <url> [--branch main] [--json]
```

- Look up the competition by slug via `db.get_competition_by_slug(slug)`.
- Update `repo_url`, `default_branch`, `local_clone_path` (derive from slug:
  `~/competitions/kaggle-<slug>` or configurable via `--clone-path`).
- Side effect: `LOCAL_WRITE` (writes DB only, does not clone).
- Exit 0 on success; exit 1 on error.

### `cmd_clone`

```
kca competition clone --slug <slug> [--path <dir>] [--json]
```

- Fetch competition from DB; get `repo_url` and `local_clone_path`.
- If `local_clone_path` already exists: report `{"ok": true, "cloned": false, "path": ...}` (skip).
- Otherwise: `git clone <repo_url> <local_clone_path>` (subprocess).
- Side effect: `LOCAL_WRITE` (creates local files).
- On clone success: confirm default `.gitignore` for `data/`, `runs/`, `artifacts/`.
- Exit 0 on success; exit 1 on git error.

### `cmd_list`

```
kca competition list [--json]
```

- Call `db.list_competitions()` (add this simple SELECT to db.py: all rows, newest first).
- Print as a table (or JSON). Exit 0 even if DB unavailable (returns empty list).
- Side effect: `READ_ONLY`.

### `cmd_info`

```
kca competition info --slug <slug> [--json]
```

- Print full competition row including `repo_url`, `local_clone_path`, `default_branch`.
- Side effect: `READ_ONLY`.

## `kca.py` registration

In `build_parser()`, add:

```python
import competition as competition_mod
competition_mod.add_parsers(sub)
```

## Acceptance criteria
- `kca competition register --slug titanic --repo-url https://github.com/user/kaggle-titanic --json` → `{"ok": true, "slug": "titanic", ...}`.
- `kca competition list --json` → `{"ok": true, "competitions": [...]}` (empty list OK without DB).
- `kca competition clone --slug titanic --json` prints `{"ok": true, "cloned": true/false, "path": "..."}`.
- `kca competition info --slug titanic --json` shows `repo_url` and `local_clone_path`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns. If `git clone` hangs in CI (no network), the test for
`cmd_clone` should mock subprocess or use a local bare repo fixture.
