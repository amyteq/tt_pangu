# M8-T014: M8 exit criteria + final review + handoff

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 14; extracted here for the double-layer convention.

## Goal
Verify ALL M8 exit criteria. Gate before M8 is declared complete.

## Read first
1. All prior M8 task specs (`docs/tasks/m8/M8-T000` through `M8-T013`).
2. `docs/milestones/m7/final-review.md` (template).
3. `docs/milestones/README.md` (§ Milestone final-review protocol).
4. `docs/milestones/_templates/handoff-prompt.md` (handoff template).

## Validation matrix (run each, report PASS / FAIL / SKIP)

### Backend follow-ups (from M7)
1. `supabase/migrations/0007_m8_tool_audit.sql` applied; `agent_tool_audit`
   table + `v_agent_tool_audit_recent` view present.
2. `tools/kca/agent/audit.py` dual-writes JSONL + DB; never raises on DB error.
3. `SkillValidationError` raised on bad name; on unknown tool in `allowed-tools`.
4. `.kca/skills/_test_fixture/` removed; `tests/fixtures/skills/_test_fixture/
   SKILL.md` present.
5. `kca skill run <name> --execute` creates an `agent_jobs` row and drives
   `AgentWorker`; allow/ask/deny paths all produce the right audit rows.
6. `src/worker/worker.py::_tool_call` honours `ToolSpec.timeout_s`,
   `ToolSpec.sandbox`, and `JobPolicy.approval_gates`.

### UI app shell
7. `cd ui && pnpm install --frozen-lockfile` succeeds.
8. `pnpm -C ui typecheck` → 0 errors.
9. `pnpm -C ui lint` → 0 issues.
10. `pnpm -C ui build` → 0 errors.
11. `pnpm -C ui test -- --run` → all pass (≥ 12 vitest cases).

### UI pages
12. Dashboard shows Projects + Active competitions + Inflight runs + Recent decisions.
13. `/runs/:jobId` renders span swim-lane + event log.
14. `/experiments` table sortable by CV + LB.
15. `/research` lists items with trust badges; external links have
    `rel="noopener noreferrer"`.
16. `/approvals` lists pending decisions; `/approvals/:id` has Approve /
    Reject / Ask-improve.
17. `/artifacts` blocks binary preview and CSV >100 rows.

### Action service
18. POST `/decision/:id/approve` idempotent (409 on second call).
19. POST `/decision/:id/reject` enforces `minLength=8` on reason.
20. POST `/decision/:id/ask-improve` appends `agent_job_events("feedback")`.
21. No service-role key reachable from the browser (search `ui/` for
    `SERVICE_ROLE` → 0 matches).

### CI
22. `.github/workflows/test.yml` has a `ui` job and a gated `live-db` job.
23. `python -m pytest tests/ -v -m "not db"` → 0 failures.
24. `ruff check .` → 0 issues; `ruff format --check .` → 0 issues.

### Smoke + e2e
25. `python -m pytest tests/test_m8_smoke.py -v` → 13/13 pass (or ≥ 12 + any extras).
26. `pnpm -C ui exec playwright test` → 4/4 pass.

### Architecture doc
27. `docs/architecture/m8-ui-shell.md` exists, ≥ 100 lines.
28. All required headings present (Overview, Layer map, Data flow per
    page, Auth model, Approval gate semantics, Audit trail, Adding a
    new page, Adding a new approve-class operation).

## Final document
Print full validation matrix (check | PASS/FAIL/SKIP | note).
If all non-SKIP pass → output `M8 EXIT CRITERIA MET`.

Create `docs/milestones/m8/final-review.md` following the structure of
`docs/milestones/m7/final-review.md` with:
- Validation matrix.
- What landed (files created / modified, with one-line purpose each).
- DB access note (which checks needed `dangerouslyDisableSandbox`).
- M9 follow-ups list.

Also update, in order:
1. `PROJECT_STATE.md` — set current milestone to M9, summarise M8
   deliverables, clear M8 open decisions.
2. `README.md` — update "Current milestone" from M8 to M9.
3. `docs/milestones/README.md` — mark M8 ✓ done with one-line summary; bump
   the header status line (the stale "M6 done, M7 in planning" line
   should already have been fixed during M7 closeout; if not, fix it now).
4. `docs/milestones/m8/handoff.md` — per-milestone handoff prompt for the
   next AI tool / session that will start M9 (live Kaggle regression test
   for Spaceship Titanic, per `docs/milestones/README.md § M9`). Use
   `docs/milestones/_templates/handoff-prompt.md` as the canonical template. Populate:
     - Read-first list (`PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`, M9
       section of `docs/milestones/README.md`, `docs/milestones/m8/final-review.md`, latest
       ADRs, `docs/architecture/m8-ui-shell.md`,
       `docs/architecture/kca-cli-architecture.md`).
     - "State at M8 exit" (1–3 lines summarising what landed +
       exit-matrix outcome + M9 follow-ups list).
     - "Current task" stub for the first M9 task (typically Prompt 0
       of `docs/milestones/m9/loop-prompts.md` once that file exists; if not yet
       written, the first task is to draft it).
   This step is required by `docs/milestones/README.md § Milestone final-review
   protocol`; do not skip it.

## Acceptance criteria
- Validation matrix above all PASS (or SKIP with documented reason).
- `docs/milestones/m8/final-review.md` exists and mirrors the m7 layout.
- `M8 EXIT CRITERIA MET` printed.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`, and
  `docs/milestones/m8/handoff.md` updated as listed above.

Report: full matrix, final status.

## Stop condition
Stop after 30 turns.
