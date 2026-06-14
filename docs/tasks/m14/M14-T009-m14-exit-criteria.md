# M14-T009: Regression tests + eval-suite CI gating + exit criteria + final review (issue #63)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Add `tests/test_m14_*.py` covering the M14 surfaces; add the eval-suite
CI score-delta gate (issue #63, per `docs/milestones/m13/final-review.md` follow-up
3); run the milestone validation matrix; write `docs/milestones/m14/final-review.md`
via the `milestone-final-review` skill; update PROJECT_STATE / README /
milestones / handoffs; and run `worktree-milestone-pr` to commit
per-loop-prompt, push the branch, and open the M14 PR.

Assumes **all M14 closeouts T000–T008 are PASS** (T008 may be
PASS-WITH-DEVIATION; document it).

## Read first
1. All M14 closeouts T000–T008.
2. `docs/milestones/m10/final-review.md` + `docs/milestones/m8_5/final-review.md` (layout precedent).
3. `milestone-final-review` skill; `worktree-milestone-pr` skill.
4. Issue #63 (gate PRs on eval score-delta).
5. `docs/adr/0019-eval-regression-suite.md` (the M13 suite definitions this gates on).
6. `runs/m13-eval/<ts>/report.json` (the diffable artefact `kca eval report` produces).

## Scope
1. **`tests/test_m14_*.py`** covering:
   - `kca goal {init, show, update}` happy + failure paths (ACTIVE_GOAL_EXISTS).
   - `kca explore init / run / rank` against a fake search space (dry-run; no real training).
   - `cmd_push` concurrency refusal when the limit is reached (fixture-driven).
   - `cmd_push` credentials pre-check refusal matching `cmd_submit`'s envelope (#62 + T004).
   - `_watch_kernel_until_terminal` state machine QUEUED → RUNNING → TERMINAL cadence (mocked clock); 500-non-terminal; STALLED release.
   - stuck detector fires at 3 non-improving SCORED submissions; NULL-score neither advances nor resets.
   - escalation row + redacted escalation doc written.
2. **Eval-suite CI gating (#63):**
   - Define per-suite `failure_threshold` in `docs/adr/0019-eval-regression-suite.md`
     (absolute for shape-checks, relative for metric deltas).
   - Add a GitHub Actions step `eval-delta-check` that runs `kca eval run`
     against the baselined snapshot and fails the PR if any suite regresses
     past its threshold (reuses the M13 nightly runner).
   - Document the bypass: an `eval:waive-delta` PR label (human-only)
     skips the gate with a mandatory rationale comment, recorded in
     `agent_tool_audit`.
3. **Validation matrix + final review:** run the full matrix, then
   `milestone-final-review` writes `docs/milestones/m14/final-review.md` mirroring
   the M10 / M8.5 layout.
4. **Source-of-truth updates (protocol §5):** PROJECT_STATE.md, README.md,
   `docs/milestones/README.md` (mark M14), `docs/milestones/m14/handoff.md`.
5. **`worktree-milestone-pr`:** commit per Loop Prompt (T000…T009), push
   the worktree branch, open the M14 PR against `main`.

## Non-goals
- No new feature surface (T002–T007 own those).
- No real Kaggle push (T008 owned the only live writes).
- No `gh pr merge` (human-only).

## Acceptance criteria
- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (existing) + new `tests/test_m14_*.py` all pass (DB-gated tests SKIP
  cleanly without `SUPABASE_DB_URL`).
- `ruff check .` and `ruff format --check .` — clean.
- `eval-delta-check` GitHub Actions step exists; fails a synthetic
  regressing PR; the `eval:waive-delta` bypass is documented + audited.
- ADR-0019 carries per-suite `failure_threshold` values.
- `docs/milestones/m14/final-review.md` exists; follows the M10 / M8.5 layout;
  validation matrix has a PASS/FAIL/SKIP tally with concrete evidence.
- PROJECT_STATE / README / milestones / handoffs updated.
- The M14 PR is open against `main` (not merged), body =
  `docs/milestones/m14/final-review.md`.

## Allowed / forbidden paths
- ALLOWED: `tests/test_m14_*.py`, `.github/workflows/*` (eval-delta-check
  step), `docs/adr/0019-eval-regression-suite.md` (failure_threshold
  addendum), `docs/milestones/m14/final-review.md`, `PROJECT_STATE.md`, `README.md`,
  `docs/milestones/README.md`, `docs/milestones/m14/handoff.md`.
- FORBIDDEN: new feature code in `tools/kca/` / `src/worker/` (fixes
  route back to the owning task); `gh pr merge`.

## Permissions
- LOCAL_WRITE (Supabase) for DB-gated tests — ALLOWED.
- `git add` / `git commit` / `git push` / `gh pr create` — ALLOWED at
  this task (milestone close, per protocol §5 + `worktree-milestone-pr`).
- No `git push --force`, no `gh pr merge`, no push to `main`.
- No real Kaggle / LLM.

## Closeout format
```
M14-T009 closeout
  Tests: tests/test_m14_*.py (+<n>); pytest <X> passed / <Y> skipped (0 failures)
  Eval CI gate: eval-delta-check added; failure_threshold in ADR-0019; eval:waive-delta bypass documented (#63)
  ruff: clean
  Validation matrix: <P> PASS / <S> SKIP / <F> FAIL
  Final review: docs/milestones/m14/final-review.md written
  Source of truth: PROJECT_STATE / README / milestones / handoffs updated
  PR: <url> (open against main; not merged)
  Acceptance: PASS — M14 exit criteria met
  Next: M15 (cross-account quota pool #21; FK hardening #60; dataset/model uploads)
```

## Related issues
- #63 (eval score-delta gate) + a new test-gap issue.

## Stop condition
Stop after 60 turns. HALT and ask if:
- Any M14 exit criterion (per `docs/milestones/README.md` §M14) is unmet — do
  NOT fabricate a PASS; record FAIL/SKIP with the reason.
- `eval-delta-check` cannot reuse the M13 nightly runner without a
  workflow restructure beyond scope — pin the minimal change and confirm.
- `worktree-milestone-pr` pre-flight fails (branch not off `main`,
  out-of-scope files staged) — halt and ask.
```
