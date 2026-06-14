# M9-T001: Download Spaceship Titanic data + verify manifest

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Download the Spaceship Titanic competition data into a local workspace,
generate / verify a sha256 manifest, and commit ONLY the manifest. Raw
data is gitignored.

This task assumes **M9-T000 closeout is PASS**.

## Read first

1. M9-T000 closeout
2. `tools/kca/kg.py::cmd_download`, `::cmd_verify`
3. `.gitignore` (confirm `data/` is ignored)
4. `supabase/migrations/0004_m4_competition_repo.sql` (competition_data
   table layout, if used)
5. `docs/engineering-practice.md` §evidence (manifests / artifacts)

## Scope

1. Run
   ```
   kca kaggle download --competition spaceship-titanic \
     --path data/spaceship-titanic \
     --json
   ```
   The `--path` is the default but stated explicitly for the closeout
   record.
2. Run
   ```
   kca kaggle verify --path data/spaceship-titanic --json
   ```
   Confirm 0 mismatches.
3. Commit `data/spaceship-titanic/manifest.json` only. Raw CSV / parquet
   files must not be staged (verify with `git status` before staging).
4. Add (or confirm) a row in the competition data table (if M4's schema
   uses one), or record the manifest path in the run artifact for M9-T002.

## Non-goals

- Do not commit raw competition data files.
- Do not run `kca kaggle submit` / `push` / `upload`.
- Do not run the worker yet — that's M9-T002.
- Do not change the manifest format introduced in M5.

## Acceptance criteria

- `data/spaceship-titanic/manifest.json` exists in the worktree.
- `data/spaceship-titanic/train.csv` and `test.csv` exist locally but are
  **not** staged.
- `kca kaggle verify` reports all entries match.
- `git status` shows `data/spaceship-titanic/manifest.json` as the only
  new staged path under `data/`.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- Network out to `kaggle.com` / `*.kaggle.com` is allowed (already in
  the sandbox allow-list).
- `git commit` and `git push` deferred to milestone closeout.
- No `cat`/`grep`/`head` over `.env*` or `kaggle.json`.

## Closeout format

```
M9-T001 closeout
  Downloaded files: train.csv, test.csv, sample_submission.csv, ...
  Manifest: data/spaceship-titanic/manifest.json (sha256 entries: <n>)
  Verify result: PASS | FAIL
  Staged: data/spaceship-titanic/manifest.json (raw data NOT staged)
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T002 ready to start
```

## Stop condition

Stop after 60 turns. If Kaggle download requires accepting competition
rules interactively, halt and ask — do not encode a "y" / "yes" through
the agent without human approval.
