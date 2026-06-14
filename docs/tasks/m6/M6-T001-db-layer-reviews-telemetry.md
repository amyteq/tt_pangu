# M6-T001: DB layer — reviews + telemetry helpers

## Milestone
M6.

## Goal
Extend `tools/kca/db.py` with helpers for the two new M6 tables and the
new `agent_jobs.otel_*` columns. Keep the no-async / parameterised-SQL
discipline from M5.

## Read first
1. `docs/tasks/m6/M6-T000-migration-0006-reviews-spans.md`.
2. `tools/kca/db.py` (`__all__`, `_with_conn` pattern).
3. `supabase/migrations/0006_*.sql` (from T000).

## API additions
Add to `__all__` and implement:

```python
# reviews
create_review(*, job_id, reviewer_model, verdict, reviewer_kind="sync",
              target_op=None, rationale=None, evidence=None,
              run_id=None, cost_usd=0.0, decision_id=None,
              otel_span_id=None) -> str
get_review(review_id) -> dict
list_reviews(job_id=None, verdict=None, limit=50) -> list[dict]
find_review_for_op(job_id, target_op) -> dict | None

# telemetry
record_span(*, trace_id, span_id, parent_span_id=None, job_id=None,
            kind, name, started_at, ended_at=None, duration_ms=None,
            attributes=None, status="ok", error=None) -> int
list_spans(trace_id=None, job_id=None, kind=None, limit=200) -> list[dict]

# agent_jobs.otel_*
set_job_trace(job_id, trace_id, root_span_id) -> None
```

## Design rules
- All writes go through `_with_conn`.
- `verdict` must be one of `{approve, reject, abstain}`; raise `ValueError` otherwise.
- `record_span` is best-effort: it accepts a partial row (no `ended_at` for
  in-flight spans) and is callable from the OTEL exporter without raising.
- `find_review_for_op` returns the newest matching row, or None.

## Acceptance criteria
- `python -c "from tools.kca import db; print(sorted(s for s in dir(db) if 'review' in s or 'span' in s or 'trace' in s))"`
  shows the new symbols.
- Live smoke (with DB):
  ```python
  rid = db.create_review(job_id=<existing>, reviewer_model="rtx4090",
                        verdict="approve", target_op="kaggle_submit",
                        rationale="diff looks correct")
  assert db.get_review(rid)["verdict"] == "approve"
  ```
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 20 turns. If a constraint name collides with existing rows,
report it and exit; do not silently drop the constraint.
