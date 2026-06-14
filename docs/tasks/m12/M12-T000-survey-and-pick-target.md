# M12-T000: Hackathon candidate survey + human pick

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Produce a small, evidence-backed shortlist of 2–3 candidate hackathon
events (Devpost-first; Devpost-equivalent platforms acceptable as
fall-backs) and stage the human pick. No DB writes. No `tools/kca/devpost.py`
authoring (that's T003). No submission attempts.

T000 unblocks T001 (Discovery / Debate Gate) and T002 (schema). The
picked slug feeds every later task.

## Read first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` §M12
5. `docs/engineering-practice.md`
6. `docs/milestones/m12/loop-prompts.md` §"M12 at a glance"
7. `docs/milestones/m9/handoff.md`
8. `tools/kca/research_fetch.py` — READ_ONLY HTTP + readability pattern (template only; do NOT add devpost code here)
9. `docs/adr/0006-configurable-approval-gates.md` — to flag any candidate that needs gates we don't have
10. `env.example` — note current env var names; do not edit

## Scope

1. Survey current Devpost (or Devpost-equivalent) hackathons via
   READ_ONLY HTTP / web research. Acceptable sources: the Devpost
   public hackathon directory, official platform announcements,
   organiser blogs. **Do not** read or echo any credential, session
   cookie, or DM URL.
2. Pick 2–3 candidates that satisfy ALL of the following:
   - Public event page reachable without login.
   - Submission deadline ≥ 14 days from today (so T001–T007 have
     headroom).
   - Rules permit AI-assisted entries (read the rules page; cite
     the URL in the candidate entry).
   - No cash prize OR prize policy is compatible with an AI-assisted
     entry (no "human-only" clause).
   - Submission format is documented (so M12-T002's
     `competitions.submission_format` jsonb has real data to populate).
3. Write `docs/evidence/m12/t000-candidates.md` with one section per
   candidate. Each section MUST contain:
   - Title + slug + canonical URL.
   - Deadline (UTC) + days until deadline.
   - Scope (theme, eligible technologies, team size limits).
   - Prize policy (cash, swag, judging-only).
   - Submission format (README? demo video? GitHub repo? Devpost
     submission form fields? Anything else.).
   - Why this is safe for an AI-assisted regression (one short
     paragraph; cite the rules URL).
   - Risk notes (anything that would block T007).
4. Add a one-paragraph "Recommendation" at the top of the evidence
   file naming which candidate the agent thinks is the best fit, but
   make it explicit that the human picks.
5. Post a single comment on the closing GitHub issue with the
   candidate list (links + 1-line summary each). Do NOT post the
   recommendation paragraph in the issue comment; the issue is for
   the human to decide.
6. When the human replies with a pick, edit the closing issue body
   to add a "Picked slug: `<slug>`" line. The closeout closes when
   this line exists.

## Non-goals

- Do NOT register the picked hackathon in the `competitions` table.
  That's M12-T002 (after migration 0009 lands).
- Do NOT add `tools/kca/devpost.py` or any new `kca` subcommand. That's
  M12-T003.
- Do NOT begin authoring an idea / prototype. That's M12-T006.
- Do NOT attempt to log in to Devpost, view any draft submission, or
  exercise any write path.
- Do NOT enumerate every Devpost hackathon — 2–3 candidates is the
  whole job.
- Do NOT change `.claude/settings.json` or any hook.

## Acceptance criteria

- `docs/evidence/m12/t000-candidates.md` exists; lists 2–3 candidates;
  each candidate has all required fields filled.
- The "Recommendation" paragraph is present and names one candidate.
- A comment on the closing GitHub issue links each candidate's URL
  and gives a one-line summary; the recommendation is NOT in this
  comment.
- The closing issue body contains a `Picked slug: <slug>` line
  agreed by the human (this gate may be deferred — the closeout may
  record "awaiting human pick" if T000 is run autonomously and the
  human is not online; T001 simply blocks until the line lands).
- No new files outside `docs/evidence/m12/`. No DB writes. No PR
  open yet (T009 closes the milestone PR).
- `python -m pytest tests/ -q` still passes (no code changes).

## Tag

`research:` (not `arch:` — T000 is READ_ONLY and produces no design
decisions).

## Permissions

- `WebFetch` / `Read` / `Glob` / `Grep` allowed. No `Edit` outside
  `docs/evidence/m12/`. No `Bash` calls that hit `devpost.com` write
  endpoints.
- `gh issue comment` + `gh issue edit` for the closing issue are
  allowed per the dev-phase non-destructive GitHub carve-out (memory:
  `feedback_permissive_github_dev_phase`).
- No `kca` write subcommands. No DB connection needed.

## Closeout format

```
M12-T000 closeout
  Candidates surveyed: <N> (2 or 3)
  Evidence file: docs/evidence/m12/t000-candidates.md
  Issue comment: <permalink>
  Recommendation: <slug> (for human reference only)
  Picked slug: <slug-from-issue-body> | awaiting human pick
  Acceptance: PASS | DEFERRED (awaiting human pick) | FAIL
  Risks / blockers: ...
  Next: M12-T001 blocked until `Picked slug:` line is present
```

## Related issues

- Closing issue for M12 — links to this task spec; records the four
  human decisions from the M12 plan conversation; gets `decision:confirmed`
  + `ai:ready` after the human pick is recorded.
- Memory pointer: `reference_supabase_db.md` for the DSN if the
  agent needs to read `competitions` to confirm no conflicting slug
  is already registered (READ_ONLY check is fine; do NOT insert).

## Stop condition

Stop after 60 turns. If no Devpost candidate satisfies all five
criteria in scope step 2, broaden to one Devpost-equivalent platform
(HackerEarth, MLH, Devfolio) and document the substitution in the
evidence file. If still no candidate, halt and ask — do NOT pick an
event with ambiguous rules or a same-week deadline.
