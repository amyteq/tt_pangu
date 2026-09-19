---
name: pr-closeout-review
description: Check that a PR's body matches the closeout template (tests run, docs/inventory, evidence, schema/secrets, remote side effects), and report which boxes are unchecked or unsupported. Read-only.
---

# pr-closeout-review — gate a PR against the closeout checklist

Use this skill before a PR is merged. It cross-checks `.github/pull_request_template.md` against the actual PR body and diff and produces a gate recommendation (`ready-to-merge` / `needs-revision`).

## Inputs

- PR number, OR the current branch's open PR.
- Read access to:
  - `gh pr view <n> --json title,body,url,headRefName,baseRefName`
  - `gh pr diff <n>`
  - `gh api repos/<owner>/<repo>/pulls/<n>/comments` (inline review comments)
  - the repository (to verify claims).

## Checks

For each section of the closeout template:

1. **Tests run.** Every checked box should have a paste of the command + result somewhere in the PR body or a linked CI run. Unchecked = blocker.
2. **Docs / inventory impact.** Either a doc was updated (verify in the diff) or a "no doc update needed" reason is given.
3. **Evidence.** Links resolve; CI artifact links are present for any UI / integration claim.
4. **Schema / RLS / secrets impact.** If the diff touches `supabase/migrations/`, the migration box must be checked and the migration must be reversible. If the diff touches `.claude/settings.json`, `.claude/hooks/*`, `env.example`, or `secrets`-adjacent files, the `area:security` label must be applied and a security-reviewer must be pinged.
5. **Remote side effects.** Non-destructive remote writes (`gh issue`/`pr` create, edit, comment, close, merge; `gh label create|edit`; pushing a feature branch) are auto-allowed in the dev phase and need no recorded approval — do not report them as gaps. Only the permanent-deletion writes listed in `CLAUDE.md` → *GitHub collaboration* (`gh … delete`, remote branch deletion, `scripts/sync_labels.py --apply`) require explicit human approval recorded on the closing issue. Verify that link. Force-push is not on that list and never belongs in a gap report as an approvable write: `CLAUDE.md` denies it outright, so a branch that was force-pushed is `needs-revision` and no approval record changes that.

## Output

```
PR #<n>: <title>
  Tests: PASS | GAPS — ...
  Docs/inventory: PASS | GAPS — ...
  Evidence: PASS | GAPS — ...
  Schema/secrets: PASS | GAPS — ...
  Remote side effects: PASS | GAPS — ...
Open review comments: <addressed-count> / <total>
Gate: ready-to-merge | needs-revision
Reasons (if needs-revision):
  - ...
```

## Must not

- Do not edit the PR body, post a comment, or merge **from this skill**. This is a read-and-report review: its output is a verdict for the caller to act on, and a reviewer that edits what it is reviewing cannot be checked. It is not a repository rule — `CLAUDE.md` → *GitHub collaboration* auto-allows `gh pr edit|comment|merge` during the dev phase, and phase-1 self-merge of your own feature-branch PR needs no separate approval once checks are green.
- Do not declare a check `PASS` based only on the box being ticked; verify the linked evidence exists.
- Do not approve a merge when `policy:approval-required` is set on the closing issue and the approval record is missing.
- Do not silence open review comments — surface them in the report.
