# M5-T004: `kca kaggle download` checksum manifest + resume

## Milestone
M5: research and browser workflow (M4 follow-up #2).

## Goal
Promote `kca kaggle download` from a thin `subprocess` wrapper into a
verifiable download flow: write a manifest with per-file sha256 + byte size,
detect partial downloads, and support `--resume`.

## Read first
1. `tools/kca/kg.py` — current `cmd_download`
2. `docs/milestones/m4/final-review.md` — M5 follow-ups #2
3. `docs/adr/0008-artifact-storage-local-first.md`

## Changes

### `tools/kca/kg.py::cmd_download`

```
kca kaggle download --competition <slug> [--path <dir>] [--resume] [--json]
```

1. If `--path` not given, default to `data/<slug>/`.
2. If `<path>/manifest.json` exists and `--resume` is set:
   - For each entry, sha256 the existing file. Mark complete entries as skip.
   - Only re-download files missing or with mismatched hash.
3. Run the actual `kaggle competitions download` only for files still needed.
4. After download:
   - Iterate every file under `<path>`, compute sha256, byte_size.
   - Write `<path>/manifest.json`:
     ```json
     {
       "competition": "<slug>",
       "fetched_at": "<iso>",
       "files": [{"name": "...", "sha256": "...", "bytes": 12345}]
     }
     ```
5. Emit:
   ```json
   {"ok": true, "competition": "...", "path": "...", "files": N,
    "manifest": "<path>/manifest.json", "skipped": K,
    "side_effect": "LOCAL_WRITE"}
   ```

### `verify` subcommand
```
kca kaggle verify --path <dir> [--json]
   → re-hashes every file vs manifest; returns {ok, ok_count, missing, mismatched}.
```

## Acceptance criteria
- `kca kaggle download --competition X --path /tmp/x --resume --json` works
  when `/tmp/x/manifest.json` is empty/absent (full download).
- A unit test seeds `/tmp/y/manifest.json` + matching dummy files and asserts
  `--resume` exits 0 with `skipped == files`.
- `kca kaggle verify --path /tmp/y --json` returns `ok: true` on match,
  `ok: false` with `mismatched` list on tamper.

## Stop condition
Stop after 30 turns.
