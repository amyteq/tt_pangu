# M11-T009: M11 exit criteria + final review + handoff + PR

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Validate the M11 exit-criteria matrix; write `docs/milestones/m11/final-review.md`
via the `milestone-final-review` skill; write
`docs/architecture/m11-ctf-workflow.md` if not already authored; update
`PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md` §M11 to `✓ done`;
write `docs/milestones/m11/handoff.md`; run `worktree-milestone-pr` to
commit per Loop Prompt, push the worktree branch, and open the M11 PR
against `main`.

## Read first

1. All M11 closeouts (T000–T008)
2. `docs/milestones/m9/final-review.md` — layout precedent (30-check matrix)
3. `docs/milestones/m10/final-review.md` (when it lands) — closest CTF-style
   layout match
4. `docs/milestones/m8_5/final-review.md` — layout precedent (compact)
5. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template
6. `docs/milestones/m9/handoff.md`, `m10-handoff.md` (when it lands) —
   precedent
7. `milestone-final-review` skill body
8. `worktree-milestone-pr` skill body
9. `docs/milestones/README.md` §M11 — exit criteria text

## Scope

1. **Run the validation matrix.** Mirror the M9 / M10 validation matrix
   structure. Each row reports PASS / FAIL / SKIP with the linking
   closeout or evidence path. The matrix MUST cover:

   - All three Discovery / Debate Gate reports exist with byte-
     checkable acceptance lines (T000).
   - Migration `0008_m11_ctf.sql` applied; four `ctf_*` tables present
     (T001).
   - `src/db/ctf.py` helpers callable; ADR-0016 present (T001).
   - Three new approval ops in all three permission profiles;
     reviewer-gate fires (T002).
   - `kca ctf` CLI surface covers all five sub-namespaces (T003).
   - Frozen past-event bundle (1 web + 1 crypto) under `data/ctf/`;
     licensing documented (T004).
   - Two `ctf_attempts` rows with `accepted=true` for the local solve
     (T005).
   - Reviewer-gate round-trip recorded for `challenge_run` +
     `flag_submit` (T006).
   - Refusal smoke: `kaggle.com` from CTF context recorded as
     `agent_reviews.verdict=reject` (T006).
   - ONE real flag submission with `ctf_attempts` row recorded (T007).
   - `tests/test_m11_e2e.py` 5/5 PASS; `tests/test_m11_smoke.py`
     PASS under DB (T008).
   - Full test suite 0 failures; ruff clean (T008).
   - `docs/architecture/m11-ctf-workflow.md` present.
   - ADRs 0016 + 0017 present.

2. **Write `docs/milestones/m11/final-review.md`.** Invoke the
   `milestone-final-review` skill against the validation matrix. The
   skill emits the canonical layout (header, scope reminder, validation
   matrix, follow-ups, sign-off). Verify the document does NOT contain
   any flag value, credential value, or `~/.ctf/*` path content.

3. **Write `docs/architecture/m11-ctf-workflow.md`** if T000 / T001
   did not already draft it. Required sections:
   - CTFtime calendar discovery → event registration (human action)
   - Credential file shape + load path
   - Challenge inventory + category triage
   - Solver execution under `challenge_run` gate
   - Flag recovery + verification (sha256)
   - Flag submission under `flag_submit` gate
   - Out-of-scope follow-ups (pwn / rev / forensics solve loops;
     calendar auto-watch; multi-event identity rotation)

4. **Update canonical memory.**
   - `PROJECT_STATE.md` — current milestone → "M11 ✓ done; entering
     M12 / M13 (TBD)"; open decisions; known blockers carried.
   - `README.md` — current milestone section.
   - `docs/milestones/README.md` §M11 — mark `✓ done`; one-line landed
     summary mirroring M9 / M10 entries; follow-ups list.

5. **Write `docs/milestones/m11/handoff.md`** per
   `docs/milestones/_templates/handoff-prompt.md` template, populated from the M11 final
   review. Sections: Context / Read these files first / State at
   M11 exit / Cross-cutting follow-ups / Rules / Current task.

6. **Run `worktree-milestone-pr`** skill:
   - `git add` the files named in each Loop Prompt's closeout.
   - `git commit` one commit per Loop Prompt (T000–T009 = 10 commits)
     OR one squash commit per milestone (the protocol default is
     "one commit per Loop Prompt"; keep that unless the human says
     otherwise).
   - `git push` the worktree's branch (`worktree-m11-planning` or
     whatever name the worktree carries) to `origin`.
   - `gh pr create --base main --title "M11: authorized CTF / lab
     workflow (X PASS / Y SKIP / 0 FAIL)" --body @docs/m11-final-
     review.md --label "type:feature" --label "area:ctf"`.
   - Do NOT merge the PR. Do NOT push to `main` directly. Do NOT
     `--force` push.

## Non-goals

- Do not exercise any new external API call beyond what's already in
  the closeouts.
- Do not re-run T007 (the single live submission).
- Do not edit closed task spec files retroactively.
- Do not merge the M11 PR — that's the human's call.

## Acceptance criteria

- `docs/milestones/m11/final-review.md` exists, contains the validation matrix,
  and reports total PASS / SKIP / FAIL counts.
- `docs/architecture/m11-ctf-workflow.md` exists with all seven
  required sections.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md` updated.
- `docs/milestones/m11/handoff.md` exists with all six template
  sections populated from M11 evidence.
- The worktree branch is pushed to `origin`; `gh pr view` returns
  the open M11 PR.
- The PR body is the M11 final review.
- No flag value / credential value / `~/.ctf/*` content appears in
  any of the new docs, the PR body, or the PR description.
- All test suites still pass: pytest 0 failures, ruff clean.

## Permissions

- Local file writes under `docs/`, `PROJECT_STATE.md`, `README.md`.
- `git add` / `git commit` / `git push` of the worktree branch (NOT
  to `main`).
- `gh pr create` (NOT `gh pr merge`).
- No external API calls.

## Closeout format

```
M11-T009 closeout
  Validation matrix: <n> PASS / <m> SKIP / <k> FAIL
  docs/milestones/m11/final-review.md: written
  docs/architecture/m11-ctf-workflow.md: written (sections: 7/7)
  PROJECT_STATE.md / README.md / docs/milestones/README.md: updated
  docs/milestones/m11/handoff.md: written
  Worktree branch: <name> pushed to origin
  PR: <url>
  Audit-grep across all new files: 0 flag/credential leaks
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M12 / M13 planning (or M11 follow-up issues, depending on
  Q&A with the human at handoff)
```

## Related issues

- M11 proposal issue (TBD). M11-T009 closes the milestone by linking
  every numbered task's closing issue + the final review PR.

## Stop condition

Stop after 60 turns. If the validation matrix has any FAIL row, do
NOT write the final review with `✓ done` status — open the failing
task's closing issue, mark `ai:blocked`, and HALT. If
`worktree-milestone-pr` fails to push (network / auth), retry once,
then HALT and ask. Do NOT bypass the `gh pr create` step by editing
the remote branch directly.
