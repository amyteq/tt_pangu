---
name: review-pr
description: Review a pull request for correctness, test coverage, and safety alignment with CLAUDE.md rules.
version: "1.0"
argument-hint: "[pr-number-or-branch]"
arguments:
  - pr_ref
allowed-tools:
  - read_file
  - bash
  - web_fetch
  - run_tests
  - litellm_call
approval-policy: permissive-dev
tags:
  - code-review
  - platform-dev
---

Review PR or branch `$pr_ref`.

Steps:
1. `gh pr diff $pr_ref` or `git diff main...$pr_ref` — collect the diff.
2. Read changed files in full.
3. Read CLAUDE.md safety boundaries.
4. Assess: correctness, test coverage, security, CLAUDE.md alignment.
5. Run tests: `python -m pytest tests/ -v -m "not db"`.
6. Produce a structured review:
   - Summary of changes.
   - Issues found (blocking / non-blocking).
   - Test results.
   - Security concerns.
   - Recommendation: approve / request-changes / needs-human-review.
