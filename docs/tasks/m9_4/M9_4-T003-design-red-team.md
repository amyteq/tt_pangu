# M9.4-T003: `design-red-team` agent scaffold

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Create `.claude/agents/design-red-team.md` — an agent that refutes a
proposed design. Given a task spec, ADR draft, or planning doc plus the
outputs of `requirements-skeptic` and `legacy-archaeologist`, the agent
must produce ≥3 alternative designs, surface capabilities the proposed
design would drop, and argue long-term costs. The agent does not
ratify designs and does not edit code.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 做法 3 (`design-red-team`).

## Read first

1. `docs/meeting-notes/2026-05-24-r3.md` §6
2. `docs/milestones/m9_4/loop-prompts.md` §"M9.4 at a glance"
3. `docs/tasks/m9_4/M9_4-T001-requirements-skeptic.md`
4. `docs/tasks/m9_4/M9_4-T002-legacy-archaeologist.md`
5. `docs/engineering-practice.md` — review-role precedent
6. `.claude/agents/reviewer.md` — skeptical, evidence-grounded precedent
7. `docs/adr/` — any existing ADR with an explicit
   "alternatives considered" section (front-matter precedent)

## Scope

1. Create `.claude/agents/design-red-team.md` with YAML front-matter:
   - `name: design-red-team`
   - `description:` proactive trigger before architecture / migration
     designs are accepted.
   - `tools: Read, Glob, Grep` — read-only. (No `Bash`. No `WebFetch`
     unless a later task explicitly adds it.)
   - `model: sonnet`.
   - `permissionMode: plan`.
   - No `skills:` line.
2. Body must define the four mandatory output sections:
   1. `alternatives:` — ≥3 alternative designs. Each entry: name,
      one-paragraph sketch, key tradeoff vs the proposed design.
   2. `dropped_capabilities:` — features / behaviors the proposed
      design would lose vs the legacy or vs the alternatives. Each
      entry MUST cite `file:line` evidence (per `CLAUDE.md` "Tone and
      style" — `file_path:line_number` pattern).
   3. `long_term_costs:` — cognitive load, ops burden, extensibility,
      blast radius. One sentence per axis minimum.
   4. `open_disagreements:` — explicit list of points where the
      red-team disagrees with the proposed design; each item ends
      with an actionable next step (more research, write a spike,
      ask human, defer to a follow-up issue).
3. Body must list Must NOT rules:
   - Do not sign off on a design ("the agent does not ratify, only
     refutes").
   - Do not modify code.
   - Do not file GitHub issues / PRs / comments.
   - Do not claim authority over the final decision — that belongs to
     the human.
4. Body must contain the checkable acceptance line: "Output MUST
   include ≥3 alternatives, ≥1 dropped capability with file:line
   evidence, all four long-term-cost axes, and ≥1 actionable
   open_disagreements entry."

## Non-goals

- Do not implement the orchestration skill (T004).
- Do not produce a sample red-team run yet (T005).

## Acceptance criteria

- `.claude/agents/design-red-team.md` exists, front-matter parses.
- All 4 mandatory output sections are listed verbatim in the body.
- All 4 Must NOT rules are listed verbatim.
- The acceptance line ("≥3 alternatives, ≥1 dropped capability with
  file:line, all four cost axes, ≥1 actionable open_disagreements")
  is present verbatim.
- No other file is touched in T003.

## Permissions

- Local file writes restricted to `.claude/agents/design-red-team.md`.
- No DB, no Kaggle, no network calls.
- `git commit` / `git push` deferred to milestone closeout (T006).

## Closeout format

```
M9.4-T003 closeout
  File created: .claude/agents/design-red-team.md (sha=…, bytes=…)
  YAML front-matter parses: YES | NO
  Mandatory output sections (4/4): YES | NO
  Mandatory Must-NOT rules (4/4): YES | NO
  Acceptance line present verbatim: YES | NO
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: M9.4-T004 ready
```

## Stop condition

Stop after 50 turns. If a contradictory expectation surfaces between
this spec and the meeting note (e.g. a future revision says
`design-red-team` should also approve designs), halt and ask — do
not silently widen the agent's authority.
