# M1 loop prompts for Arch Linux Claude Code runner

## Purpose
These prompts run M1 / MVP-1: local Kaggle tooling wrapper baseline.

M1 should create a safe local wrapper layer around existing helper scripts under `tools/legacy/`, especially Python/IPython notebook conversion scripts, without making any real Kaggle submissions or remote uploads.

## Before running on Arch Linux

```bash
cd ~/work/kaggle-code-agent
claude --version
git status --short
git fetch origin
git checkout main
git pull --rebase
```

Use one branch/worktree per task or one single M1 branch. Do not let Mac VS Code Claude, Arch Claude CLI, and Claude Code Web edit the same branch at the same time.

## Recommended: safe sequential mode

Run tasks one at a time. Merge/rebase between tasks if needed.

### T000: inventory first

```bash
git checkout -b claude/arch/M1-T000-legacy-tool-inventory
claude --bg \
  --name "M1-T000-legacy-tool-inventory" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T000-legacy-tool-inventory.md until acceptance criteria pass, or stop after 40 turns and summarize blockers. Do not implement tools/kca yet. Do not run real Kaggle commands. Do not read or print secrets."
```

### T001: CLI skeleton

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-T001-kca-cli-skeleton
claude --bg \
  --name "M1-T001-kca-cli-skeleton" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T001-kca-cli-skeleton.md until acceptance criteria pass, or stop after 80 turns and summarize blockers. Keep changes small and reviewable. Do not run real Kaggle commands. Do not read or print secrets."
```

### T002: notebook conversion wrappers

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-T002-notebook-conversion-wrappers
claude --bg \
  --name "M1-T002-notebook-conversion-wrappers" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T002-notebook-conversion-wrappers.md until acceptance criteria pass, or stop after 80 turns and summarize blockers. Wrap existing tools/legacy scripts where safe. Do not rewrite legacy code unless necessary. Do not run real Kaggle commands. Do not read or print secrets."
```

### T003: artifact layout and smoke tests

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-T003-artifact-layout-smoke-tests
claude --bg \
  --name "M1-T003-artifact-layout-smoke-tests" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T003-run-artifact-layout-and-smoke-tests.md until acceptance criteria pass, or stop after 60 turns and summarize blockers. Use temporary directories for tests. Do not run real Kaggle commands. Do not read or print secrets."
```

### T004: approval hooks

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-T004-kaggle-approval-hooks
claude --bg \
  --name "M1-T004-kaggle-approval-hooks" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T004-kaggle-remote-operation-approval-hooks.md until acceptance criteria pass, or stop after 70 turns and summarize blockers. Use synthetic hook JSON tests only. Do not run real Kaggle commands. Do not read or print secrets."
```

### T005: final integration review

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-T005-final-integration-review
claude --bg \
  --name "M1-T005-final-integration-review" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Execute docs/tasks/m1/M1-T005-m1-final-integration-review.md until acceptance criteria pass, or stop after 50 turns and summarize blockers. Do not add major new features. Do not run real Kaggle commands. Do not read or print secrets."
```

## Alternative: single overnight M1 branch

Use this only if you want one long branch/PR and can review a larger diff.

```bash
git checkout main
git pull --rebase
git checkout -b claude/arch/M1-local-kaggle-wrapper-baseline
claude --bg \
  --name "M1-local-kaggle-wrapper-baseline" \
  --permission-mode auto \
  --model opus \
  --effort high \
  "/goal Complete M1 / MVP-1 local Kaggle tooling wrapper baseline until all exit criteria pass or stop after 120 turns and summarize blockers.

Read first:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- docs/architecture/model-routing.md
- latest docs/adr files
- tools/legacy/TOOLS.md
- tools/legacy/**/*.py

Scope:
1. Inventory tools/legacy and document side-effect levels.
2. Build tools/kca CLI skeleton.
3. Register 1-2 existing Python/IPython notebook conversion scripts behind stable wrapper commands.
4. Define and test runs/<competition>/<run_id>/ artifact layout.
5. Add smoke tests for wrapper commands and artifact creation.
6. Add or strengthen hooks/settings so Kaggle submit/kernel push/upload commands require human approval or are blocked in automation.
7. Update docs/tooling and PROJECT_STATE.md with concise status.

Required safe commands:
- python -m tools.kca --help
- python -m tools.kca tools list --json
- python -m tools.kca runs init --competition smoke-test --run-id test-run-001 --root /tmp/kca-runs
- python -m tools.kca notebook to-ipynb tests/fixtures/kca/hello.py --output /tmp/kca-hello.ipynb --force
- python -m tools.kca notebook to-script /tmp/kca-hello.ipynb --output /tmp/kca-hello.py --force
- pytest or the repo documented test command

Hard rules:
- No autonomous competition agent loop.
- No real Kaggle submission.
- No kernel push/upload/dataset upload.
- No full Supabase integration.
- Never read or print secrets.
- Keep git diff focused on M1.
- If legacy script behavior is unclear, document blockers instead of guessing.

Return at completion:
- files changed
- tests run and results
- risks
- approval needs
- remaining M1/M2 follow-ups"
```

## Optional in-session `/loop` monitor

Use `/loop` only for short-term polling while the Claude Code session remains open. It is not a durable task queue.

```text
/loop 30m Check the current M1 branch status. Run only read-only commands unless a previous M1 task already authorized local tests. Summarize: current branch, git status, latest test result if available, blockers, and whether human approval is needed. Do not edit files, do not push, do not run Kaggle remote-write or submission commands, and do not read secrets.
```

## Mac/VS Code review prompt after each PR

```text
Review the PR branch for M1. Do not edit files yet.

Focus on:
- whether the implementation matches docs/tasks/m1/M1-*.md;
- whether `tools/kca` wrappers are local-first and safe;
- whether notebook conversion uses existing tools/legacy scripts when safe;
- whether tests use temp dirs and fixtures rather than real competition data;
- whether Kaggle submit/kernel push/upload commands are blocked or require human approval;
- whether any secrets or credential paths were read, printed, or committed;
- whether docs/tooling matches actual CLI behavior.

Return:
- approve/request changes;
- concrete issues with file paths;
- commands you ran;
- suggested smallest follow-up patch.
```

## Human approval prompt for remote operations

Use this exact format if Claude requests a remote-write or submission action:

```text
Human approval request:
- Operation:
- Command:
- Competition/platform:
- Run ID / branch:
- Expected remote side effect:
- File/artifact being uploaded or submitted:
- Validation already completed:
- Risk if wrong:
- Rollback possible? yes/no:

Do not execute until I explicitly reply: APPROVE <operation>.
```
