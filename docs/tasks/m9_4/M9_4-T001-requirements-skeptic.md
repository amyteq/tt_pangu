# M9.4-T001: `requirements-skeptic` agent scaffold

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Create `.claude/agents/requirements-skeptic.md` — a question-only agent
that surfaces hidden requirements before implementation begins on
architecture-shaped or legacy-migration-shaped tasks. The agent does
not write code, does not edit files, does not infer decisions. Its
output is a structured question list whose shape is checkable by the
parent session.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 做法 3 + 做法 4.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/meeting-notes/2026-05-24-r3.md` §6 (做法 3 + 做法 4)
3. `docs/milestones/m9_4/loop-prompts.md` §"M9.4 at a glance"
4. `.claude/agents/researcher.md` — front-matter / read-only precedent
5. `.claude/agents/reviewer.md` — skeptical-role precedent
6. `.claude/agents/milestone-reviewer.md` — explicit "Must NOT" rules

## Scope

1. Create `.claude/agents/requirements-skeptic.md` with YAML front-matter:
   - `name: requirements-skeptic`
   - `description:` one-line trigger description (proactively before
     architecture / legacy-migration tasks).
   - `tools: Read, Glob, Grep` — read-only.
   - `model: sonnet` (cheaper than Opus; questions don't need top tier).
   - `permissionMode: plan` — refuses any non-plan tool use.
   - No `skills:` line; the orchestration skill (`design-archaeology`)
     comes in T004 and references the agent, not the other way round.
2. Body must specify:
   - What the agent does (asks sharp questions before implementation).
   - What the agent must NOT do (write code, edit files, run shell,
     propose final implementations, claim authority over decisions).
   - Output schema: numbered question list grouped by category. At
     minimum these categories must be present: `hidden_constraints`,
     `personas_and_accounts`, `side_effects`, `edge_cases`, `rollback`.
   - Checkable acceptance line (verbatim in the agent body): "Output
     MUST contain ≥5 questions spread across ≥3 categories, and an
     `explicit_unknowns:` section listing things the agent could not
     answer without human input."
3. Add a one-line entry to the agent's `description:` so it surfaces in
   the parent's agent picker for the right tasks (the trigger phrase
   "before implementation on architecture or legacy-migration tasks"
   is mandatory).

## Non-goals

- Do not implement the orchestration skill. That is T004.
- Do not modify `competition-researcher` / `evidence-reviewer` /
  `milestone-reviewer`. M9.4 is additive.
- Do not add new permission profiles, hook entries, or settings.
- Do not produce a sample run yet — the demonstration replay is T005.

## Acceptance criteria

- `.claude/agents/requirements-skeptic.md` exists with the front-matter
  fields above (parsed as YAML without errors).
- The body lists the five mandatory categories verbatim.
- The body lists the four Must NOT rules verbatim.
- The body contains the "≥5 questions across ≥3 categories + explicit
  unknowns" acceptance line, exact wording.
- `python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.claude/agents/requirements-skeptic.md').read_text().split('---',2)[1])"` exits 0.
- No other file is touched in T001.

## Permissions

- Local file writes restricted to `.claude/agents/requirements-skeptic.md`.
- No DB, no Kaggle, no network calls.
- `git commit` / `git push` deferred to milestone closeout (T006).

## Closeout format

```
M9.4-T001 closeout
  File created: .claude/agents/requirements-skeptic.md (sha=…, bytes=…)
  YAML front-matter parses: YES | NO
  Mandatory categories present: hidden_constraints, personas_and_accounts, side_effects, edge_cases, rollback — YES | NO
  Mandatory Must-NOT rules present (4/4): YES | NO
  Acceptance line present verbatim: YES | NO
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: M9.4-T002 ready
```

## Stop condition

Stop after 50 turns. If the front-matter pattern conflicts with an
existing agent (name collision), halt and ask — do not rename existing
agents silently.
