# M2-T006: artifact storage strategy ADR

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Decide and document where M2 puts artifact bytes (notebook outputs, logs,
submission files, screenshots), since the `artifacts` table only stores a
`storage_path` reference.

## Read first
1. `supabase/migrations/0001_init.sql` — `artifacts` table shape
2. ADR-004 in `docs/design-decisions.md`
3. `tools/kca/run.py` — current `runs/<comp>/<run_id>/artifacts/` directory

## Required deliverable
- `docs/adr/0007-artifact-storage-local-first.md` proposing:
  - **M2:** artifacts live on the local filesystem at `runs/<comp>/<run_id>/artifacts/<filename>`. `artifacts.storage_path` is `local://<run_dir>/artifacts/<filename>` (or an absolute path under `runs/`).
  - **M3+:** when the worker runs in a sandboxed container, the worker uploads to Supabase Storage and rewrites `storage_path` to `supabase://<bucket>/<key>`. M2 does NOT do this.
  - `artifacts.content_hash` populated with SHA-256 even in M2, so M3 can detect duplicates.
- Update `tools/kca/COMMANDS.md` "Safety" section to mention artifact paths follow this ADR.

## Design constraints
- No code changes in this task — pure ADR + doc update.
- The ADR must be reversible: the `storage_path` URI scheme makes the M3 migration cosmetic.

## Non-goals
- Do not add Supabase Storage buckets in M2.
- Do not implement an upload command.
- Do not hash existing artifacts retroactively.

## Acceptance criteria
- `docs/adr/0007-artifact-storage-local-first.md` exists and is referenced from `docs/design-decisions.md`.
- The URI scheme convention (`local://` vs `supabase://`) is stated and rationalized.
- `tools/kca/COMMANDS.md` has a one-line pointer to ADR-007.

## Stop condition
Not applicable — docs-only task; should finish in one pass.
