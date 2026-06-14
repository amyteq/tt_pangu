# M7-T007: Seed `.kca/skills/`

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 7; extracted here for the double-layer convention.

## Goal
Create four SKILL.md files under `.kca/skills/`:
`run-milestone`, `triage-log`, `prepare-submission`, `review-pr`.

## Read first
1. `tools/kca/agent/skill_loader.py`   (SkillMeta fields)
2. `tools/kca/agent/permission_policy.py`   (profile names)
3. `docs/meeting-notes/2026-05-21-r1.md`   (§2 KCA skill example + four workflow recipes)
4. `CLAUDE.md`   (operating principles — untrusted data, one-change-at-a-time discipline)
5. `docs/milestones/README.md`   (M7 seed skills list)

## Scope / Files / Implementation guidance

### `.kca/skills/run-milestone/SKILL.md`
```
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
```

### `.kca/skills/triage-log/SKILL.md`
```
---
name: triage-log
description: Summarise and classify a job's event log into actionable findings using a local or cloud LLM.
version: "1.0"
argument-hint: "[job-id]"
arguments:
  - job_id
allowed-tools:
  - read_file
  - litellm_call
approval-policy: permissive-dev
tags:
  - triage
  - log-analysis
---

Triage agent job `$job_id`.

Steps:
1. Fetch the job's event trail via `kca run logs --job-id $job_id`.
2. Route to a local model endpoint if available (see `kca local probe`).
3. Produce a structured summary:
   - Job status and outcome.
   - Key decisions made.
   - Errors and failures with root causes.
   - Recommended next action: retry / escalate / close.
```

### `.kca/skills/prepare-submission/SKILL.md`
```
---
name: prepare-submission
description: Validate a run's submission.csv, check format and metric, and create a submission decision record ready for human approval.
version: "1.0"
argument-hint: "[run-dir]"
arguments:
  - run_dir
allowed-tools:
  - read_file
  - bash
  - create_artifact
  - litellm_call
approval-policy: default
tags:
  - kaggle
  - submission
---

Prepare submission for run at `$run_dir`.

Steps:
1. Verify submission.csv exists and header matches competition format.
2. Check row count and that target column values are valid.
3. Load metrics.json; confirm cv_score is recorded.
4. Summarise: run_id, competition, cv_score, submission_path, artifact_hash.
5. Create a decision record:
   `kca decision create --operation kaggle_submit --run-id <id> --reason "CV:<score>"`
6. Print the decision record ID. Do NOT submit — human must approve via
   `kca decision approve <id>`.

Stop if:
- submission.csv is missing or malformed → fail with clear error.
- cv_score is missing → warn and stop.
```

### `.kca/skills/review-pr/SKILL.md`
```
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
```

## Acceptance criteria

```
python tools/kca/kca.py skill list --json
  → skills list includes run-milestone, triage-log, prepare-submission, review-pr

for skill in run-milestone triage-log prepare-submission review-pr; do
  python tools/kca/kca.py skill show $skill | grep -q "name:" && echo "PASS $skill" || echo "FAIL $skill"
done
```

Dry-run each seed skill (only run-milestone and review-pr take args):
```
python tools/kca/kca.py skill run run-milestone \
  --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json
  → ok=true, rendered_prompt contains "docs/tasks/m7/M7-T001.md"

python tools/kca/kca.py skill run triage-log \
  --arg job_id=00000000-0000-0000-0000-000000000000 --dry-run --json
  → ok=true
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: skill list output + dry-run results.

## Stop condition
Stop after 30 turns.
