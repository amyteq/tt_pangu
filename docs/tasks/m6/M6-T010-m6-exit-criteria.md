# M6-T010: M6 exit criteria + `docs/milestones/m6/final-review.md`

## Milestone
M6.

## Goal
Verify all M6 exit criteria before the milestone is declared complete.
Mirror the M5 validation-matrix pattern; produce `docs/milestones/m6/final-review.md`
with the M7 follow-up list at the bottom.

## Read first
1. `docs/milestones/m5/final-review.md` (template).
2. All other M6 task specs.

## Validation matrix (run each, report PASS/FAIL/SKIP)

Schema + DB (require `SUPABASE_DB_URL`):
1. Migration 0006 idempotent (apply twice).
2. `agent_reviews` table exists with all columns from T000.
3. `agent_telemetry_spans` table exists.
4. `agent_jobs.otel_trace_id` / `otel_root_span_id` columns present.

Local-model layer:
5. `kca local list --json` lists 0 endpoints with the default env.example.
6. With 2 endpoints set via env, `kca local probe --json` reports
   per-endpoint ok / latency.
7. `kca local pick --json` returns the highest-priority reachable endpoint
   (or fallback when all are down).
8. `model_for("summarise")` resolves to the picked endpoint's served name
   when reachable, and to `KCA_LOCAL_FALLBACK_MODEL` when not.

Reviewer:
9. `kca review --help` lists `list / show / run`.
10. `Reviewer(dry_run=True).review(...)` returns `verdict=approve`.
11. Reviewer gate fires on `kaggle_submit` in a dry-run job; an
    `agent_reviews` row is created with `verdict=approve`.
12. Reject path: forcing `verdict=reject` either escalates to
    `human_decisions` (default) or fails the job (`ESCALATE_REJECT=0`).

OTEL:
13. With `KCA_OTEL_ENABLED=1 KCA_OTEL_EXPORTERS=console`, a dry-run job
    emits stderr span lines for `job / turn / tool`.
14. With `KCA_OTEL_EXPORTERS=sqlite`, the SQLite file has rows.
15. With `KCA_OTEL_EXPORTERS=supabase` + DB up, `agent_telemetry_spans`
    has rows for the same trace_id.
16. `KCA_OTEL_ENABLED=0` ⇒ no span output.

TC-3:
17. TC-3 Spaceship Titanic 8/8 checks PASS.

Tests:
18. `python -m pytest tests/ -v` (no DB) — 0 failures.
19. `python -m pytest tests/ -v` (live DB) — 0 failures.

## Output
- Print the validation matrix.
- If all non-SKIP pass: output `M6 EXIT CRITERIA MET`.
- Create `docs/milestones/m6/final-review.md` (mirror `docs/milestones/m5/final-review.md`
  template) with a "M7 follow-ups" section including:
  1. UI shell — Lovable / TS dashboard surfacing reviews, spans, runs.
  2. Reviewer self-improvement loop — promote frequent rationales to ADR
     candidates.
  3. OTEL trace export to Tempo/Honeycomb (off by default).
  4. Local-model warm pool — keep one endpoint loaded across jobs.
  5. Multi-agent debate mode (>= 2 independent reviewers per high-stakes
     op).
  6. Per-competition reviewer policy overrides via `competition_policy`.

## Acceptance criteria
- Validation matrix above all PASS (or SKIP with documented reason).
- `docs/milestones/m6/final-review.md` exists and mirrors the m5 layout.
- `M6 EXIT CRITERIA MET` printed.

## Stop condition
Stop after 20 turns.
