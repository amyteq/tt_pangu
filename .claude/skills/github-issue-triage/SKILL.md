---
name: github-issue-triage
description: Triage one or more GitHub issues — propose label adds/removes and a triage comment, gated by deterministic rules. Never grants ai:ready without confirmed decisions and clear acceptance criteria.
---

# github-issue-triage — propose labels and triage comments

Use this skill when working an issue triage pass on this repo. The default mode is *propose-only*: surface the plan, never call `gh issue edit / comment` or `gh label *` without explicit human approval.

## Inputs

- Issue numbers (one or more), OR a filter like `is:open label:ai:triage`.
- Read access to `.github/labels.yml`, `.github/ISSUE_TEMPLATE/*`, `docs/engineering-practice.md`.

## Rules (deterministic only)

A change is *deterministic* when the rule does not require interpreting an ambiguous comment.

### Promote to `ai:ready`

All must be true:

- Issue is open.
- Issue has acceptance criteria filled in (look for the `acceptance` field in the issue body — issue forms make this explicit).
- Issue has an owner / reviewer (assignee or `@`-mention in body).
- If `type:decision` was ever applied, a linked `decision:confirmed` issue or comment exists.
- Issue does not have `ai:blocked`.
- Issue does not touch the safety classification surfaces (secrets, schema, Kaggle live, customer-visible side effects) unless the issue body has an explicit "approved by <human>" record.

### Apply `ai:blocked`

Any one:

- The issue references an unresolved `decision:needed` issue.
- The issue body contains a checked safety classification box without an approval record.
- A reviewer comment explicitly asks to block.

### Suggest `area:*`

From file paths, modules, or surface keywords mentioned in the body. Multiple `area:*` labels are allowed.

### Suggest `priority:*`

Only from explicit owner statements ("P0", "blocker", "must ship by …"). Never infer priority from comment tone.

## Output

For each issue:

```
#<n> <title>
  current labels: ...
  proposed adds: ...
  proposed removes: ...
  triage comment (draft):
    > ...
  decision: ai:ready | ai:blocked | decision:needed | triage-deferred
  rule(s) applied: ...
  evidence: <issue body field | comment URL | doc anchor>
```

## Must not

- Do not call any remote-write `gh` command without explicit human approval.
- Do not infer a decision from ambiguous comments — when the answer is unclear, recommend `decision:needed` + `ai:blocked` and tag a human.
- Do not bulk-apply labels across many issues without first surfacing the full batch plan for human approval.
- Do not promote to `ai:ready` if acceptance criteria are empty or vague.
