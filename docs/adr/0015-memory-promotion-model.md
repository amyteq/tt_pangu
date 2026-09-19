# ADR-0015: Memory-promotion model — canonical files and propose-only path

## Status

Accepted (M9.3, 2026-05-26).

## Context

Project decisions land in three places during day-to-day work: GitHub issue / PR / review comments, meeting-notes markdown files under `docs/meeting-notes/`, and Claude Code session activity. The [`session-memory-and-audit.md`](../architecture/session-memory-and-audit.md) design note describes the three-tier raw → curated → core memory model; the [`github-as-agent-interface.md`](../architecture/github-as-agent-interface.md) note explains why a comment is *evidence, not a decision*.

Until M9.3, the step that crosses from evidence to canonical memory was ad-hoc — sometimes done by hand, sometimes silently skipped. We need:

- An explicit, narrow list of which files are **canonical memory** (the Tier 3 surface this ADR governs), so the promotion step has a clear target.
- A **propose-only** path so that promotion is a reviewable diff and not a quiet rewrite.
- A clear boundary between this canonical memory and the user's Claude Code auto-memory directory at `memory/`, so the two systems do not stomp on each other.

## Decision

### Canonical memory (four files / patterns)

The `memory-promotion` skill targets exactly these four:

1. `PROJECT_STATE.md` — current milestone, open decisions, completed milestones.
2. `docs/milestones/README.md` — milestone roster, scope, dependency order.
3. `docs/milestones/m{N}/handoff.md` — per-milestone exit state.
4. `docs/adr/NNNN-*.md` — long-lived architectural decisions.

Other Tier 3 surfaces named in `session-memory-and-audit.md` §4 — `docs/m{N}-final-review.md` and `docs/tasks/<task-id>.md` — are *historical records* (final-review) and *pre-implementation specs* (task specs). They are not promotion targets: the final-review skill owns one, task authors own the other. ADR-0015 does not regulate them.

### Propose-only path

The `memory-promotion` skill (`.claude/skills/memory-promotion/SKILL.md`) writes patch *proposals* to `docs/proposals/memory-<YYYY-MM-DD>-<short>.md` with an unchecked human-approval checkbox. It **never** edits the four canonical files itself, even when a confirmation marker (`decision:confirmed` label, merged PR with explicit text, or a human "approved/yes/confirmed" comment) is present.

A human (or a task spec explicitly authorising one specific edit, e.g. milestone close) applies the proposal as a normal diff.

### Boundary with `memory/` (user auto-memory)

The `memory/` directory at the repo root holds the user's Claude Code auto-memory — `MEMORY.md` (index) plus topic files (`user_profile.md`, `platform_decisions.md`, `kaggle_workflow.md`, etc.). It is governed by the user's Claude Code session memory rules and is **not** canonical project memory. The `memory-promotion` skill does not read or write it.

The two systems may agree or disagree at any moment; ADR-0015 makes no claim about consistency between them. If a fact appears in both, canonical memory wins for repo-level questions; auto-memory wins for user-preference questions.

## Consequences

- **Human gate is load-bearing.** Every change to `PROJECT_STATE.md`, `docs/milestones/README.md`, `docs/milestones/*/handoff.md`, or `docs/adr/**` is now a human-reviewed diff. No skill writes them silently.
- **`docs/proposals/` is a staging directory**, not canonical memory. Files there accumulate until applied or discarded; a periodic cleanup pass is expected but not scheduled by this ADR.
- **Relationship to existing skills**: `github-issue-triage` gates labels and AI pickup (different surface — issue-level state, not Tier 3 files); `inventory-drift-audit` scans the repo for contradictions across all files (different scope — read-only audit that may *cite* but not patch canonical memory); `memory-promotion` proposes patches against the four canonical files only.
- **Milestone closeout** stays the conventional channel for PROJECT_STATE.md and docs/milestones/README.md updates. The `memory-promotion` skill produces proposals that the closeout step applies, rather than skipping the proposal step.
- **The `memory/` auto-memory is sandboxed off.** Users who change their auto-memory rules do not change canonical project memory.

## Relationship to existing skills and docs

| Skill / doc | Surface it touches | This ADR's stance |
|---|---|---|
| `.claude/skills/memory-promotion/SKILL.md` | The four canonical files (proposals only) | **Created by this ADR.** Propose-only. |
| `.claude/skills/github-issue-triage/SKILL.md` | GitHub labels + AI pickup | Sibling. Different surface. No overlap. |
| `.claude/skills/inventory-drift-audit/SKILL.md` | Whole-repo drift scan | Sibling. Read-only on canonical files. |
| `.claude/skills/milestone-final-review/SKILL.md` | `docs/m{N}-final-review.md` | Not regulated here (final-review is not canonical memory). |
| `.claude/skills/design-archaeology/SKILL.md` | `docs/archaeology/<short>.md` | Different surface (legacy analysis). No overlap. |
| `docs/architecture/session-memory-and-audit.md` | Tier 1/2/3 model | Parent design. ADR-0015 narrows Tier 3 to the four canonical files for promotion purposes. |
| `docs/architecture/github-as-agent-interface.md` | "Comment is evidence, not decision" principle | Cited principle. ADR-0015 enforces it on the file-write side. |
| `memory/` (user auto-memory) | User's Claude Code memory store | Out of scope. ADR-0015 explicitly does not regulate it. |

## Open questions (non-blocking)

- Should `README.md` milestone-status be canonical? Today it is updated at milestone close alongside `PROJECT_STATE.md`. The plan is to treat it as a *mirror* of canonical memory, not canonical itself — so the skill does not target it. Reconsider if README begins to carry decisions not in the four canonical files.
- Should `AGENTS.md` and `CLAUDE.md` be canonical? They are agent-instructions, not project decisions. Same answer: not canonical.

These questions are surfaced here so future reviewers know the boundary was deliberate, not accidental.
