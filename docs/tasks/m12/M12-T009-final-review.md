# M12-T009: M12 exit criteria + final review + closeout

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Run the M12 validation matrix; write `docs/milestones/m12/final-review.md`
mirroring the M9 / M9.4 / M10 layout; update canonical memory
(`PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`,
`docs/milestones/m12/handoff.md`); commit per-Loop-Prompt; push the
worktree branch; open the milestone PR against `main`.

This is the only M12 Loop Prompt that calls `worktree-milestone-pr`.

## Tag

Routine. Closeout task.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12 (current state — to be marked done)
3. `docs/milestones/m12/loop-prompts.md` (full milestone scope)
4. All M12 task closeouts (T000–T008)
5. `docs/milestones/m9/final-review.md`, `docs/milestones/m9_4/final-review.md`,
   `docs/milestones/m9_2/final-review.md` (recent final-review layouts)
6. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template
7. `docs/milestones/m9/handoff.md`, `docs/milestones/m9_4/handoff.md`,
   `docs/milestones/m9_2/handoff.md` (recent handoff precedents)
8. `.claude/skills/milestone-final-review/SKILL.md`
9. `.claude/skills/worktree-milestone-pr/SKILL.md`
10. `docs/milestone-loop-protocol.md` §5 (commit / push / PR cadence)

## Scope

1. Run the M12 validation matrix:
   - All T000–T008 closeouts marked PASS.
   - `docs/evidence/m12/t000-candidates.md` exists; closing issue
     records the picked slug.
   - All three Discovery / Debate Gate reports
     (`docs/evidence/m12/t001/discovery/*.md`) carry their canonical
     acceptance lines verbatim.
   - `docs/adr/0018-generalized-competition-type.md` exists; enum
     literal present.
   - `supabase/migrations/0009_m12_competition_type_teams.sql`
     applied locally; M9 / M10 baseline rows still resolve their
     gates correctly.
   - `tools/kca/devpost.py` + `kca devpost register/fetch/info` and
     `kca devpost submit` all behave as their task specs require.
   - `.kca/skills/hackathon-experiment-loop/SKILL.md`,
     `.kca/permissions/hackathon-runner.yaml`, the
     `submission_checklist` tool, and the two UI pages exist and
     parse / build clean.
   - `runs/<slug>/<run_id>/submission_pack/` exists with the four
     expected artefacts; `experiment_runs` row recorded with
     `metric_name='checklist_completion'`.
   - `agent_reviews` + `human_decisions` + `submissions` rows
     recorded for `target_op="devpost_submit"`; submission URL
     present.
   - `tests/test_m12_e2e.py` + `tests/test_m12_smoke.py` pass in
     their respective CI jobs.
   - `pnpm -C ui {lint,typecheck,build,test}` clean (or
     explicitly-marked SKIP if pnpm is unavailable in the local
     sandbox).
2. Invoke the `milestone-final-review` skill to produce
   `docs/milestones/m12/final-review.md`. The doc MUST follow the M9 / M9.4
   layout:
   - Header with date, summary, PASS / SKIP / FAIL counts.
   - Per-task validation matrix (one row per T000–T008, each with
     PASS / FAIL / SKIP + evidence link).
   - "Exit criteria" roll-up against the list in
     `docs/milestones/m12/loop-prompts.md` "Required tests / evidence" + the
     bullets in `docs/milestones/README.md` §M12.
   - "What landed" prose summary (ADR-0018, migration 0009,
     adapter, skill, profiles, UI pages, real Devpost submission
     metadata).
   - "Out-of-scope follow-ups" list (matches the loop-prompts
     file).
3. Update canonical memory (per `project_milestone_protocol.md`):
   - `PROJECT_STATE.md` — set current milestone to M13; update
     decisions list; record any new blockers surfaced during M12.
   - `README.md` — bump current-milestone section; reference
     `docs/milestones/m12/final-review.md` if applicable.
   - `docs/milestones/README.md` §M12 — mark `✓ done`; add a one-line
     shipped summary (date + key artefacts) using the same format
     as §M9 / §M9.4 done-marks.
4. Write `docs/milestones/m12/handoff.md` using
   `docs/milestones/_templates/handoff-prompt.md` as the template. Populate "State at
   handoff", "Read these files first", "Current task" with M13
   priorities (the M13 entry is the evaluation / reliability /
   regression-suite milestone).
5. Run the `worktree-milestone-pr` skill:
   - Commit per Loop Prompt (one commit per T000–T009; or a
     squash-friendly grouping if the protocol's §5 says so).
   - Push the `worktree-m12-planning`-derived branch to origin.
   - Open the milestone PR against `main` using
     `.github/pull_request_template.md`.
   - The "Live external submission" box may be checked in this PR
     (T007 is the one task that justifies it). Link the approval
     comment AND the Devpost submission URL in the PR body.
   - Do NOT merge. Merge requires explicit human approval per
     memory `feedback_permissive_github_dev_phase.md`.
6. Verify the PR's CI status before reporting PASS:
   - `no-db pytest` green
   - `live-db pytest` green
   - `ruff` clean
   - UI `pnpm` jobs green (or explicit SKIP if the pipeline
     accepts that posture)

## Non-goals

- Do NOT merge the PR. Merge is a human decision.
- Do NOT renumber any other milestone (M11 / M13 / etc. stay where
  they are).
- Do NOT add a second real Devpost submission in this task. T007 is
  the only place that runs one.
- Do NOT change `.claude/settings.json`, `.claude/hooks/`, or any
  permission profile beyond what T002–T007 already shipped.
- Do NOT skip the validation matrix to push the PR earlier. The
  final-review skill writes the matrix; the PR cannot open without
  it.

## Acceptance criteria

- `docs/milestones/m12/final-review.md` exists; reports PASS (or PASS-with-SKIP
  for documented exceptions); per-task matrix populated.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md` §M12, and
  `docs/milestones/m12/handoff.md` updated.
- One commit per Loop Prompt landed on the worktree branch.
- Branch pushed to origin.
- PR opened against `main`; CI status green for `no-db pytest`,
  `live-db pytest`, `ruff`, and UI `pnpm` jobs.
- PR body links: `docs/milestones/m12/final-review.md`, ADR-0018, T007's
  approval comment, T007's Devpost submission URL.
- The closing GitHub issue for M12 is updated with the PR URL and
  closed once the PR merges (merge is human-gated; T009 stops at PR
  open + green CI).
- No new tests / migrations / source files outside this task's
  scope.

## Permissions

- File writes to: `docs/milestones/m12/final-review.md`, `PROJECT_STATE.md`,
  `README.md`, `docs/milestones/README.md` (§M12 done-mark only),
  `docs/milestones/m12/handoff.md`.
- `git add`, `git commit`, `git push` to the worktree branch.
- `gh pr create`, `gh issue edit`, `gh issue comment` — all
  non-destructive, allowed under the dev-phase GitHub carve-out
  (memory `feedback_permissive_github_dev_phase.md`).
- No DB schema changes. No new source files. No new tests.

## Closeout format

```
M12-T009 closeout
  Final review: docs/milestones/m12/final-review.md (PASS — N tasks PASS, M SKIP, 0 FAIL)
  Canonical memory updated:
    - PROJECT_STATE.md: current milestone = M13
    - README.md: bumped
    - docs/milestones/README.md §M12: marked ✓ done
    - docs/milestones/m12/handoff.md: written
  Commits: <N> commits on branch worktree-m12-planning (one per Loop Prompt)
  PR: <gh pr url>
  CI: no-db PASS | live-db PASS | ruff PASS | UI PASS|SKIP
  T007 evidence in PR body: approval comment + submission URL linked
  Acceptance: PASS — link to closing issue + PR
  Risks / blockers: ...
  Next: M13 (evaluation, reliability, regression suite)
```

## Related issues

- Closing issue for M12 — updated with the PR URL; closes on PR
  merge (human-gated).
- The closing PR is the M12 milestone PR; it is also the audit
  trail for T007's real submission.

## Stop condition

Stop after 60 turns. If the final-review skill can't produce a PASS
matrix (any T000–T008 closeout missing), HALT and open follow-up
issues for the missing items; do NOT fake a PASS. If `git push`
fails (e.g. branch protection unexpectedly blocks the worktree
branch), HALT — do NOT force-push. If `gh pr create` fails, HALT
and diagnose; do NOT bypass the PR template.
