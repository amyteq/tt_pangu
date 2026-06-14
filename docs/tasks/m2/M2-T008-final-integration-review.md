# M2-T008: M2 final integration review

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Confirm M2 exit criteria are met. Produce a PR-ready summary.

## Read first
1. `docs/milestones/README.md` — M2 exit criteria
2. All `docs/tasks/m2/M2-T*.md` specs
3. `supabase/migrations/0001_init.sql` + `0002_kca_run_alignment.sql`
4. `tools/kca/db.py`, `tools/kca/run.py`, `tools/kca/kaggle.py`
5. `tests/test_kca_smoke.py`, `tests/test_kca_db_smoke.py`
6. `docs/adr/0007-artifact-storage-local-first.md`

## Required checks
```bash
# 1. Migrations apply cleanly
make supabase-up
supabase db reset --debug

# 2. M1 smoke tests still pass
python -m pytest tests/test_kca_smoke.py -v

# 3. M2 DB smoke tests pass
KCA_DB_TARGET=local SUPABASE_DB_URL="postgres://postgres:postgres@localhost:54322/postgres" \
  python -m pytest tests/test_kca_db_smoke.py -v

# 4. End-to-end manual loop
KCA_DB_TARGET=local SUPABASE_DB_URL=... python tools/kca/kca.py run init --competition titanic --hypothesis "b" --json
KCA_DB_TARGET=local SUPABASE_DB_URL=... python tools/kca/kca.py run record-metric --run-dir runs/titanic/<ts> --key cv --value 0.82 --json
KCA_DB_TARGET=local SUPABASE_DB_URL=... python tools/kca/kca.py run list --json

# 5. Approval gate records a pending decision
KCA_ALLOW_REMOTE= KCA_DB_TARGET=local SUPABASE_DB_URL=... \
  python tools/kca/kca.py kaggle submit --competition x --file /dev/null --message t --json
psql "$SUPABASE_DB_URL" -c "select decision_type, status from human_decisions order by created_at desc limit 1;"

# 6. Files committed clean
git status --short
```

## Acceptance criteria
M2 exit (per milestones.md): "Schema and data model support MVP-1 artifacts and future worker jobs. A local/dev worker can record run events without needing product UI."

- Migration 0002 applies on a fresh local Supabase.
- `kca run` operates DB-first; FS files become a cache.
- `kca kaggle submit` block path records a `human_decisions.pending` row.
- All M1 + M2 smoke tests pass.
- ADR-007 (artifact storage) is in place.
- No secret/credential paths read.
- No code path performs a real Kaggle remote write.

## Deliverable
A PR-ready summary covering: files changed, behavior added, tests run, risks, M3 follow-ups.

## Stop condition
Stop after 50 turns if any acceptance check fails and the cause is not
clearly fixable. Summarize the failing check, exact command output, and
proposed next-smallest patch.
