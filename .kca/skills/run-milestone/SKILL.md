---
name: run-milestone
description: Execute a milestone task end-to-end in an isolated workspace until acceptance criteria pass or blockers are documented.
version: "1.0"
argument-hint: "[task-md-path]"
arguments:
  - task_path
allowed-tools:
  - read_file
  - edit_file
  - write_file
  - bash
  - git_commit
  - gh_pr_create
  - run_tests
  - litellm_call
  - create_artifact
approval-policy: permissive-dev
tags:
  - platform-dev
  - milestone
---

Execute milestone task `$task_path`.

Workflow:
1. Read $task_path and CLAUDE.md.
2. Inspect the current architecture and test state.
3. Create or use an isolated workspace/branch.
4. Make the smallest coherent change that advances the acceptance criteria.
5. Run relevant tests, lint, type checks, and smoke tests.
6. Iterate until acceptance criteria pass or a decision gate is reached.

Produce on completion:
- Summary of changes made.
- List of changed files.
- Test results.
- Risks and known regressions.
- Unresolved blockers.
- Recommended next task.

Stop conditions:
- All acceptance criteria pass.
- A decision gate is reached (create a decision record instead of proceeding).
- Max turns, budget, or time is reached.
