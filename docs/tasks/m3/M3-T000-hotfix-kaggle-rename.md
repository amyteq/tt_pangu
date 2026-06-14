# M3-T000: Hotfix — rename `tools/kca/kaggle.py` → `tools/kca/kg.py`

## Milestone
M3 prerequisite (identified in `docs/milestones/m2/final-review.md` risks section).

## Goal
Eliminate the risk that `tools/kca/kaggle.py` shadows the PyPI `kaggle` package when
both are on `sys.path`. This is a pure rename with no behaviour change.

## Read first
1. `docs/milestones/m2/final-review.md` — Risks section, bullet about `tools/kca/kaggle.py`
2. `tools/kca/kca.py` — find the `import kaggle` or `from . import kaggle` lines
3. `tools/kca/COMMANDS.md` — module name column

## Scope
- Rename `tools/kca/kaggle.py` → `tools/kca/kg.py`.
- Update all internal references within `tools/kca/`.
- Update any test files that import from `tools.kca.kaggle`.
- No logic changes.

## Files to touch
| File | Change |
|---|---|
| `tools/kca/kaggle.py` | rename → `tools/kca/kg.py` |
| `tools/kca/kca.py` | `from . import kaggle` → `from . import kg`; `kaggle.subparser(...)` → `kg.subparser(...)` |
| `tools/kca/COMMANDS.md` | update module name in table |
| `tests/test_kca_smoke.py` | `from tools.kca import kaggle` → `from tools.kca import kg` if present |
| `tests/test_kca_db_smoke.py` | same |

## Acceptance criteria
- `python tools/kca/kca.py kaggle --help` exits 0.
- `python -m pytest tests/test_kca_smoke.py -v -k "kaggle or submit"` all pass.
- `grep -r "^import kaggle\|^from kaggle\|from \. import kaggle" tools/kca/` → empty.
- No file in `tools/kca/` has `import tools.kca.kaggle` or `from tools.kca import kaggle`.

## Stop condition
Stop after 10 turns. This is a trivial rename; any blocker should be reported immediately.

## Non-goals
- No logic changes to the kaggle gate.
- No new commands.
