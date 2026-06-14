# M11-T000: Discovery / Debate Gate for the M11 CTF architecture

## Milestone
M11: authorized CTF / lab workflow. **`arch:` tagged** — Discovery / Debate
Gate per `docs/milestone-loop-protocol.md` §7 is mandatory before any T001+
implementation work begins.

## Goal
Run the three role-isolated subagents (`legacy-archaeologist`,
`requirements-skeptic`, `design-red-team`) against the proposed M11
architecture — the `ctf_events` / `ctf_challenges` / `ctf_attempts` data
model, the three new approval operations (`challenge_run`, `flag_submit`,
`network_egress`), and the CTFtime → event-credentials → challenge →
solver → flag-submit workflow taxonomy.

T000 is **gate-only**: no code, no schema, no permission edits.
A missing byte-checkable acceptance line is a T000 FAIL and blocks all
downstream M11 work.

## Read first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` §M11
5. `docs/architecture/discovery-debate-gate.md` — verbatim acceptance lines
6. `docs/architecture/design-archaeology.md`
7. `docs/milestone-loop-protocol.md` §7
8. `docs/milestones/m9/handoff.md`
9. `docs/adr/0005-job-taxonomy.md` — `project_kind` enum + `ctf` slug
10. `docs/adr/0006-configurable-approval-gates.md` — operation data shape
11. `supabase/migrations/0001_init.sql` — existing `ctf_scopes` table
12. `.claude/skills/ctf-sandbox/SKILL.md` — current workflow body
13. `src/worker/reviewer.py` — existing reviewer-gate pattern
14. `docs/evidence/m9_4-kkr-replay/` — worked precedent (kkr.py)
15. `.claude/agents/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`

## Scope

1. **Invoke `legacy-archaeologist` first.** Pass it the CTF-related
   artefacts already in the repo: `ctf_scopes` table (migration 0001),
   `.claude/skills/ctf-sandbox/SKILL.md`, `src/worker/reviewer.py` CTF
   mentions, `docs/adr/0005-job-taxonomy.md` `ctf` platform enum,
   any prior CTF references in meeting notes. Produce the 10-section
   report and write it to
   `docs/evidence/m11/discovery/legacy-archaeologist.md`.

2. **Invoke `requirements-skeptic` next.** Pass it the planning Q&A
   decisions (credential model, frozen-bundle + 1 live submission,
   five-category taxonomy with web+crypto exercised, three new ops).
   Produce ≥5 questions across ≥3 categories (scope authorization,
   credential handoff, multi-event identity, flag-submission semantics,
   audit retention) plus an `explicit_unknowns:` section. Write to
   `docs/evidence/m11/discovery/requirements-skeptic.md`.

3. **Invoke `design-red-team` last.** Pass it the proposed data model
   shape (`ctf_events` / `ctf_challenges` / `ctf_attempts`), the three
   new ops, and the two prior reports. Produce ≥3 alternatives for the
   data model and for the approval-op design; name ≥1 dropped capability
   with `file:line` evidence (e.g. dropping per-challenge
   `attempts_per_hour` rate-limit); cover all 4 cost axes; record ≥1
   `open_disagreement`. Write to
   `docs/evidence/m11/discovery/design-red-team.md`.

4. **Verify acceptance lines byte-for-byte.** Compare each report's
   canonical acceptance line against the verbatim text in
   `docs/architecture/discovery-debate-gate.md`. Any mismatch is a
   T000 FAIL.

5. **File or update the closing GitHub issue.** Link the three evidence
   files. Add the `arch:` label. Promote to `decision:confirmed` only
   after the human has read all three reports and signed off.

## Non-goals

- Do not modify `supabase/migrations/`, `.kca/permissions/`,
  `src/worker/`, or `tools/kca/` in this Loop Prompt.
- Do not author migration `0008_m11_ctf.sql` — that's T001.
- Do not write ADRs 0016 / 0017 yet — they land with the implementation
  tasks (T001 / T002) that reference the relevant red-team findings.
- Do not skip an agent because "the answer seems obvious". Each agent
  has a load-bearing acceptance line; skipping = FAIL.

## Acceptance criteria

- All three reports exist under
  `docs/evidence/m11/discovery/{legacy-archaeologist,
  requirements-skeptic,design-red-team}.md`.
- `legacy-archaeologist.md` contains all 10 sections and names ≥5
  behavior dimensions inherited from the existing CTF artefacts.
- `requirements-skeptic.md` contains ≥5 questions across ≥3
  categories and an `explicit_unknowns:` section.
- `design-red-team.md` contains ≥3 alternatives, ≥1 dropped
  capability with `file:line` evidence, all 4 cost axes, and ≥1
  `open_disagreement`.
- Each report's canonical acceptance line matches
  `docs/architecture/discovery-debate-gate.md` byte-for-byte.
- The closing issue is `decision:confirmed` (or this Loop Prompt
  halts and asks the human to confirm).
- No files changed outside `docs/evidence/m11/discovery/` and the
  closing GitHub issue.

## Permissions

- Local file reads (excluding the secret denylist) and Agent tool
  invocations for the three subagents are allowed.
- `git commit` and `git push` require explicit human approval (default
  per protocol §5 — overridden only by the milestone closeout in T009).
- Do not modify any file outside `docs/evidence/m11/discovery/`.

## Closeout format

```
M11-T000 closeout
  legacy-archaeologist: PASS | FAIL — sections present: 10/10; behavior dims: <n>
  requirements-skeptic: PASS | FAIL — questions: <n> across <m> categories; explicit_unknowns: yes/no
  design-red-team: PASS | FAIL — alternatives: <n>; dropped capabilities: <n>; cost axes: 4/4; open_disagreements: <n>
  Acceptance lines (byte-checkable): 3/3 match | <n>/3 match — list mismatches
  Closing issue: <url> — decision:confirmed | decision:needed
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T001 ready to start
```

## Related issues

- M11 proposal issue (TBD) — collects the planning Q&A decisions
  (credential model, frozen+live regression target, category exercise
  scope, three new approval ops). This task closes the Discovery /
  Debate Gate bullet on that issue.

## Stop condition

Stop after 80 turns. If any subagent report fails its canonical
acceptance line, halt and ask the human — do **not** fudge the report
to make it pass. If `legacy-archaeologist` surfaces a load-bearing
requirement that invalidates the planned data model (e.g.
multi-event identity collision), halt and propose a new ADR draft
under `docs/adr/` before re-running T000.
