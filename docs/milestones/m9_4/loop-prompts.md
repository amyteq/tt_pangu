# M9.4 — Loop Prompts

_Discovery / Debate Gate agents: `requirements-skeptic`, `legacy-archaeologist`, `design-red-team`._
_Scope: scaffold the three contrarian agents, the backing `design-archaeology` skill, and the
acceptance-criteria hooks that make "be more proactive in plan/design/architect mode"
checkable rather than vibe-based._
_Background: `docs/meeting-notes/2026-05-24-r3.md` §6 (做法 1–4) — observation that
Claude Code missed multi-Kaggle-account semantics during `kkr.py` / `kkr.yaml`
migration because no agent role was responsible for asking._
_Prerequisite: M9 exit confirmed (`docs/milestones/m9/final-review.md` PASS). M9.4 runs in
parallel with M10; it does NOT depend on M10, and M10 does NOT depend on M9.4._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md`
(sequencing, secret denylist, sandbox/DB DSN, **per-milestone worktree by default**)._

---

## M9.4 at a glance

M9.4 closes the gap surfaced in the 2026-05-24 R3 meeting:

> 发现 Claude Code 有时执行任务时不够主动积极, 比如之前让其接手 legacy 的 kkr.py,
> kkr.yaml, 开始设计 build KCA 平台的 tool 时, agent 并没有询问原先设计中的一些理念,
> 比如多 Kaggle 账户提交。

The fix, per §6 of that note, is **not** "remind Claude to be more proactive."
It is **three role-isolated agents plus an acceptance gate** so proactivity
becomes a checkable artifact:

- `requirements-skeptic` — asks questions; never proposes implementation.
- `legacy-archaeologist` — reads legacy code/config; surfaces hidden design
  intent, multi-account / owner / env dimensions, side effects, registries.
- `design-red-team` — refutes the current proposed design; produces at least
  three alternatives and argues tradeoffs.

The three are wired together by a new `.claude/skills/design-archaeology/SKILL.md`
that the milestone-loop-protocol invokes **before** any implementation work
begins on an architecture-shaped or legacy-migration-shaped task.

M9.4 is **planning + scaffolding**, not a feature-shipping milestone:

- New files land under `.claude/agents/`, `.claude/skills/`, `docs/architecture/`,
  `docs/tasks/`, and the milestone-loop-protocol gets one additive section.
- No `src/`, `tools/kca/`, `ui/`, `services/`, `supabase/migrations/` changes.
- No real Kaggle calls. No DB schema changes. No new permission policies.
- Validate by **dry-run replay** on `tools/legacy/kkr.py` + `tools/legacy/kkr.yaml`:
  the three agents must collectively recover the multi-account / owner / env
  semantics that were missed during the original migration.

### Entry gates

Direct entry into M9.4 is blocked until **all** are true:

- M9 is merged on `main` (`docs/milestones/m9/final-review.md` exists and reports PASS).
- The closing issue for M9.4 (TBD; analogous to issue #12 for M10) has
  `decision:confirmed` + `ai:ready`.
- `tools/legacy/kkr.py` and `tools/legacy/kkr.yaml` are reachable from the
  repo root — M9.4 uses them as the demonstration fixture.

### What's in scope

| Capability | Owned by | M9.4 touches |
|---|---|---|
| Question-only agent | `.claude/agents/requirements-skeptic.md` (new) | T001 |
| Legacy-reader agent | `.claude/agents/legacy-archaeologist.md` (new) | T002 |
| Refutation agent | `.claude/agents/design-red-team.md` (new) | T003 |
| Orchestration skill | `.claude/skills/design-archaeology/SKILL.md` (new) | T004 |
| Workflow hook | `docs/milestone-loop-protocol.md` — additive §7 "Discovery / Debate Gate" | T004 |
| Acceptance template | `docs/architecture/discovery-debate-gate.md` (new) — checkable AC list | T001 / T002 / T003 / T004 |
| Demonstration fixture | `docs/evidence/m9_4-kkr-replay/` — three agent transcripts replaying `kkr.py` migration | T005 |
| Smoke tests | `tests/test_m9_4_agents.py` — agent files parse, skill loader resolves, acceptance checks present | T005 |
| Final review | `milestone-final-review` skill | T006 |

### What's NOT in scope

- Building a runtime version of these agents inside `src/worker/`. M9.4 lives
  entirely in Claude Code's `.claude/` agent/skill surface. The runtime
  equivalent is a follow-up issue (separate milestone).
- Changing the existing `competition-researcher` / `evidence-reviewer` /
  `milestone-reviewer` agents. The three new agents are additive and
  role-isolated. Cross-references between them must be one-way and
  explicit.
- Adding new tools, permission policies, or DB rows for these agents.
  They use existing `Read`, `Glob`, `Grep`, `WebFetch` (where applicable)
  and produce markdown output only.
- Auto-blocking implementation work via hook code. M9.4 enforces the
  Discovery / Debate Gate via **acceptance criteria** in task specs and
  the milestone-loop-protocol, not via a tool-level deny. Hook-based
  enforcement is a follow-up.
- Running the gate on every task. The gate is mandatory only for tasks
  the milestone explicitly tags as `arch:` or `legacy-migration:` in the
  task spec; routine task specs continue to use the existing protocol.

DB / sandbox details: M9.4 does not touch the DB. Sandbox bypass is **not**
required for M9.4 Loop Prompts unless the closeout step needs `git push` /
`gh pr create`; that follows the milestone-loop-protocol §5 default.

---

## M9.4 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M9.4-T001 | Design + scaffold `requirements-skeptic` agent (question-only, no code, no edits) | Prompt 1 |
| M9.4-T002 | Design + scaffold `legacy-archaeologist` agent (read legacy artefacts; surface hidden design intent) | Prompt 2 |
| M9.4-T003 | Design + scaffold `design-red-team` agent (≥3 alternative designs; refute proposed approach) | Prompt 3 |
| M9.4-T004 | Wire the three agents into a `design-archaeology` skill + milestone-loop-protocol §7 "Discovery / Debate Gate" | Prompt 4 |
| M9.4-T005 | Replay the `kkr.py` / `kkr.yaml` migration through the gate as a demonstration; smoke tests | Prompt 5 |
| M9.4-T006 | M9.4 exit criteria validation + `docs/milestones/m9_4/final-review.md` | Prompt 6 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m9_4/M9_4-T00N-*.md` spec.

---

## Loop Prompt 1 — M9.4-T001 `requirements-skeptic` agent

```
/goal Execute M9.4-T001 requirements-skeptic agent scaffold until acceptance criteria pass or stop after 50 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T001-requirements-skeptic.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md
- docs/milestones/README.md (no §M9.4 yet — this milestone lives in m9_4-loop-prompts.md)
- docs/meeting-notes/2026-05-24-r3.md §6 (做法 3 + 做法 4)
- .claude/agents/researcher.md (front-matter / scope precedent)
- .claude/agents/reviewer.md (skeptical-role precedent)
- .claude/agents/milestone-reviewer.md (Must NOT rules precedent)

Mission (full version in task spec):
Create .claude/agents/requirements-skeptic.md. The agent's job is to ask
sharp questions before implementation begins on architecture-shaped or
legacy-migration-shaped tasks. It must NOT write code, edit files, or run
shell commands. Output is a numbered question list grouped by category
(hidden constraints, personas, side effects, edge cases, rollback) plus
explicit unknowns. The agent definition must declare a checkable
acceptance criterion (e.g. "≥5 questions across ≥3 categories") so a
parent session can verify the agent did its job.
```

---

## Loop Prompt 2 — M9.4-T002 `legacy-archaeologist` agent

```
/goal Execute M9.4-T002 legacy-archaeologist agent scaffold until acceptance criteria pass or stop after 50 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T002-legacy-archaeologist.md

Read also (background context):
- M9.4-T001 closeout
- docs/meeting-notes/2026-05-24-r3.md §6 (做法 1 design-archaeology skill + 做法 3 agent)
- tools/legacy/kkr.py + tools/legacy/kkr.yaml (the demonstration fixture)
- docs/tasks/m1/M1-T000-legacy-tool-inventory.md (legacy-inventory precedent)
- .claude/agents/researcher.md (read-only / source-focused precedent)

Mission (full version in task spec):
Create .claude/agents/legacy-archaeologist.md. The agent reads legacy
scripts, configs, READMEs, and notebooks and produces a structured report:
workflows supported, hidden assumptions, user personas / owner accounts /
env mappings, side effects, state files / registries, config dimensions,
features to preserve, features to deprecate, and questions that MUST be
asked before implementation. The agent must NOT execute the legacy code,
modify any legacy file, fetch external dependencies, or infer decisions
from ambiguity (it raises questions, not conclusions). Acceptance
criterion: ≥5 distinct legacy behavior dimensions surfaced on the
kkr.py / kkr.yaml fixture, including multi-account / owner / env mapping.
```

---

## Loop Prompt 3 — M9.4-T003 `design-red-team` agent

```
/goal Execute M9.4-T003 design-red-team agent scaffold until acceptance criteria pass or stop after 50 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T003-design-red-team.md

Read also (background context):
- M9.4-T001, M9.4-T002 closeouts
- docs/meeting-notes/2026-05-24-r3.md §6 (做法 3 design-red-team)
- docs/engineering-practice.md (review-role precedent)
- .claude/agents/reviewer.md (skeptical, evidence-grounded precedent)
- docs/adr/ (any existing ADR with explicit alternatives-considered section)

Mission (full version in task spec):
Create .claude/agents/design-red-team.md. The agent reads a proposed
design (from a task spec, ADR draft, or planning doc) plus the
requirements-skeptic / legacy-archaeologist outputs, and refutes it:
≥3 alternative designs, each with stated tradeoffs; an explicit list of
capabilities the current proposal would drop relative to the legacy or
alternative paths; long-term cost estimates (cognitive load, ops burden,
extensibility, blast radius). The agent must NOT sign off on a design,
modify code, or claim authority over the final decision. It must cite
file:line evidence when arguing a legacy capability would be lost.
```

---

## Loop Prompt 4 — M9.4-T004 `design-archaeology` skill + protocol §7 wiring

```
/goal Execute M9.4-T004 design-archaeology skill + milestone-loop-protocol §7 wiring until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T004-discovery-debate-gate.md

Read also (background context):
- M9.4-T001, M9.4-T002, M9.4-T003 closeouts
- .claude/skills/ (existing skill front-matter precedent)
- docs/milestone-loop-protocol.md (current §1–§6)
- docs/meeting-notes/2026-05-24-r3.md §6 (做法 1 + 做法 4 acceptance criteria)

Mission (full version in task spec):
Create .claude/skills/design-archaeology/SKILL.md that orchestrates the
three agents in order: legacy-archaeologist → requirements-skeptic →
design-red-team. Add docs/architecture/discovery-debate-gate.md with the
canonical acceptance-criteria template task specs can include by
reference. Add an additive §7 "Discovery / Debate Gate" to
docs/milestone-loop-protocol.md describing when the gate is mandatory
(tasks tagged arch: or legacy-migration:) and how its outputs are
attached to the task closeout. Do NOT change §1–§6 of the protocol; the
gate is additive and opt-in by task tag.
```

---

## Loop Prompt 5 — M9.4-T005 `kkr.py` replay + smoke tests

```
/goal Execute M9.4-T005 kkr.py / kkr.yaml replay through the Discovery / Debate Gate and smoke tests until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T005-kkr-replay-and-smoke.md

Read also (background context):
- M9.4-T001 .. M9.4-T004 closeouts
- tools/legacy/kkr.py, tools/legacy/kkr.yaml
- docs/tasks/m1/M1-T000-legacy-tool-inventory.md (what was migrated)
- .claude/skills/design-archaeology/SKILL.md (from T004)

Mission (full version in task spec):
Invoke the design-archaeology skill on the legacy kkr.py / kkr.yaml
fixture and capture the three agent transcripts under
docs/evidence/m9_4-kkr-replay/{legacy-archaeologist,requirements-skeptic,
design-red-team}.md. Acceptance criterion: the replayed run surfaces
the multi-Kaggle-account / owner / env mapping that the original kkr
migration missed (R3 meeting note §6). Add tests/test_m9_4_agents.py
(no DB, no creds, no network): the three agent .md files parse,
required front-matter fields are present, the design-archaeology skill
loader resolves them, and the discovery-debate-gate.md acceptance
template has at least the canonical sections.
```

---

## Loop Prompt 6 — M9.4-T006 exit criteria + final review

```
/goal Execute M9.4-T006 exit criteria validation + docs/milestones/m9_4/final-review.md until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_4/M9_4-T006-exit-criteria.md
Skill: milestone-final-review

Read also (background context):
- M9.4-T001 .. M9.4-T005 closeouts
- docs/milestones/m9/final-review.md (layout precedent)
- docs/milestones/m8_5/final-review.md (layout precedent)
- docs/evidence/m9_4-kkr-replay/

Mission (full version in task spec):
Roll up the M9.4 validation matrix into docs/milestones/m9_4/final-review.md
mirroring the M8.5 / M9 layout. Update PROJECT_STATE.md to mark M9.4
done and append the "Discovery / Debate Gate" capability. Update
README.md current-milestone section if M9.4 is the active milestone at
close time. Then run the milestone-end git+gh sequence per
docs/milestone-loop-protocol.md §5: one commit per Loop Prompt, push the
worktree branch, open a PR against main with m9_4-final-review.md as
the PR body.
```

---

## Cross-references

- Meeting note origin: `docs/meeting-notes/2026-05-24-r3.md` §6.
- Sibling planning milestone (different scope, same shape): `docs/milestones/m9_1/loop-prompts.md`.
- Demonstration fixture: `tools/legacy/kkr.py`, `tools/legacy/kkr.yaml`.
- Parent agent inventory: `.claude/agents/`.
- Parent skill inventory: `.claude/skills/`.
