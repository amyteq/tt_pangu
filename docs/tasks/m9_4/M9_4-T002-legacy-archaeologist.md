# M9.4-T002: `legacy-archaeologist` agent scaffold

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Create `.claude/agents/legacy-archaeologist.md` — a read-only agent that
extracts hidden design intent from legacy code, configs, READMEs, and
notebooks before they are migrated or replaced. The kkr.py / kkr.yaml
migration is the canonical case where this role was missing: the
multi-Kaggle-account / owner / env-mapping semantics were not
discovered until after the platform tools were designed.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 做法 1 (design-archaeology
content) + 做法 3 (agent role).

## Read first

1. `docs/meeting-notes/2026-05-24-r3.md` §6 (做法 1 + 做法 3)
2. `docs/milestones/m9_4/loop-prompts.md` §"M9.4 at a glance"
3. `docs/tasks/m9_4/M9_4-T001-requirements-skeptic.md` — companion agent shape
4. `tools/legacy/kkr.py`, `tools/legacy/kkr.yaml` — the fixture this
   agent must be able to crack
5. `docs/tasks/m1/M1-T000-legacy-tool-inventory.md` — legacy-inventory precedent
6. `.claude/agents/researcher.md` — read-only / source-focused precedent

## Scope

1. Create `.claude/agents/legacy-archaeologist.md` with YAML front-matter:
   - `name: legacy-archaeologist`
   - `description:` proactive trigger for legacy-migration tasks.
   - `tools: Read, Glob, Grep` — no shell, no write tools.
   - `model: sonnet`.
   - `permissionMode: plan`.
   - No `skills:` line.
2. Body must specify the 10 mandatory output sections (the §6 做法 1
   checklist verbatim):
   1. Workflows the legacy tool supports.
   2. Hidden assumptions.
   3. User personas / owner accounts / env mappings (the kkr.py case).
   4. Side effects (Kaggle pushes, file writes, registry mutations).
   5. State files / registries / dotenv overrides.
   6. Config dimensions (`--env`, `--owner`, `--slug`, version labels…).
   7. Features to preserve.
   8. Features to deprecate (with reason).
   9. Questions that MUST be asked before implementation (handed off to
      `requirements-skeptic`).
   10. Tests / fixtures that would prove behavior parity.
3. Body must list Must NOT rules:
   - Do not execute the legacy code (no `python kkr.py …`, no
     `kaggle …`, no shell).
   - Do not modify any legacy file.
   - Do not fetch external dependencies.
   - Do not infer decisions from ambiguity — the agent surfaces
     questions, never conclusions.
4. Body must contain the checkable acceptance line: "Output MUST cover
   all 10 sections; ≥5 distinct legacy behavior dimensions must be
   named explicitly, including any multi-account / owner / env
   mapping the legacy artefact encodes."

## Non-goals

- Do not run the agent yet. Demonstration replay is T005.
- Do not modify the legacy artefacts under `tools/legacy/`.
- Do not write the orchestration skill (T004).

## Acceptance criteria

- `.claude/agents/legacy-archaeologist.md` exists, front-matter parses.
- All 10 mandatory output sections are listed verbatim in the body.
- All 4 Must NOT rules are listed verbatim.
- The "≥5 dimensions + multi-account/owner/env explicitly named"
  acceptance line is present.
- No other file is touched in T002.

## Permissions

- Local file writes restricted to `.claude/agents/legacy-archaeologist.md`.
- No DB, no Kaggle, no network calls.
- `git commit` / `git push` deferred to milestone closeout (T006).

## Closeout format

```
M9.4-T002 closeout
  File created: .claude/agents/legacy-archaeologist.md (sha=…, bytes=…)
  YAML front-matter parses: YES | NO
  Mandatory sections (10/10): YES | NO
  Mandatory Must-NOT rules (4/4): YES | NO
  Acceptance line present verbatim: YES | NO
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: M9.4-T003 ready
```

## Stop condition

Stop after 50 turns. If the kkr.py / kkr.yaml fixture is missing or
moved, halt and ask — do not invent a different fixture.
