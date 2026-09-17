# ADR-0008 — Artifact storage is local-first in M2, with a URI scheme that survives the move to Supabase Storage in M3

Status: accepted (for M2) Date: 2026-05-18

## Context

The `artifacts` table in `supabase/migrations/0001_init.sql` stores a `storage_path text` per artifact, plus optional `content_hash` and `byte_size`. It does not say where the bytes actually live. M2 (Supabase / control-plane foundation) needs to commit to a place — but the long-term answer is the Supabase Storage bucket attached to a per-job worker container, which M2 does not have.

Three options were considered:

1. **Local filesystem under `runs/<comp>/<run_id>/artifacts/`**, `storage_path` stores a relative path. M2 work; minimal moving parts.
2. **Supabase Storage from day one**, even though M2 has no worker that produces artifacts in a meaningful way. `kca` would have to authenticate, upload, hash, and rewrite paths.
3. **S3 / generic object store** via a separate provider — sidesteps Supabase choice but adds a third dependency.

## Decision

Pick option 1 for M2: artifacts are local files under the existing `runs/<comp>/<run_id>/artifacts/` directory (which `kca run init` already creates). Store the location in `artifacts.storage_path` using a URI scheme so M3 can swap the backend without changing readers.

### URI scheme

| Scheme            | M2 meaning                                                        |
|-------------------|-------------------------------------------------------------------|
| `local://<path>`  | Path is relative to repo root (e.g. `local://runs/titanic/20260518_103000/artifacts/submission.csv`). |
| `supabase://<bucket>/<key>` | Reserved for M3+. Not used in M2. Readers should accept the URI scheme but raise NotImplemented until M3.  |
| `s3://<bucket>/<key>` | Reserved if Supabase Storage proves inadequate. Not used in M2.    |

### Content hashing

`artifacts.content_hash` is populated with a **SHA-256 hex digest** of the file contents. The hash is computed at write time, not lazily, so duplicate detection in M3 can rely on it without re-reading files.

### When `artifacts` rows are written

Not in M2-T004's `kca run` path — `kca run init` creates the `runs/` directory but does not insert `artifacts` rows. Future M3 work (worker producing outputs) inserts one `artifacts` row per produced file and references it from `experiment_runs.artifacts jsonb` or `submissions.submission_file_artifact_id`.

## Consequences

- **Good:** zero new infrastructure for M2. The existing filesystem layout is already in use; M2 just promises a URI scheme.
- **Good:** the `local://` → `supabase://` migration is a 1:1 rewrite of the `storage_path` column when a worker uploads its first file. No schema change required.
- **Trade-off:** until M3 uploads run, artifacts are only accessible from the machine that produced them. Sharing across machines requires either pre-uploading manually, or waiting for M3.
- **Trade-off:** RLS on the `artifacts` table doesn't gate file access in M2 (the files live outside Postgres). Policy enforcement has to be in code paths that resolve `storage_path`. Acceptable for M2 because there is no multi-tenant access yet.

## Out of scope for this ADR

- Streaming uploads / resumable transfers (M3+).
- Encryption-at-rest beyond what the host filesystem provides.
- Retention/cleanup policies for `runs/` cache (covered by `.gitignore` for now).
- An `artifacts upload` CLI command — that ships when the M3 worker arrives.

## References

- `supabase/migrations/0001_init.sql` — `artifacts` table.
- `tools/kca/run.py` — creates `runs/<comp>/<run_id>/artifacts/`.
- ADR-004 in `docs/design-decisions.md` — "Store code in git, artifacts in storage, metadata in Postgres."
