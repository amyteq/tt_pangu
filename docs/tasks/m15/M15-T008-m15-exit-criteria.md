# M15-T008: regression tests + exit criteria + `docs/milestones/m15/final-review.md`

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Add the M15 regression tests, run the milestone validation matrix, write
`docs/milestones/m15/final-review.md`, and update the source-of-truth docs
(PROJECT_STATE / README / milestones index) + the M16 handoff. Closes M15.

Assumes **M15-T000…T007 closeouts are PASS** (T007 may be PASS-WITH-DEVIATION
only if a documented, human-acknowledged live blocker prevents the LB score).

## Read first
1. All M15 closeouts (T000–T007).
2. `docs/milestones/m14/final-review.md` + `docs/milestones/m14/handoff.md`
   (layout precedents).
3. `milestone-final-review` skill + `worktree-milestone-pr` skill.
4. `docs/milestone-loop-protocol.md` §5 (source-of-truth update rule).
5. `PROJECT_STATE.md` (the "Current milestone" + ADR-0018 follow-up sections to
   update).

## Scope
1. **Regression tests** `tests/test_m15_*.py` covering:
   - refresh-rules port: auto-ingest on the new API surface + degradation path
     preserved (T001).
   - push → submit → score with submit mocked, incl. autonomy-screen branch +
     budget-gate counts-the-submit (T002).
   - submission_format schema validate-on-read: valid + invalid + permissive
     fallback per type (T003).
   - `approved_by_user_id` populate path + NULL-tolerant resolver (T004).
   - `profile_fallback` event emitted once per fallback per job (T005).
2. **Exit-criteria validation matrix** (mirror M14's `# | Check | Result |
   Notes` table); tally PASS / SKIP / FAIL.
3. **`docs/milestones/m15/final-review.md`** via `milestone-final-review`,
   mirroring the M14 layout.
4. **`docs/milestones/m15/handoff.md`** for M16 (carry the deferrals: #21/#85
   quota pool, #83 GPU; the `auth.users` FK finalisation).
5. **Source-of-truth updates**: `PROJECT_STATE.md` (flip current milestone to
   M16; mark #77/#78/#59/#60/#61/#64 resolved), `docs/milestones/README.md`
   (flip the M15 section status to ✓ done with the closure summary).

## Non-goals
- No new feature work — tests + closeout only. Bugs found are fixed in the
  owning task's scope, then re-validated here.

## Acceptance criteria
- `tests/test_m15_*.py` exists and covers T001–T005 paths; `python -m pytest`
  green (cloud DSN).
- The validation matrix maps each M15 exit criterion to a PASS/SKIP/FAIL row
  with a note.
- `docs/milestones/m15/final-review.md` exists and follows the M14 layout.
- `docs/milestones/m15/handoff.md` exists with the M16 deferral list.
- PROJECT_STATE / README / milestones index updated per protocol §5.
- `ruff check .` / `ruff format --check .` clean.

## Allowed / forbidden paths
- ALLOWED: `tests/test_m15_*.py`, `docs/milestones/m15/final-review.md`,
  `docs/milestones/m15/handoff.md`, `docs/milestones/README.md` (M15 status
  flip), `PROJECT_STATE.md`.
- FORBIDDEN: new feature code in `tools/kca/**` (fix in owning tasks),
  `supabase/migrations/**` (no new migrations).

## Permissions
- LOCAL_WRITE (Supabase) ALLOWED for test rows; pooler needs
  `dangerouslyDisableSandbox=true`.
- No real Kaggle / LLM (T007 owns the live run).
- `worktree-milestone-pr` commits per-loop-prompt, pushes the branch, opens the
  M15 PR against `main` (per protocol §5).

## Closeout format
```
M15-T008 closeout
  Tests: tests/test_m15_*.py — <X> passed (T001–T005 paths)
  Matrix: <P> PASS / <S> SKIP / <F> FAIL
  final-review: docs/milestones/m15/final-review.md written (M14 layout)
  handoff: docs/milestones/m15/handoff.md → M16 (deferrals #21/#85/#83 + auth.users FK)
  SoT: PROJECT_STATE / README / milestones index updated
  pytest / ruff: <X> passed; clean
  Acceptance: PASS — M15 closed
  Next: M16 (cross-account quota #21/#85 + cheaper GPU #83)
```

## Related issues
- #77, #78, #59, #60, #61, #64 (all M15 issues — verify each is resolved /
  closeable by this task's matrix).

## Stop condition
Stop after 60 turns. HALT and ask if:
- An exit criterion FAILs and the fix is a non-trivial change to an owning
  task's code — pin the failure and decide (fix-in-place vs PASS-WITH-DEVIATION)
  with the human before closing the milestone.
