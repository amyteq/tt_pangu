# M4-T007: Wire real kaggle CLI into `kca kaggle` commands

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Replace the stub implementations in `tools/kca/kg.py` with real calls to the
`kaggle` CLI for `submit`, `push` (kernel), `download` (data), and `watch`.
All remote operations still go through the `_check_approval_gate` from M4-T006.

## Read first
1. `tools/kca/kg.py` — current stubs and `_gate()` function
2. `docs/adr/0006-configurable-approval-gates.md` — which operations are gated
3. `docs/tooling/env-configuration.md` — `KAGGLE_USERNAME`, `KAGGLE_KEY`
4. `docs/testing/competition-test-cases.md` — `kca kaggle push --dry-run` usage in TC-3

## Changes to `tools/kca/kg.py`

### `cmd_submit`

```
kca kaggle submit --competition <slug> --file <path> [--message <msg>] [--json]
```

- Gate: `_check_approval_gate("kaggle_submit", policy)`.
- Construct: `kaggle competitions submit -c <slug> -f <path> -m <message>`.
- Capture stdout/stderr. Parse success vs error.
- Output: `{"ok": true, "competition": "...", "file": "...", "side_effect": "SUBMISSION"}`.
- Requires `KAGGLE_USERNAME` and `KAGGLE_KEY` to be set (check and emit clear error if missing).

### `cmd_push` (kernel push)

```
kca kaggle push --kernel-dir <path> [--dry-run] [--json]
```

- Gate: `_check_approval_gate("kernel_push", policy)`.
- If `--dry-run`: validate `kernel-metadata.json` exists; output
  `{"ok": true, "dry_run": true, "kernel_dir": "..."}`. No subprocess.
- Otherwise: `kaggle kernels push -p <kernel_dir>`.
- Output: `{"ok": true, "kernel_dir": "...", "side_effect": "REMOTE_WRITE"}`.

### `cmd_download`

```
kca kaggle download --competition <slug> [--path <dir>] [--json]
```

- Gate: `_check_approval_gate("dataset_upload", policy)` — not gated by default.
- `kaggle competitions download -c <slug> -p <path>`.
- Output: `{"ok": true, "competition": "...", "path": "..."}`.
- Side effect: `LOCAL_WRITE` (downloads to local dir).

### `cmd_watch`

```
kca kaggle watch --kernel <owner/slug> [--poll-seconds 30] [--json]
```

- No gate (READ_ONLY polling).
- Loop: `kaggle kernels status <owner/slug>` every `poll_seconds`.
- Exit when status is `"complete"` or `"error"`.
- Output final: `{"ok": true, "status": "complete", "kernel": "..."}`.

## Testing strategy

- Unit test `--dry-run` path (no subprocess) in `tests/test_kaggle_dry_run.py`.
- Mock `subprocess.run` for live-command tests to avoid real API calls.
- Integration test (`KAGGLE_USERNAME` + `KAGGLE_KEY` required): skip if not set.

## Acceptance criteria
- `kca kaggle push --kernel-dir tests/fixtures/sample_kernel --dry-run --json`
  → `{"ok": true, "dry_run": true, ...}` without API credentials.
- `kca kaggle submit ...` without `KAGGLE_USERNAME` set → `{"ok": false, "error": "KAGGLE_USERNAME not set"}`.
- Policy gate: `_check_approval_gate("kaggle_submit", {"approval_gates": {"kaggle_submit": true}})` raises `ApprovalRequired`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns. Do not make real Kaggle API calls during implementation.
If the kaggle CLI is not installed in the dev environment, stub the subprocess
call and add a note in `docs/tooling/env-configuration.md`.
