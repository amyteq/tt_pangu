# M12-T005: UI — HackathonDeadline + SubmissionChecklist pages

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Add two new UI pages and their routes, with vitest + Playwright smoke
tests:

1. `ui/src/pages/HackathonDeadline.tsx` — countdown to
   `competitions.deadline`; phase indicator (open / submission-pending /
   judging / closed); read-only team roster.
2. `ui/src/pages/SubmissionChecklist.tsx` — templated checklist
   driven by `competitions.submission_format`; per-item status
   (todo / done / blocked) inferred from the run's submission_pack
   directory.

Existing `ApprovalInbox` / `DecisionGate` pages handle the
`devpost_submit` gate. No new approval UI in M12.

## Tag

Routine.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 5
4. `docs/adr/0014-ui-stack.md`
5. `ui/src/pages/ApprovalInbox.tsx` — typed read pattern + supabase-js shape
6. `ui/src/pages/DecisionGate.tsx` — approve / reject UI (reuse, do not duplicate)
7. `ui/src/pages/Dashboard.tsx` — route + layout precedent
8. `ui/src/pages/Research.tsx` — typed read pattern
9. `ui/src/lib/supabase.ts` — typed client
10. `ui/playwright.config.ts` and an existing Playwright smoke test
11. `supabase/migrations/0009_m12_competition_type_teams.sql` (T002) —
    `competitions.deadline`, `competitions.submission_format`, `teams`,
    `team_memberships`
12. `.kca/skills/hackathon-experiment-loop/SKILL.md` (T004) — what
    artefacts land in `runs/<slug>/<run_id>/submission_pack/`

## Scope

1. Add `ui/src/pages/HackathonDeadline.tsx`:
   - Route: `/hackathons/:slug/deadline`.
   - Reads: `competitions` row by slug; `team_memberships` joined on
     `teams` for the slug's team (per the ADR-0018 team-scoped rules).
   - Renders: deadline countdown (live updating, computed from
     `competitions.deadline`), phase chip
     (`competitions.deadline > now()` → "open"; else "closed"; richer
     phase strings deferred), team roster table (name + role,
     read-only).
   - Use existing components / styles; do NOT introduce a new UI lib.
2. Add `ui/src/pages/SubmissionChecklist.tsx`:
   - Route: `/hackathons/:slug/runs/:run_id/checklist`.
   - Reads: `competitions.submission_format` (jsonb); the latest
     `experiment_runs` row for the run_id; the contents of
     `runs/<slug>/<run_id>/submission_pack/` (via a dedicated
     `services/decision_api` or equivalent endpoint — see step 3).
   - Renders: a checklist table — one row per `submission_format`
     item with status (todo / done / blocked) and an "evidence"
     column linking to the file under submission_pack.
   - Status is **inferred**, not mutable, in M12. A mutate path is
     a follow-up.
3. If `services/decision_api` does not expose a way to read
   submission_pack file presence, add ONE new READ_ONLY endpoint:
   `GET /runs/<run_id>/submission_pack` → returns the file list.
   Implementation note: this re-uses the same DB/storage layer the
   submission_checklist tool reads (T004). Mirror its checklist
   structure so the UI and the worker agree.
4. Wire routes in `ui/src/App.tsx` (or wherever route registration
   lives — mirror existing patterns).
5. Tests:
   - `ui/src/pages/HackathonDeadline.test.tsx` — vitest smoke:
     renders without crashing; shows the deadline countdown and the
     team roster from a mocked supabase client.
   - `ui/src/pages/SubmissionChecklist.test.tsx` — vitest smoke:
     renders the expected checklist rows from a mocked client.
   - `ui/tests/m12-pages.spec.ts` — Playwright smoke: navigates to
     each new route in a built UI; asserts the H1 + 1–2 visible
     items. Reuses the existing test fixtures / supabase mock.

## Non-goals

- Do NOT make the checklist mutable in M12.
- Do NOT add a "Submit to Devpost" button. The reviewer-gate path
  in T007 lives in `ApprovalInbox.tsx`; users approve there.
- Do NOT add a new approval / decision page.
- Do NOT add an idea-board page in M12. The idea / discussion data
  rides on `research_items`; the existing `Research.tsx` page covers
  it.
- Do NOT add a "team invite" UI. Team membership is read-only in M12.
- Do NOT add new charts / visualisations beyond the countdown.

## Acceptance criteria

- `ui/src/pages/HackathonDeadline.tsx` exists; route resolves;
  renders the deadline + roster for a seeded competition + team
  combo.
- `ui/src/pages/SubmissionChecklist.tsx` exists; route resolves;
  renders the expected checklist for a seeded run.
- New vitest tests pass (`pnpm -C ui run test --run`).
- New Playwright smoke passes (`pnpm -C ui run e2e`).
- `pnpm -C ui lint` and `pnpm -C ui typecheck` clean.
- `pnpm -C ui build` clean.
- Existing vitest + Playwright tests still pass.
- If a new endpoint was added to `services/decision_api`, it returns
  READ_ONLY data only; covered by an existing or new test under
  `services/decision_api/tests/`.

## Permissions

- File writes to: `ui/src/pages/HackathonDeadline.tsx`,
  `ui/src/pages/SubmissionChecklist.tsx`, route registration file,
  vitest test files, Playwright smoke file. Possibly
  `services/decision_api/app.py` (one new READ_ONLY GET route) + its
  test.
- No DB schema changes (T002 already shipped them).
- No external network calls.
- `git commit` / `git push` deferred to T009 closeout.

## Closeout format

```
M12-T005 closeout
  New pages:
    - ui/src/pages/HackathonDeadline.tsx (route /hackathons/:slug/deadline)
    - ui/src/pages/SubmissionChecklist.tsx (route /hackathons/:slug/runs/:run_id/checklist)
  New endpoint (if added): services/decision_api GET /runs/<run_id>/submission_pack
  vitest: N tests passing
  Playwright: ui/tests/m12-pages.spec.ts passing
  pnpm -C ui {lint,typecheck,build}: clean
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T006 (local e2e hackathon flow)
```

## Related issues

- Closing issue for M12 — gets a comment with screenshots (no
  credentials in screenshots) of the two new pages.
- ADR-0014 (UI stack) — referenced, not changed.

## Stop condition

Stop after 80 turns. If `pnpm` is not on PATH in the agent's local
sandbox, SKIP the build/lint/typecheck/test commands locally and
delegate to CI — same posture as M9 / M10. Mark the SKIP explicitly
in the closeout. If a new endpoint creates a SQL / RLS policy issue,
halt and ask — do NOT relax RLS policies without explicit approval.
