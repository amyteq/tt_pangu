# M6-T007: `kca review` CLI

## Milestone
M6.

## Goal
Surface reviewer state through a CLI so a human can list past reviews, see
a specific verdict + rationale, and trigger a manual reviewer run against
a job that's already finished (async post-mortem path, even though M6
default is sync gating).

## Read first
1. `tools/kca/decisions.py` — subcommand pattern.
2. `tools/kca/research.py` — `--json` + DB-graceful-degradation pattern.
3. `src/worker/reviewer.py` (from T004).
4. `tools/kca/db.py::create_review` / `list_reviews` (from T001).

## Files

### New: `tools/kca/review.py`

```
kca review list [--job-id <uuid>] [--verdict approve|reject|abstain]
                [--limit 50] [--json]
kca review show --id <review_id> [--json]
kca review run --job-id <uuid> [--target-op <op>] [--reviewer-model <id>]
               [--dry-run] [--json]
```

- `list`: `db.list_reviews(...)`; degrade to `{ok: true, reviews: [],
  db_warning: "..."}` when no DB.
- `show`: `db.get_review(...)`; emit `--json` with verdict + rationale +
  evidence.
- `run`: builds a `ReviewRequest` from `db.list_job_events(job_id)` + the
  job's prompt, invokes `Reviewer(...)`, writes `agent_reviews`, prints
  the verdict.

### Update: `tools/kca/kca.py`
Register the `review` subparser.

## Acceptance criteria
- `kca review --help` lists `list / show / run`.
- `kca review list --json` exits 0 without DB and returns
  `{ok: true, reviews: []}`.
- With DB up and one prior review row: `kca review list --json` returns it.
- `kca review run --job-id <uuid> --dry-run --json` returns
  `{verdict: "approve", reviewer_model: "<configured>", ...}` and inserts
  one row in `agent_reviews`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 15 turns. If the dry-run reviewer hangs (it should not — it
returns immediately), enforce `KCA_REVIEWER_TIMEOUT_S` at the call site.
