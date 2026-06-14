# M10-T001: Data discovery + non-CSV manifest (`tpu-getting-started`)

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Discover Petals to the Metal's data layout via `kaggle competitions
files` (READ_ONLY) and commit a small `manifest.json` that documents the
dataset shape the Kaggle kernel will read at runtime. The raw TFRecord
data (~5+ GB across image-size variants) is NOT downloaded by default;
the kernel runner reads it from Kaggle-hosted GCS during the M10-T004
kernel run.

This task assumes **M10-T000 closeout is PASS**.

## Read first

1. M10-T000 closeout
2. `tools/kca/kg.py::cmd_download`, `::cmd_verify` (the existing CSV
   manifest path)
3. `docs/tasks/m9/M9-T001-data-download.md` (the CSV-shape precedent)
4. `.gitignore` (confirm `data/` is ignored)
5. `supabase/migrations/0004_m4_competition_repo.sql` (competition data /
   artifacts table layout)
6. Issue #14 (`competitions.repo_url` schema drift) — context only; do
   not block on closing it.

## Scope

1. Run `kaggle competitions files -c tpu-getting-started --csv` (or the
   JSON variant) and capture the file list. Record:
   - File names (e.g. `tfrecords-jpeg-192x192/`, `tfrecords-jpeg-224x224/`, ...).
   - Per-file sizes (Kaggle reports them).
   - The dataset's image-size variants (192x192 / 224x224 / 331x331 / 512x512).
2. Write `data/tpu-getting-started/manifest.json` with the following
   schema (mirroring M9-T001 where possible):
   ```json
   {
     "competition": "tpu-getting-started",
     "format": "kernel-input",
     "discovered_at": "<ISO-8601>",
     "files": [
       {
         "name": "tfrecords-jpeg-192x192/train/...",
         "size": 12345678,
         "sha256": null,
         "comment": "remote-only; read by kernel at runtime"
       },
       ...
     ],
     "image_size_variants": ["192x192", "224x224", "331x331", "512x512"],
     "notes": "Raw TFRecords are NOT downloaded; the kernel runner
               consumes them from Kaggle's GCS-hosted dataset."
   }
   ```
3. Force-add `manifest.json` (since `data/` is gitignored): `git add -f
   data/tpu-getting-started/manifest.json`. Raw TFRecord files (if a
   developer chooses to download a slice for inspection) must NOT be
   staged — verify with `git status` before staging.
4. Do NOT download the full dataset. If the developer needs a small
   slice for local notebook authoring (M10-T002), download only one
   tfrecord file at a time and ensure it stays under `data/tpu-getting-
   started/` (gitignored).

## Non-goals

- Do not download the full TFRecord dataset.
- Do not write sha256 hashes for files that haven't been downloaded
  (`sha256: null` in the manifest is correct for remote-only entries).
- Do not commit raw TFRecord data.
- Do not run `kca kaggle submit` / `push` / `upload`.
- Do not run the worker — that's M10-T002.
- Do not invent a new top-level `kca` subcommand. If the existing
  `cmd_download` / `cmd_verify` shape doesn't fit, write the manifest
  with a small private helper or as a one-off script under `scripts/`.

## Acceptance criteria

- `data/tpu-getting-started/manifest.json` exists in the worktree and
  is staged.
- `manifest.json` lists ≥ 1 image-size variant directory and ≥ 1 file
  entry per variant.
- `git status` shows `data/tpu-getting-started/manifest.json` as the
  only staged path under `data/tpu-getting-started/`.
- If any raw TFRecord file was downloaded for local inspection, it is
  NOT staged.
- All baseline validation still passes (pytest, ruff, pnpm where
  available).

## Permissions

- Network out to `kaggle.com` / `*.kaggle.com` is allowed (already in
  the sandbox allow-list).
- `git commit` and `git push` deferred to milestone closeout.
- No `cat`/`grep`/`head` over `.env*` or `kaggle.json`.

## Closeout format

```
M10-T001 closeout
  Files discovered: <n> entries across <k> image-size variants
  Manifest: data/tpu-getting-started/manifest.json (entries: <n>, sha256 entries: 0 — remote-only)
  Discovery method: kaggle competitions files -c tpu-getting-started (READ_ONLY)
  Staged: data/tpu-getting-started/manifest.json (raw TFRecords NOT staged)
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T002 ready to start
```

## Related issues

- #12 — M10 proposal; this closes the M10-T001 bullet on its task table.
- #14 — `competitions.repo_url` schema drift. Note any interaction
  (e.g. if `cmd_register` is extended to record `data_path` in the
  `competitions` row, that lands in #14, not here).

## Stop condition

Stop after 60 turns. If Kaggle returns a "competition rules not
accepted" error, halt and ask — do not encode a click-through. If the
file list comes back empty (Kaggle competition shape changed), halt
and ask — do not synthesize a manifest from local assumptions.
