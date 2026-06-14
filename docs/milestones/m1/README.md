# M1 — local Kaggle tooling wrapper baseline

Milestone overview lives in the canonical index:
[`docs/milestones/README.md`](../README.md) (§ "M1 / MVP-1").

## Files in this folder

| File | What it is |
|---|---|
| `loop-prompts.md` | Canonical M1 loop prompts (architecture answers, sequential execution plan). Migrated from `docs/m1-loop-prompts.md`. |
| `notes.md` | Earlier Arch-Linux-runner-oriented M1 loop prompts. Migrated from `docs/prompts/M1-loop-prompts.md` and kept as historical notes — it is an alternate/earlier take on the same milestone, not a duplicate of `loop-prompts.md`. |
| `handoff.md` | M1 → M2 handoff. Migrated from `docs/handoffs/m1-handoff.md`. |

## Note on the two prompt files

There were two M1 loop-prompt documents before the docs migration:

- `docs/m1-loop-prompts.md` — the canonical milestone loop prompts → `loop-prompts.md`.
- `docs/prompts/M1-loop-prompts.md` — an older runner-focused variant → `notes.md`.

The second was **moved, not deleted**: its content (Arch Linux runner setup,
per-task `claude --bg` invocations) is M1-relevant historical context that is
not fully reproduced in `loop-prompts.md`. See
[`docs/milestones/migration-report.md`](../migration-report.md) for the full
move map.
