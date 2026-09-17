---
name: kg-nb
description: Convert between Jupyter notebooks and percent-format Python scripts via the kca CLI. Use when the user asks to turn .ipynb into editable .py, or rebuild .ipynb from .py.
---

# kg-nb — notebook ↔ percent-format conversion

Use this skill when the user wants to:

- Turn a `.ipynb` into a flat percent-format `.py` for editing or diff review.
- Rebuild a `.ipynb` from a `.py` percent-format script for execution or submission.

`.py` is the editable truth source; `.ipynb` is an execution/submission artifact. Never edit a `.ipynb` directly when a `.py` exists.

A mechanical wrapper, not a loop stage: `kg-run-experiment` and `kg-submit` call it when a kernel authored as `.py` has to be pushed as `.ipynb` (`competitions/nvidia-nemotron/kernels/*.py`, `kca-nemo.yaml:code_file`).

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | One source file — a `.ipynb` to flatten, or a percent-format `.py` to rebuild — and an optional output path. |
| **Output schema** | The converted file at `dst`, plus one JSON object on stdout: `ok`, `side_effect`, `src`, `dst`, `written_cells` / `code_cells` / `markdown_cells`, `changed`, and `error` / `stderr` on failure. |
| **State transition** | None of its own. Called from within `IMPLEMENT` or `PRE_SUBMIT_GATE`. |
| **Allowed tools** | Bash, for the two `kca nb` subcommands. `local-write`. No network, no remote services. |
| **Budget** | None. |
| **Prerequisite approvals** | None. It writes a local file; pushing or submitting the result is `kg-submit`'s, under the rules that skill states. |
| **Idempotency** | Safe to re-run: the same source produces the same destination, and `changed` reports whether anything moved. Round-tripping `.py` → `.ipynb` → `.py` is not guaranteed to be byte-identical, so keep the `.py` as the source of truth rather than regenerating it from a pushed notebook. |
| **Failure classes** | `ok: false` is a stop, not a retry — read `error` and `stderr`. `ModuleNotFoundError: percent_nb` means `tools/legacy/percent_nb.py` is missing; report it, do not patch it. A `# %%` marker mismatch is a source-format error: quote the line range and ask. |
| **Acceptance tests** | `ok: true`, `dst` exists, and the cell counts match the source's structure. The `.py` remains the edited artifact and the `.ipynb` is regenerated from it. |

## Commands

Convert `.ipynb` → `.py`:

```
python tools/kca/kca.py nb to-py <SRC.ipynb> [--output DST.py] [--no-keep-markdown] --json
```

Convert `.py` → `.ipynb`:

```
python tools/kca/kca.py nb to-ipynb <SRC.py> [--output DST.ipynb] [--keep-markdown] --json
```

Both commands emit one JSON object on stdout with these fields:

- `ok`: `true`/`false`
- `side_effect`: `"LOCAL_WRITE"`
- `src`, `dst`: absolute paths
- `written_cells`, `code_cells`, `markdown_cells`: cell counts (only on success)
- `changed`: whether the destination changed
- `error`, `stderr`: failure details (only on failure)

## How to interpret output

- `ok: true` → write succeeded; report `dst` and cell counts to the user.
- `ok: false` → do **not** retry blindly. Inspect `error` and `stderr`. Common causes:
  - `ModuleNotFoundError: percent_nb` → `tools/legacy/percent_nb.py` missing; do not patch.
  - format errors (mismatched `# %%` markers) → quote the line range and ask the human.

## Safety

- Side effect: `LOCAL_WRITE`. No network. No remote services.
- Never invoke `nb to-ipynb` over an unreviewed `.py` if the user hasn't asked for it.
- Do not commit generated `.ipynb` files unless the user asks; treat them as artifacts.

## Out of scope

- Test-notebook construction → use the legacy `nb2test.py` directly, or a future `kca nb to-test`.
- Markdown export → use `python tools/legacy/nb2md.py` directly.
