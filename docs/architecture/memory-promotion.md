# Memory promotion — evidence → proposal → human gate → canonical memory

Status: design note paired with [ADR-0015](../adr/0015-memory-promotion-model.md) (the canonical-memory list) and the parent design at [`session-memory-and-audit.md`](session-memory-and-audit.md) (the three-tier raw/curated/core model). Source: `docs/meeting-notes/2026-05-24-r3.md` §3.

This document describes the data flow the `.claude/skills/memory-promotion/SKILL.md` skill implements. The skill turns evidence (GitHub conversation, meeting-notes, session output) into a patch *proposal* against one of the four canonical memory files. A human, not the skill, applies the patch.

The guiding principle is the one already in [`github-as-agent-interface.md`](github-as-agent-interface.md): **a comment is evidence, not a decision.** ADR-0015 makes that principle enforceable on the file-write side: nothing reaches canonical memory without crossing a human-reviewed diff.

---

## 1. Data flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Evidence sources                                                         │
│                                                                          │
│  GitHub                          docs/meeting-notes/      Session output │
│  ├─ issue body                   <date>-rN.md             docs/evidence/ │
│  ├─ PR body                                                <task-id>/    │
│  ├─ review comments                                        closeout.md   │
│  ├─ issue comments                                                       │
│  └─ labels (decision:confirmed?)                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  Phase 1 — gather (verbatim quotes only)
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 2 — Extraction (structured output, in-skill)                       │
│                                                                          │
│   confirmed_requirements:        # each entry cites a source             │
│   changed_requirements:                                                  │
│   confirmed_design_decisions:                                            │
│   changed_design_decisions:                                              │
│   open_questions:                # ambiguity goes here, not confirmed_*  │
│   blockers:                                                              │
│   proposed_labels:                                                       │
│                                                                          │
│   Confirmation markers:                                                  │
│     - decision:confirmed label                                           │
│     - human "approved/yes/confirmed" comment                             │
│     - merged PR body                                                     │
│   Absent any of these → open_questions, never confirmed_*                │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  Phase 3 — write proposal file
┌─────────────────────────────────────────────────────────────────────────┐
│ docs/proposals/memory-<YYYY-MM-DD>-<short>.md                            │
│                                                                          │
│   - Target file: ONE OF the four canonical files                         │
│   - Patch instruction: literal diff OR "insert after section X"          │
│   - [ ] approved by <name> on <YYYY-MM-DD>     (unchecked)               │
│   - Evidence: URL+anchor or file:line for every claim                    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  Phase 4 — human gate (NOT in-skill)
┌─────────────────────────────────────────────────────────────────────────┐
│ Canonical memory (the four files governed by ADR-0015)                   │
│                                                                          │
│   PROJECT_STATE.md                                                        │
│   docs/milestones/README.md                                                      │
│   docs/milestones/m{N}/handoff.md                                          │
│   docs/adr/NNNN-*.md                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

The arrow from proposal → canonical is **always** a human action: either
a reviewer applies the diff in their editor, or a task spec explicitly
authorises one specific edit at milestone close (the latter is how M9.3
itself appends to `PROJECT_STATE.md` "Completed milestones").

---

## 2. Canonical memory (four files)

Repeated here verbatim from [ADR-0015](../adr/0015-memory-promotion-model.md):

1. `PROJECT_STATE.md`
2. `docs/milestones/README.md`
3. `docs/milestones/m{N}/handoff.md`
4. `docs/adr/NNNN-*.md`

Out of scope for this skill: `README.md`, `AGENTS.md`, `CLAUDE.md`,
`docs/m{N}-final-review.md`, `docs/tasks/<task-id>.md`, anything under
`memory/` (user auto-memory).

---

## 3. Cross-links

- Skill: [`.claude/skills/memory-promotion/SKILL.md`](../../.claude/skills/memory-promotion/SKILL.md)
- Sibling skill (label gating): [`.claude/skills/github-issue-triage/SKILL.md`](../../.claude/skills/github-issue-triage/SKILL.md)
- Sibling skill (drift scan): [`.claude/skills/inventory-drift-audit/SKILL.md`](../../.claude/skills/inventory-drift-audit/SKILL.md)
- Parent design: [`session-memory-and-audit.md`](session-memory-and-audit.md)
- Companion design: [`github-as-agent-interface.md`](github-as-agent-interface.md)
- Governing ADR: [ADR-0015](../adr/0015-memory-promotion-model.md)

---

## 4. Non-goals

- This document does not describe how proposals are *applied*. Application is a normal git workflow: edit, diff-review, commit.
- It does not describe the broader Tier 1 (raw) and Tier 2 (curated session) flow — see [`session-memory-and-audit.md`](session-memory-and-audit.md).
- It does not describe label-state-machine transitions or AI-pickup gating — see [`github-as-agent-interface.md`](github-as-agent-interface.md) and [`github-issue-triage`](../../.claude/skills/github-issue-triage/SKILL.md).
- It does not regulate `memory/` (user Claude Code auto-memory).
