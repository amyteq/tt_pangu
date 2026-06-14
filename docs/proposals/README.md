# docs/proposals/ — staging for canonical-memory patches

This directory is the staging area for patch proposals against the four
canonical memory files (`PROJECT_STATE.md`, `docs/milestones/README.md`,
`docs/milestones/m{N}/handoff.md`, `docs/adr/NNNN-*.md`). See
[ADR-0015](../adr/0015-memory-promotion-model.md) and
[`docs/architecture/memory-promotion.md`](../architecture/memory-promotion.md).

## Rules

- Files here are **proposals**, not canonical memory. They are not the
  source of truth for anything.
- Each proposal targets exactly one canonical file and carries an
  unchecked `[ ] approved by <name> on <YYYY-MM-DD>` checkbox.
- A human applies a proposal by editing the target canonical file as
  a normal diff (not by editing the proposal in place).
- File naming: `memory-<YYYY-MM-DD>-<short-slug>.md`.
- Proposals may be discarded if their target fact is superseded
  before application. Discard by deletion in a normal PR.

## Who writes them

The `.claude/skills/memory-promotion/SKILL.md` skill writes proposals
here. No other skill is authorised to write canonical-memory patches.
