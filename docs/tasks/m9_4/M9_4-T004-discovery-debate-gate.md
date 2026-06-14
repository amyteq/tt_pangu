# M9.4-T004: `design-archaeology` skill + protocol §7 "Discovery / Debate Gate"

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Wire the three new agents (`requirements-skeptic`,
`legacy-archaeologist`, `design-red-team`) into a single orchestration
skill and an additive section of the milestone-loop-protocol so any
future architecture-shaped or legacy-migration-shaped task can invoke
the gate by reference rather than reinventing the workflow.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 做法 1 (skill) + 做法 4
(acceptance criteria).

## Read first

1. `docs/tasks/m9_4/M9_4-T001-requirements-skeptic.md`
2. `docs/tasks/m9_4/M9_4-T002-legacy-archaeologist.md`
3. `docs/tasks/m9_4/M9_4-T003-design-red-team.md`
4. `.claude/skills/` — front-matter precedent (`milestone-final-review`,
   `worktree-milestone-pr`, `kaggle-experiment-loop`)
5. `docs/milestone-loop-protocol.md` — current §1–§6
6. `docs/meeting-notes/2026-05-24-r3.md` §6 做法 1 + 做法 4

## Scope

1. Create `.claude/skills/design-archaeology/SKILL.md`:
   - YAML front-matter with `name: design-archaeology`,
     `description:` matching the trigger phrasing in
     `docs/milestones/m9_4/loop-prompts.md` ("before implementation on
     architecture or legacy-migration tasks"), and a `phase: planning`
     hint (no runtime side effects).
   - Body documents the three-stage orchestration order:
     1. `legacy-archaeologist` — read the legacy artefact, produce
        the 10-section report.
     2. `requirements-skeptic` — read the report, produce the
        ≥5-question challenge list across ≥3 categories.
     3. `design-red-team` — read the proposed design + both prior
        outputs, produce ≥3 alternatives and the dropped-capability /
        long-term-cost analysis.
   - Body declares which outputs the parent session must collect
     before any implementation work begins.
   - Skill is invocation-only (no shell commands). It is read by the
     parent session, not executed.
2. Create `docs/architecture/discovery-debate-gate.md`:
   - Canonical "acceptance criteria template" task specs can include
     by reference (e.g. "this task adopts
     docs/architecture/discovery-debate-gate.md acceptance template").
   - Lists the union of the three agents' acceptance lines so a parent
     session can verify all three were exercised.
   - Documents the `arch:` / `legacy-migration:` task tag convention.
3. Append §7 "Discovery / Debate Gate" to
   `docs/milestone-loop-protocol.md`. **Additive only.** Must NOT
   modify §1–§6. §7 explains:
   - When the gate is mandatory (tasks tagged `arch:` or
     `legacy-migration:` in their `## Milestone` or first heading).
   - How the gate's outputs are attached to the task closeout
     (paths under `docs/evidence/<milestone>/<task>/discovery/`).
   - That hook-based enforcement is out of scope for M9.4 and a
     follow-up issue.

## Non-goals

- Do not edit the existing six sections of the protocol.
- Do not implement a hook-level enforcement (deferred follow-up).
- Do not modify any existing skill under `.claude/skills/`.
- Do not run the gate yet — demonstration is T005.

## Acceptance criteria

- `.claude/skills/design-archaeology/SKILL.md` exists; YAML
  front-matter parses.
- `docs/architecture/discovery-debate-gate.md` exists and contains:
  - the union of the three agents' acceptance lines verbatim;
  - the `arch:` / `legacy-migration:` tag convention;
  - the closeout-evidence path convention.
- `docs/milestone-loop-protocol.md` ends with a new §7 section whose
  heading is exactly `## 7. Discovery / Debate Gate`.
- The protocol's §1–§6 are byte-identical to the pre-T004 version
  (verify with `git diff` showing only an additive tail).
- No other file is touched in T004.

## Permissions

- Local writes restricted to the three files named above.
- No DB, no Kaggle, no network.
- `git commit` / `git push` deferred to milestone closeout (T006).

## Closeout format

```
M9.4-T004 closeout
  Files created/modified:
    .claude/skills/design-archaeology/SKILL.md (new, sha=…)
    docs/architecture/discovery-debate-gate.md (new, sha=…)
    docs/milestone-loop-protocol.md (additive §7 only)
  Skill YAML parses: YES | NO
  Protocol §1–§6 unchanged: YES | NO (diff range proves it)
  §7 heading matches verbatim: YES | NO
  Three-stage orchestration documented: YES | NO
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: M9.4-T005 ready
```

## Stop condition

Stop after 60 turns. If the protocol's §1–§6 cannot be preserved
byte-for-byte (e.g. an unrelated change is mid-flight on the
worktree), halt and ask — do not absorb someone else's edits.
