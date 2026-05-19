# kaggle-code-agent Milestones

Status: proposed  
Created: 2026-05-16  
Scope: hybrid human + AI code competition platform

## Product thesis

`kaggle-code-agent` is a platform for human users to collaborate with AI code agents on code competitions and authorized challenge environments.

Initial focus: Kaggle competitions.  
Later extensions: authorized CTF/lab challenges, Devpost, hackathons, benchmark competitions, and other policy-scoped coding contests.

The platform should help a human user:

- discuss ideas and strategies;
- research competition rules, data, notebooks, papers, discussions, and baseline approaches;
- create, modify, test, and iterate code;
- track experiments, artifacts, results, submissions, and analysis;
- require human approval for external side effects such as Kaggle submissions or remote kernel pushes;
- summarize learnings and produce final writeups.

## Terminology: two meanings of "code agent"

This project uses two related but distinct agent concepts.

### 1. Platform-development coding agents

These are external AI tools used to build this repository.

Examples:

- Claude Code CLI / VS Code / Desktop / Web;
- ChatGPT Pro;
- Cursor;
- Lovable later, mainly for UI/product shell;
- GitHub Actions / Claude Code Web / Routines for cloud automation.

Role:

- write and review this product's source code;
- update docs, tasks, tests, and architecture decisions;
- run local tests and CI repair loops;
- open branches/PRs under human supervision.

Important rule: these tools do not share hidden memory reliably. GitHub repository files are the durable source of truth.

### 2. Runtime competition code agents

These are agents launched by the finished platform to help a human user compete.

Initial runtime direction:

- Claude Agent SDK as the first core worker/harness;
- isolated workspace/container per job;
- Python/notebook-first for Kaggle;
- TypeScript/Python service boundary depending on platform vs worker needs;
- future model router for Claude, GPT-style models, local vLLM/Ollama models, and specialized tools.

Runtime agents must operate under competition-specific policy, sandboxing, budget limits, approval gates, and audit logging.

## Architecture north star

```text
Human user / future UI
        ↓
TypeScript-first platform/control plane
  - project/session/job/task queue
  - policy and approval gates
  - discussion/research/analysis records
  - experiment/run/submission/artifact records
  - model router configuration
        ↓
Worker layer
  - Python-first Kaggle workers
  - Claude Agent SDK runtime sessions
  - notebooks/scripts/tools/kca wrappers
  - Playwright/browser/research tools
  - sandboxed execution and evaluation
        ↓
External systems
  - GitHub repo / branches / PRs
  - Supabase DB/storage/edge functions later
  - Kaggle API/CLI, only with approval for remote side effects
  - authorized CTF/lab/hackathon platforms under explicit policy
```

## Cross-cutting rules

- GitHub repo files are the project memory and source of truth.
- Each agent task gets a branch/worktree/PR when it modifies code.
- Main branch remains stable and protected.
- Do not allow multiple AI sessions to edit the same branch/files at the same time.
- No secrets in repo, prompts, logs, artifacts, or screenshots.
- Kaggle submissions, kernel pushes, dataset uploads, and other remote side effects require explicit human approval.
- CTF/lab work must be local/sandboxed or explicitly authorized.
- Every task prompt should include acceptance criteria and a stop condition.
- Every worker loop should have budget, turn, time, and side-effect limits.
- Tests and local validation should run before external submission.

## M0 / MVP-0: project baseline and memory discipline

Goal: make the repository safe and legible for multi-tool AI-assisted development.

### M0-T001 Project baseline

Deliverables:

- `docs/tasks/M0-T001-project-baseline.md` task spec.
- Clear distinction between platform-development coding agents and runtime competition code agents.
- Project docs state GitHub files are durable memory.
- Branch/PR/worktree rules documented.
- Secrets and remote side-effect rules documented.
- Test/smoke commands documented or blockers recorded.
- `docs/milestones.md` created.

Exit criteria:

- A new Claude Code session can read repo docs and understand what not to touch.
- A human can safely launch a small Claude Code task without ambiguous scope.

## M1 / MVP-1: local Kaggle tooling wrapper baseline

Goal: create a local-first wrapper layer that AI agents can call safely.

Planned tasks:

- Build `tools/kca/` CLI skeleton.
- Register 1-2 existing helper scripts, especially Python/IPython notebook conversion.
- Define stable wrapper commands for script-to-notebook and notebook-to-script conversion.
- Define artifact layout: `runs/<competition>/<run_id>/`.
- Add smoke tests for wrapper commands and artifact creation.
- Add or strengthen hooks so Kaggle submit/kernel push/upload commands require human approval.
- Document tool side-effect levels: read-only, local-write, remote-write, submission.

Non-goals:

- No autonomous competition agent loop yet.
- No real Kaggle submission in automated tests.
- No full Supabase integration yet.

Exit criteria:

- Claude Code can safely call `kca` wrappers for local operations.
- Dangerous remote operations are blocked or require approval.
- Local run artifacts are structured and testable.

## M2: Supabase/control plane foundation

Goal: define and prototype the persistent control plane.

Planned capabilities:

- Projects, competitions, sessions, jobs, tasks.
- Messages/discussions/research notes.
- Experiments, runs, metrics, artifacts, submissions.
- Human approvals and audit events.
- Worker job queue design.
- Storage strategy for large artifacts outside Postgres rows.

Likely stack:

- TypeScript-first platform service and future UI.
- Supabase DB/storage/edge functions/queues where useful.
- Python worker processes for Kaggle/runtime tasks.

Exit criteria:

- Schema and data model support MVP-1 artifacts and future worker jobs.
- A local/dev worker can record run events without needing product UI.

## M3: Python-first competition worker v0 ✓ done

Goal: run controlled local worker jobs from the platform queue.

Planned capabilities:

- Worker creates isolated workspace/worktree per job.
- Worker can call `kca` local tools.
- Worker records job status, logs, artifacts, metrics.
- Worker enforces max turns, max cost, max runtime, and configurable approval gates.
- Worker can run tests/evaluations and summarize results.

Runtime agent:

- `litellm.completion()` as the unified LLM provider interface (ADR-0004).
- Provider-agnostic: Claude, GPT-4o, local vLLM/Ollama selectable per job.
- Sampling params (temperature, top_p) set per job type in JobPolicy.

Workspace strategy (M3 interim):

- M3 creates worktrees inside the platform repo at `.workspaces/<job_id>/`.
- This is a temporary simplification to get the worker skeleton working.
- Full competition repo strategy (ADR-0009) is implemented in M4.

Approval gates:

- Configurable per project/competition (ADR-0006).
- Default: allow for kaggle_submit, kernel_push, git_push.
- Human intervention reserved for major direction decisions.

Exit criteria:

- A job runs locally: prompt → workspace → LLM tool loop → kca tool call → recorded result.
- Budget limits (turns, cost, runtime) enforced and logged.
- Approval gate fires and records a human_decisions row when configured.

## M4: Kaggle competition workflow v0

Goal: support a full Kaggle baseline loop with proper competition repo isolation.

### M4 task sequence

| Task | Description | Depends on |
|---|---|---|
| M4-T000 | `pyproject.toml` pip-installable kca entry point | — |
| M4-T001 | Migration 0004: competition repo cols + experiments/runs/submissions tables | — |
| M4-T002 | DB layer: competition, experiment, run, submission functions | T001 |
| M4-T003 | `kca competition register/clone/list` subcommands | T002 |
| M4-T004 | `kca workspace init --repo` flag + `kca run init/record-metric/list` | T002 |
| M4-T005 | `scripts/run_job.py` competition repo lifecycle | T002, T003, T004 |
| M4-T006 | Configurable approval gate policy resolution (ADR-0006) | — |
| M4-T007 | Wire real `kaggle` CLI into `kca kaggle` commands | T006 |
| M4-T008 | TC-1 Titanic end-to-end dry-run loop | T003–T007 |
| M4-T009 | `tests/test_m4_smoke.py` (8–12 tests, no API/DB/credentials) | T003–T007 |
| M4-T010 | M4 exit criteria validation + `docs/m4-final-review.md` | all |

Planned capabilities:

- **Competition repo management** (ADR-0009):
  - `kca competition register --slug <slug> --repo-url <url>`
  - `kca competition clone --slug <slug>` — git clone to local_clone_path
  - `kca workspace init` gains `--repo <path>` flag (worktree inside competition repo)
  - Migration 0004: `repo_url`, `default_branch`, `local_clone_path` on `competitions`
  - `pyproject.toml` in platform repo so `pip install -e .` makes kca available in competition repos
- Competition metadata and rule notes.
- Data download/checksum policy.
- Baseline notebook/script generation from research brief.
- Local validation/CV strategy (cross-validation harness).
- Experiment tracking: branch per hypothesis, run per execution, metrics in DB.
- Leaderboard result recording (public LB score vs CV).
- Submission file format validation.
- Kernel push and kaggle submit via configured approval policy.

Regression test competitions (TC-1 through TC-4 from `docs/testing/competition-test-cases.md`):
- TC-1 Titanic — validates full L1 loop end-to-end.
- TC-2 House Prices — validates feature engineering iteration.
- TC-3 Digit Recognizer — validates kernel push dry-run.
- TC-4 Flower Classification with TPUs — validates full L3 complexity.

Exit criteria:

- Platform can run a Titanic end-to-end loop: research → implement → experiment → prepare_submission.
- Each competition runs in its own GitHub repo with experiment branches.
- Submission is prepared and validated locally; submit job executes per approval policy.

## M5: research and browser workflow

Goal: add research, webpage reading, and browser-visible analysis loops.

Planned capabilities:

- Browser/page reading via Playwright or MCP-compatible browser tooling.
- Research notes with citations/source URLs and trust labels.
- Competition rules extraction.
- Notebook/discussion/paper summarization.
- Browser screenshots or DOM snapshots stored as artifacts when useful.

Exit criteria:

- Agent can research competition context and produce auditable notes.
- Research output is linked to experiment decisions.

## M6: model router and multi-agent review

Goal: route tasks by difficulty, cost, and risk.

Planned routing examples:

- Main implementation/debug: Claude Sonnet/Opus via Agent SDK.
- Independent code/strategy review: GPT-style model or another Claude session.
- Low-cost summarization/log triage: local vLLM/Ollama model where adequate.
- Final high-value review: strongest available model, human-approved budget.

Exit criteria:

- Model choice is explicit, logged, and policy-controlled.
- Local/cheap models can be used for bounded support tasks without weakening safety gates.

## M7: product UI shell

Goal: expose the control plane through a human-friendly interface.

Planned capabilities:

- Project/competition dashboard.
- Prompt/task queue.
- Agent run logs and event timeline.
- Research notes and discussions.
- Experiment/run table.
- Approval inbox for submissions/remote actions.
- Artifact browser.

Likely approach:

- TypeScript-first app.
- Lovable may be used later for product shell, dashboard, or management UI.
- UI reads/writes Supabase-backed data and never bypasses policy gates.

Exit criteria:

- Human can monitor and approve/reject worker actions through UI.

## M8: authorized CTF/lab workflow

Goal: support CTF-style challenges only inside explicit authorization boundaries.

Planned capabilities:

- Challenge scope and authorization metadata.
- Local container/lab-only execution.
- Solver script generation and testing.
- Writeup generation.
- Hard policy blocks for external scanning, real targets, credential theft, persistence, or unsafe actions.

Exit criteria:

- CTF workflow is useful for local/sandbox labs and safely refuses out-of-scope activity.

## M9: Devpost/hackathon workflow

Goal: generalize competition policy modules beyond Kaggle and CTF.

Planned capabilities:

- Hackathon rules and deadline tracking.
- Team discussion and idea board.
- App prototype workflows.
- Demo/video/readme generation.
- Submission checklist and approval gates.

Exit criteria:

- The same platform can represent different competition policies without changing worker core logic.

## M10: evaluation, reliability, and regression suite

Goal: measure whether the platform improves over time.

Planned test cases:

- Tool smoke tests.
- Classic Kaggle practice tasks.
- Notebook/kernel dry-run workflows.
- Reasoning-heavy Kaggle-style test cases.
- Authorized local CTF labs.
- Regression comparisons across Claude/GPT/local model routes.

Metrics:

- Task completion rate.
- Test pass rate.
- Cost per successful run.
- Human intervention count.
- Approval gate correctness.
- Artifact/log completeness.
- Regression failure rate.

Exit criteria:

- New platform changes can be evaluated against known workflows before use in real competitions.

## Open design questions

- Should the first platform service be TypeScript-only, or TypeScript API + Python worker from day one?
- Which Supabase queue/job mechanism should be used first?
- What is the minimal local sandbox acceptable for Kaggle worker experiments?
- How should existing helper scripts be wrapped: direct CLI, Python package, or MCP/custom tools?
- What is the first Kaggle practice competition for regression testing?
- What policy schema best represents Kaggle vs CTF vs hackathon side effects?
- What model-router interface is stable enough for MVP without overengineering?

## Suggested next tasks after M0-T001

1. `M1-T001-kca-cli-skeleton.md`
   - Create `tools/kca/` CLI skeleton.
   - Register 1-2 existing helper scripts.
   - Add smoke tests.

2. `M1-T002-artifact-layout.md`
   - Define `runs/<competition>/<run_id>/`.
   - Add run metadata schema and sample artifact.

3. `M1-T003-approval-hooks.md`
   - Strengthen hooks/settings to require approval for Kaggle submissions, kernel pushes, dataset uploads, and destructive commands.

4. `M2-T001-supabase-control-plane-schema.md`
   - Convert current Supabase ideas into an initial migration and local development notes.

5. `M3-T001-agent-sdk-worker-spike.md`
   - Minimal Agent SDK worker spike in sandbox/workspace, no real competition side effects.
