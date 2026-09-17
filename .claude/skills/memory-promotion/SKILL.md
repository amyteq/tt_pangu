---
name: memory-promotion
description: Use to distill GitHub issue/PR/review/meeting-notes content into proposed patches against canonical memory (PROJECT_STATE.md, docs/milestones/README.md, docs/milestones/*/handoff.md, docs/adr/). Propose-only — never edits canonical files; writes proposals to docs/proposals/. Inherits the no-inference-from-ambiguity rule from github-issue-triage.
---

# memory-promotion — distil evidence into propose-only canonical-memory patches

Use this skill when GitHub issue / PR / review / meeting-notes activity or a session's work has produced facts that *should* land in canonical project memory. The skill turns evidence into a patch *proposal*, never into a direct edit. A human applies the patch as a normal diff.

Pairs with [`github-issue-triage`](../github-issue-triage/SKILL.md) (label and AI-pickup gating) and [`inventory-drift-audit`](../inventory-drift-audit/SKILL.md) (scan for contradictions). All three are propose-only on the canonical memory files.

## Canonical memory (ADR-0015)

The four canonical files this skill targets:

- `PROJECT_STATE.md` — current milestone, open decisions, completed milestones.
- `docs/milestones/README.md` — milestone roster, scope, dependency order.
- `docs/milestones/m{N}/handoff.md` — per-milestone exit state.
- `docs/adr/NNNN-*.md` — long-lived architectural decisions.

The user's `memory/` directory (Claude Code auto-memory) is a **separate system** — not canonical project memory and out of scope for this skill. See ADR-0015 for the boundary.

## 4-phase workflow

### Phase 1 — Evidence gathering

Inputs (one or more):

- GitHub issue / PR URL or number — read via `gh issue view <n>`, `gh pr view <n> --json title,body,reviews,commits,labels`, `gh api repos/<owner>/<repo>/issues/<n>/comments`, `gh api repos/<owner>/<repo>/pulls/<n>/comments`.
- `docs/meeting-notes/<date>-rN.md` path.
- A session's evidence bundle (`docs/evidence/<task-id>/closeout.md`).

Quote source text verbatim with an anchor (URL+`#issuecomment-...` or `file:line`). Never paraphrase as fact.

### Phase 2 — Extraction (structured output)

Emit a YAML-ish block with these seven keys (omit any with no entries — do **not** invent filler):

```text
confirmed_requirements:        # each entry must cite source line/URL
changed_requirements:
confirmed_design_decisions:
changed_design_decisions:
open_questions:                # any ambiguity goes HERE, NOT into confirmed_*
blockers:
proposed_labels:               # GitHub label add/remove suggestions
```

A "confirmation marker" — what makes something `confirmed_*` rather than `open_questions:` — is one of:

- The issue/PR carries the `decision:confirmed` label.
- A human reviewer left an explicit "approved" / "yes" / "confirmed" comment on the artifact.
- The PR was merged with the relevant text in its body.

Anything else is `open_questions:`.

### Phase 3 — Patch proposal

Write proposals to `docs/proposals/memory-<YYYY-MM-DD>-<short>.md`. The file MUST contain:

- **Target file**: exactly one of the four canonical files. One target per proposal — split into multiple proposal files if needed.
- **Patch instruction**: either a literal diff block or an "insert after section X" instruction with the new text.
- **Human-approval checkbox**: `[ ] approved by <name> on <YYYY-MM-DD>` — left unchecked. The human checks it when applying.
- **Evidence link**: URL+anchor or `file:line` for every claim the patch encodes.

### Phase 4 — Human gate

Stop after Phase 3. Do **not** edit any canonical file. A human (or a follow-up task with explicit authorisation, e.g. a milestone close) applies the patch.

## Must / Must not

- **Must** treat ambiguous comments as `open_questions:`. Never invent a `decision:confirmed` from silence.
- **Must** quote source text verbatim with an anchor (URL+`#…` or `file:line`). Paraphrase-as-fact is a defect.
- **Must** write proposals under `docs/proposals/` only. Never edit `PROJECT_STATE.md`, `docs/milestones/README.md`, `docs/milestones/*/handoff.md`, or `docs/adr/**` from within this skill.
- **Must** leave the approval checkbox unchecked. The human checks it on apply.
- **Must not** issue `gh` write commands — no `gh issue/pr edit|comment|close|label`, no `gh label create|delete`. Reading via `gh issue view`, `gh pr view`, `gh api …` is allowed.
- **Must not** edit anything under `memory/` — that is the user's auto-memory directory, governed separately. ADR-0015 explains.
- **Must not** apply a patch even when a confirmation marker exists. Application is a separate, explicit step (milestone close, or a task spec that authorises one specific edit).

## Trigger phrases

Use this skill when a task says: "distil PR #N", "extract decisions from <meeting-notes>", "what landed in <issue>", "promote to PROJECT_STATE", "update milestones from PR review", "propose a handoff patch", "draft an ADR from comments".

## Worked example

`docs/proposals/memory-2026-05-26-m10-pr18.md` is the canonical worked example, produced in M9.3-T003 against PR #18 (M10 planning). It illustrates the extraction matrix + one concrete patch proposal against `PROJECT_STATE.md` or `docs/milestones/README.md`, with an unchecked approval checkbox.
