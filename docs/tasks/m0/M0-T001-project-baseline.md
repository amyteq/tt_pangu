# M0-T001 Project Baseline

Status: proposed  
Milestone: M0 / MVP-0  
Owner: human + Claude Code  
Primary execution surface: Claude Code CLI / VS Code / Web  
Created: 2026-05-16

## Purpose

Create a reliable development baseline for `kaggle-code-agent` before implementing MVP-1 features.

This task is intentionally lightweight. It should clarify the repository's current state, project vocabulary, safety rules, docs structure, test commands, and near-term milestones. It should not implement the Kaggle tooling wrapper, Supabase worker, Agent SDK loop, browser integration, or competition execution features yet.

## Important terminology decision

The project must consistently distinguish two related but different meanings of "code agent":

1. **Platform-development coding agents**
   - These are the external AI tools used by the human developer to build this repository.
   - Examples: Claude Code CLI, Claude Code VS Code/Desktop/Web, ChatGPT Pro, Cursor, Lovable later.
   - Their job is to modify this product's source code, write docs, run local tests, open PRs, and help the human developer.
   - This product codebase is expected to become primarily TypeScript for the platform/control plane, with Python components for competition workers and ML tooling.

2. **Runtime competition code agents**
   - These are the agents that the finished platform will launch to help a human user compete in Kaggle, authorized CTF/lab, Devpost, hackathon, or similar competitions.
   - Initial runtime agent core: Claude Agent SDK, running in isolated worker containers/workspaces.
   - Future runtime model routing: Claude for main coding/reasoning, GPT/ChatGPT-style models for independent review, local vLLM/Ollama for low-cost subagents, selected by task type and policy.
   - Language/runtime depends on competition needs. Kaggle workflows are expected to be Python/notebook-first.

A successful M0 baseline should make this distinction visible in project docs so future AI tools do not confuse "Claude Code helping develop the platform" with "the platform's internal competition agent."

## Read these files first

Read these files before proposing or making changes. If a file does not exist, explicitly note it in the baseline report.

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/architecture/model-routing.md`
5. Latest files in `docs/adr/`
6. `docs/milestones/README.md` if present
7. Existing `README.md`, package manifests, test configuration, and CI files

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Prefer documentation and baseline structure over feature implementation.
- Never expose, print, or commit secrets.
- Never read `.env`, Kaggle credentials, API keys, local private keys, or files under `secrets/`.
- Never submit to Kaggle, push remote kernels, upload datasets, or call remote competition APIs without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.
- Do not run destructive commands.
- Do not push branches or create PRs unless the human explicitly asks.
- If package manager, language stack, or test commands are unclear, document the uncertainty instead of guessing.

## Current task

Inspect the current repository and create/update the minimum docs needed for a reliable development baseline.

### Required work

1. Understand the current repository layout.
2. Identify missing tests, missing docs, dependency issues, unclear entrypoints, and unclear project boundaries.
3. Confirm or create a lightweight project vocabulary that distinguishes:
   - platform-development coding agents;
   - runtime competition code agents;
   - platform/control plane;
   - worker/runtime;
   - competition policy modules.
4. Confirm that GitHub repo files are the durable project memory across Claude Code, ChatGPT, Cursor, Lovable, and future tools.
5. Ensure the baseline includes branch/PR/worktree rules for multi-agent development.
6. Ensure the baseline includes safety boundaries for Kaggle, notebooks, remote submissions, kernels, CTF/lab work, and secrets.
7. Ensure tests/smoke checks are documented, even if they are not yet implemented.
8. Ensure the milestone plan points from M0 to MVP-1 without starting MVP-1 implementation.

### Candidate files to add or update

Use existing files if they already exist. Do not create duplicates with conflicting names.

- `PROJECT_STATE.md`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/milestones/README.md`
- `docs/architecture.md` or `docs/architecture/overview.md`
- `docs/architecture/platform-vs-runtime-agents.md`
- `docs/testing.md`
- `docs/tasks/README.md`
- `.gitignore`
- `.claude/settings.json`

### Explicit non-goals

Do not implement these in M0-T001:

- `tools/kca/` CLI skeleton.
- Python/ipynb conversion wrappers.
- Kaggle CLI integration.
- Supabase schema or migrations beyond documenting intended direction.
- Claude Agent SDK worker.
- Browser/Playwright/MCP integration.
- CTF solver or exploitation tooling.
- Actual Kaggle submission or remote kernel push.
- Product UI, Lovable UI shell, dashboard, authentication, or billing.

These belong to later milestones, especially MVP-1 and beyond.

## Expected output from Claude Code

Before editing, return:

1. Summary of intended change.
2. Files likely to modify.
3. Risks and approval needs.
4. Tests/smoke checks to run.
5. Any missing context or ambiguities.

After editing, return:

1. Summary of changes made.
2. Files modified.
3. Commands run and results.
4. Risks, blockers, and follow-up tasks.
5. Whether the work stayed inside M0 scope.
6. Suggested next task prompt, likely `MVP-1` / `M1-T001-kca-cli-skeleton`.

## Acceptance criteria

- Repository docs clearly state the difference between platform-development coding agents and runtime competition code agents.
- Repository docs clearly state that GitHub files, not hidden AI memory, are the source of truth.
- Repository docs describe the current architecture or explicitly document what is still unknown.
- Repository docs describe how to run tests/smoke checks, or document blockers if no tests exist yet.
- `docs/milestones/README.md` exists or is updated with a high-level product plan from M0 through later Kaggle/CTF/hackathon support.
- Any updates to `CLAUDE.md` / `AGENTS.md` reinforce safety, branch/PR, secrets, test, and approval rules.
- No secrets, `.env`, Kaggle credentials, API keys, or private files are read or committed.
- No Kaggle submission, kernel push, dataset upload, or remote competition side effect occurs.
- No major feature implementation happens in this task.
- The final response includes a concise diff summary, test results, and blockers.

## Suggested safe commands

Use only commands appropriate for the detected repo. Prefer read-only commands until a plan is approved.

```bash
git status --short
git branch --show-current
git log --oneline -5
find . -maxdepth 3 -type f \
  -not -path './.git/*' \
  -not -path './node_modules/*' \
  -not -path './.venv/*' \
  -not -path './venv/*' \
  | sort | head -300
```

Optional environment discovery, if safe:

```bash
python --version || true
node --version || true
uv --version || true
pytest --version || true
pnpm --version || true
npm --version || true
```

Run tests only after discovering the stack and documenting the command:

```bash
uv run pytest -q || pytest -q || true
pnpm test || npm test || true
```

If a command fails because dependencies are not installed, record it as a blocker; do not perform broad environment changes unless the human approves.

## Copy-paste prompt for Claude Code, plan first

```text
You are working on a repository that builds a hybrid human + AI code agent platform for Kaggle competitions and authorized CTF/lab/hackathon-style challenges.

Read these files first:
1. PROJECT_STATE.md
2. AGENTS.md
3. CLAUDE.md
4. docs/architecture/model-routing.md
5. Latest files in docs/adr/
6. docs/milestones/README.md if present
7. README.md and package/test configuration if present

Rules:
- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose, read, or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.
- Do not implement MVP-1 features yet.

Important terminology:
- Platform-development coding agents are external tools like Claude Code, ChatGPT, Cursor, and Lovable used to build this repository.
- Runtime competition code agents are agents launched by this platform to help human users work on competitions. The first runtime core is expected to use Claude Agent SDK, with future model routing. Kaggle runtime work is Python/notebook-first.
- The platform/control plane is expected to become TypeScript-first, with Python workers for competition execution.

Current task: M0-T001 project baseline.
Inspect the current repo and propose a minimal baseline update. Focus on docs, project memory, safety rules, branch/PR rules, test commands, and milestones. Do not implement the kca CLI, Supabase worker, Agent SDK loop, browser tools, or Kaggle submission features.

Return before editing:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Suggested tests/smoke checks.
- Any missing context.

Wait for my approval before editing.
```

## Copy-paste prompt for Claude Code, execute after approval

```text
/goal Execute docs/tasks/m0/M0-T001-project-baseline.md until:
- project docs distinguish platform-development coding agents from runtime competition code agents;
- GitHub repo files are documented as the source of truth across Claude Code, ChatGPT, Cursor, Lovable, and future tools;
- branch/PR/worktree rules and secret handling rules are documented;
- tests or smoke checks are documented, or blockers are recorded;
- docs/milestones/README.md exists or is updated with a high-level product plan;
- no MVP-1 feature implementation occurs;
- no secrets are read or committed;
- no Kaggle submission, kernel push, dataset upload, or remote competition side effect occurs;
- git diff only touches relevant baseline docs/settings files;
or stop after 40 turns and summarize blockers.
```

## Copy-paste prompt for Claude Code Web

Use only after committing and pushing this task spec.

```text
Execute docs/tasks/m0/M0-T001-project-baseline.md in plan-first mode.
Do not implement MVP-1 features.
Do not read secrets or perform remote competition side effects.
Return a plan first with intended files, risks, and tests. Wait for approval before editing.
```

## Copy-paste prompt for PR review

```text
Review the PR for M0-T001 project baseline.
Focus on:
- Whether docs match the actual repository.
- Whether the platform-development agent vs runtime competition agent distinction is clear.
- Whether GitHub repo files are treated as durable memory.
- Whether branch/PR/worktree and secret handling rules are clear.
- Whether the task stayed inside M0 scope and did not implement MVP-1 features.
- Whether tests/smoke checks are correctly documented.
- Whether any secrets, credentials, or irrelevant files were touched.
Do not edit files yet. Produce review comments first.
```
