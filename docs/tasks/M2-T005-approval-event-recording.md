# M2-T005: approval event recording

## Milestone
M2: Supabase / control-plane foundation.

## Goal
When `kca kaggle submit`, `kca kaggle push`, or `kca kaggle upload` is blocked
by the Layer-A env gate (`KCA_ALLOW_REMOTE != "1"`), record the attempt as a
`pending` row in `human_decisions` so an approval inbox can surface it later.

This is the first concrete bridge between kca's runtime gates and the control
plane.

## Read first
1. `tools/kca/kaggle.py` (current gate)
2. `tools/kca/db.py` (T003)
3. `supabase/migrations/0001_init.sql` — `human_decisions` table

## Required behavioral change
In `tools/kca/kaggle.py`:
- When `_gate()` returns `False` (blocked), before emitting the blocked envelope:
  1. Call `db.insert_approval_request(session_id=None, decision_type='kaggle.<subcmd>', prompt=<one-line summary>, options=<args>)`.
  2. If the DB insert fails (e.g., DB down locally), emit the blocked envelope as today and add `approval_recorded: false` plus a stderr warning. Do not raise.
  3. If insert succeeds, add `approval_request_id: <uuid>` to the envelope.

`decision_type` values introduced:
- `kaggle.submit`
- `kaggle.push`
- `kaggle.upload`

`prompt` example: `"Approve Kaggle submit to competition=titanic file=submission.csv message='baseline v1'"`.

## Design constraints
- The block path must remain fast and unconditional — DB record is best-effort.
- Never block on DB to refuse a remote operation; the env gate is the hard refusal.
- `session_id` is nullable because kca CLI doesn't yet track sessions; M3 will populate it.

## Non-goals
- Do not move the gate decision from env-var to "approved row exists" — that's M3 / M4.
- Do not surface a UI/CLI for approving/rejecting (M7+ owns the UI; CLI command can be a follow-up).

## Acceptance criteria
- `KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit --competition x --file /dev/null --message t --json` still exits 2.
- Output JSON now contains `approval_request_id` (uuid) when DB is reachable, or `approval_recorded: false` when not.
- `select count(*) from human_decisions where decision_type='kaggle.submit' and status='pending';` increments per blocked attempt.

## Suggested checks
```bash
make supabase-up
KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit --competition titanic --file /dev/null --message t --json
psql "$SUPABASE_DB_URL" -c "select decision_type, status, prompt from human_decisions order by created_at desc limit 1;"
```

## Stop condition
Stop after 30 turns if `human_decisions`'s required columns conflict with
kca's available context (e.g., it needs a project_id that kca can't supply).
Propose either a schema tweak (T001 follow-up) or a column-nullability change.
