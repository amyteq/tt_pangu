---
name: milestone-final-review
description: Generate docs/milestones/m{N}/final-review.md from a milestone's validation matrix. Use at milestone end, after every Loop Prompt has PASSed. Mirrors the M5/M6 final-review layout — does not invent metrics.
---

# milestone-final-review — write `docs/milestones/m{N}/final-review.md`

Use this skill at milestone end to produce the canonical final review markdown.

## Inputs you need

- Milestone number `{N}` (e.g. `6`, `8_5`).
- The PASS/FAIL/SKIP table from every Loop Prompt's verification step in the current session. If a Loop Prompt was completed in an earlier session, the human must paste or point to that PASS record.
- The current branch (worktree) name.
- The actual DSN / endpoint values used during validation (for the "DB access note").

Refuse to write the final review if any input above is missing or unknown. Do **not** fill in placeholder metrics.

## Layout

Mirror the immediately-prior milestone's final review (`docs/m{N-1}-final-review.md`):

```markdown
# M{N} / MVP-{N} — final integration review

_Branch: `<branch>`._

## Milestone exit (per docs/milestones/README.md)

> <one-paragraph block-quote of the milestone's exit definition,
>  copied verbatim from docs/milestones/README.md>

**Status: met.** <one sentence — how many non-SKIP checks PASSed,
against which DB/endpoint, with what sandbox notes>

## Validation matrix

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | <description> | PASS | <one-line evidence: command output snippet, count, file path> |
| 2 | ... | ... | ... |

(one row per check from every Loop Prompt; PASS/FAIL/SKIP plus a concrete
evidence snippet — not "looks good")

## DB access note

<copy from prior milestone if unchanged; update only if the DSN, sandbox
rule, or container-IP behavior changed this milestone>

## What landed

<bulleted list of major deliverables, one bullet per Loop Prompt's main
output — file paths, table names, CLI subcommands, ADR numbers. Refer
to the actual file paths created, not the task spec's planned paths>

## M{N+1} follow-ups

<numbered list copied verbatim from the milestone's last task spec's
"M{N+1} follow-ups" section, if present; otherwise synthesize from
the Loop Prompts' stop conditions and known-gaps notes>
```

## Required honesty

- If a check SKIPPed, write **SKIP** with the documented reason — not PASS.
- If a metric is unknown, write `N/A — not recorded` and add it to the follow-ups list. Never fabricate numbers.
- If a Loop Prompt PASSed only after a fix-up, write **PASS** but record the fix in the "What landed" section so the diff is auditable.

## Output

Write to `docs/milestones/m{N}/final-review.md`. After writing, print the file path, the validation matrix's PASS/FAIL/SKIP count, and any items deferred to follow-ups.

## Safety

- READ_ONLY against everything except `docs/milestones/m{N}/final-review.md` itself.
- No git, no gh, no network. Leave commit/push/PR to `worktree-milestone-pr`.
