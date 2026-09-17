---
name: milestone-review
description: Review a milestone against acceptance criteria, produce a structured review report. Read-only; never claims completion on its own. Distinct from milestone-final-review (which writes the canonical final review doc).
---

# milestone-review — produce the review that feeds the milestone closeout

Use this skill mid- or end-milestone to map every acceptance criterion to evidence. It is the input to `milestone-final-review`, not a replacement.

## Inputs

- Milestone number (e.g. `7`, `8`, `8_5`).
- `docs/milestones/README.md` and `docs/tasks/m{N}/M{N}-T*.md`.
- Merged PRs for the milestone (`gh pr list --base main --state merged` with milestone tag or label).
- CI run results (`gh api repos/.../actions/runs`).
- `temp/*.log` files captured during validation.
- Audit logs in `.agent/` and any artifacts in `docs/evidence/`.

## Method

For each acceptance criterion in the task spec:

1. Find the evidence: test run URL / commit / doc section / audit row.
2. Mark `PASS` (evidence exists and matches), `FAIL` (evidence contradicts), or `GAP` (no evidence found).
3. If `GAP`, propose a follow-up issue body with acceptance criteria.

## Output

```
Milestone: M{N}
Branch / PR: ...
Acceptance criteria:
  - [PASS|FAIL|GAP] <criterion> — evidence: <link>
  ...
Open follow-up issues (proposed):
  - <title>, labels: ... — <body>
Risks introduced:
  - ...
Ready for closeout: YES | NO  (with reasons)
```

## Must not

- Do not write `docs/milestones/m{N}/final-review.md` — that is the `milestone-final-review` skill's job.
- Do not push commits, file issues, or apply labels **from this skill** — surface them as proposals for the caller to act on. This is a read-only review; it is not a repository rule that those writes need approval (`CLAUDE.md` → *GitHub collaboration* auto-allows them in the dev phase).
- Do not declare a criterion `PASS` without a specific evidence link. "I read the diff" is not evidence — the test/audit row/doc is.
- Do not retroactively redefine acceptance criteria to fit the implementation.
