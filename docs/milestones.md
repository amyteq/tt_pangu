# kaggle-code-agent Milestones

Status: M6 done, M7 in planning  
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

## Source of truth

**GitHub repo + Claude Code + CI + Supabase migrations.**

All product source code, migrations, tests, architecture decisions, and task specs live in this repository. AI tools do not share hidden memory reliably across sessions or products. Claude Code is the primary development environment for all layers: CLI, backend, UI shell, and worker.

Lovable may be used for visual prototyping or landing-page mockups only. It is not the source of truth for schema, migrations, agent runners, or any backend logic.

## Terminology: two meanings of "code agent"

This project uses two related but distinct agent concepts.

### 1. Platform-development coding agents

These are external AI tools used to build this repository.

Examples:

- Claude Code CLI / VS Code / Desktop / Web (primary);
- ChatGPT Pro / Cursor (supplementary);
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

## Milestone final-review protocol

After every milestone final review, before marking done:

1. Update `PROJECT_STATE.md` — set current milestone, summarize open decisions, and record any new known blockers.
2. Update `README.md` current milestone section to name the new active milestone and goal.
3. Update `docs/milestones.md` — mark the finished milestone `✓ done`, add a one-line summary of what landed, and note any follow-ups carried forward.

---

## M0 / MVP-0: project baseline and memory discipline ✓ done

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

---

## M1 / MVP-1: local Kaggle tooling wrapper baseline ✓ done

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

---

## M2: Supabase/control plane foundation ✓ done

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

---

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

---

## M4: Kaggle competition workflow v0 ✓ done

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

---

## M5: research and browser workflow ✓ done

Goal: add research, webpage reading, and browser-visible analysis loops,
plus clear the M4 follow-ups (kaggle download checksums, resume paused jobs,
model routing, CI).

### M5 task sequence

| Task | Description | Depends on |
|---|---|---|
| M5-T000 | Migration 0005 — research_items extensions + research_citations table | — |
| M5-T001 | DB layer — research / artifact / citation helpers | T000 |
| M5-T002 | `tools/kca/research_fetch.py` — lightweight HTTP + opt-in Playwright | — |
| M5-T003 | `kca research add/fetch/list/show/cite` CLI + `external_fetch` gate | T001, T002 |
| M5-T004 | `kca kaggle download --resume` + `kca kaggle verify` with sha256 manifest | — |
| M5-T005 | Resume paused jobs via `scripts/run_job.py --job-id` after approve | — |
| M5-T006 | Model routing per job type (`src/worker/routing.py`, ADR-0010) | — |
| M5-T007 | `.github/workflows/test.yml` — no-db + live-db + lint | — |
| M5-T008 | TC-2 House Prices end-to-end (RMSLE, two-experiment loop) | T003, T004 |
| M5-T009 | `tests/test_m5_smoke.py` (10–12 tests) | T002, T003, T004, T006 |
| M5-T010 | M5 exit criteria + `docs/m5-final-review.md` | all |

Planned capabilities:

- Browser/page reading via lightweight HTTP + readability (default) with an
  opt-in Playwright path for JS-heavy pages.
- Research notes with citations/source URLs and trust labels recorded in
  `research_items`; per-run citations in `research_citations`.
- `external_fetch` approval gate per ADR-0006; default allow, opt-in tighten.
- Browser screenshots or DOM snapshots stored under `artifacts/research/`
  and linked from the DB row.
- Kaggle data integrity via sha256 manifest + `--resume` + `kca kaggle verify`.
- Paused-job resume via `scripts/run_job.py --job-id` after `kca decisions
  approve` — re-uses budget tracker state from `agent_job_events`.
- Per-job-type model routing (ADR-0010): Sonnet for implement/experiment,
  Opus for eval/analysis, Haiku for triage; CLI override always wins.
- CI on every PR runs `no-db` + `lint` (and `live-db` for trusted PRs).

Exit criteria:

- Agent can research competition context and produce auditable notes
  linked from experiment runs.
- `kca kaggle download --resume` + `verify` survive a tampered file.
- A paused job resumes after approval and finishes with correct
  `turns_used` accumulation.
- TC-2 House Prices loop completes; `cv_rmsle` for the log1p experiment is
  lower than the baseline.
- Full test suite passes with and without `SUPABASE_DB_URL`.

---

## M6: multi-agent review + OTEL telemetry + local-model layer ✓ done

Goal: harden the M3–M5 worker with an independent reviewer agent, end-to-end
OpenTelemetry tracing, and a local-model layer that routes log-triage /
summarisation jobs to user-owned GPU hosts before paying for cloud tokens.

Planned capabilities:

- Reviewer agent (sync mode) fires before high-stakes ops
  (`kaggle_submit`, `supabase_migrate`, `git_force_push`, `dataset_upload`,
  `delete_artifact`). Verdict `approve | reject | abstain` lands in a new
  `agent_reviews` table; `approve` satisfies the matching approval gate
  without human intervention, `reject` escalates (default) or fails the
  job, `abstain` falls through to the existing human-decisions flow.
- Local-model layer (`src/worker/local_model.py`) talks to vLLM / Ollama
  endpoints on the user's GPU hosts (`snorlax` RTX 4090, `may` RTX 3090)
  via OpenAI-compatible HTTP. Numbered-slot env config
  (`KCA_LOCAL_ENDPOINT_<n>_*`), priority ordering, a TTL-cached probe, and
  a `KCA_LOCAL_FALLBACK_MODEL` cloud fallback.
- New job types `log_triage` and `summarise` route to the local layer by
  default; `kca local probe / pick / triage` surfaces endpoint state.
- OTEL instrumentation per ADR-0007 with three exporters: stderr (dev),
  SQLite (`.agent/telemetry.sqlite`), and Supabase
  (`agent_telemetry_spans`). Spans cover job / turn / tool / reviewer /
  local-probe.
- TC-3 Spaceship Titanic exercises the reviewer-gate path end-to-end on a
  binary-classification submission flow.

Exit criteria: all met. See `docs/m6-final-review.md`.

---

## M7: KCA CLI architecture — command / skill / tool / job / permission policy

Goal: implement the full KCA command/skill/tool/job architecture so the platform
has a stable, inspectable CLI that can drive agent workflows, replace ad-hoc
`python tools/kca/kca.py` calls, and enforce structured permission decisions.

This is distinct from the product UI shell (M8): M7 is operator/developer-facing
and headless. The UI in M8 will call into the same CLI/API surface.

See `docs/meeting-notes/2026-05-21-r1.md` §1–3 for full design rationale.

### Four-layer model

| Layer | Description |
|---|---|
| **Command** | Deterministic CLI/API entry points for operators (`kca job run`, `kca decision approve`). |
| **Skill** | Agent-facing workflow recipes stored under `.kca/skills/<name>/SKILL.md` with YAML frontmatter. Callable via `kca skill run <name>` or slash-style invocation. |
| **Tool** | Executable actions with input/output schema, timeout, permission label, sandbox metadata, and audit logging. |
| **Job** | Durable records that run a skill through the agent loop with budget, turn, cost, runtime limits, and decision gates. |

### M7 task sequence

| Task | Description | Depends on |
|---|---|---|
| M7-T000 | Audit + repair `.github/workflows/` — fix failing CI checks, add no-db + lint jobs | — |
| M7-T001 | Skill loader: read `.kca/skills/<name>/SKILL.md` with YAML frontmatter; argument substitution | — |
| M7-T002 | Command registry: register KCA CLI subcommands declaratively | T001 |
| M7-T003 | Tool registry: tool metadata, approval policy labels, sandbox metadata | T001 |
| M7-T004 | Permission policy layer: allow/ask/deny resolution with structured JSON policy records | T003 |
| M7-T005 | Slash-style invocation: `kca skill run <name> [args] [--dry-run]` shows permissions + rendered prompt | T001, T004 |
| M7-T006 | Audit logging: record every tool execution in `agent_job_events` with policy decision | T004 |
| M7-T007 | Seed `.kca/skills/` with `run-milestone`, `triage-log`, `prepare-submission`, `review-pr` | T001 |
| M7-T008 | `tests/test_m7_smoke.py`: skill parsing, arg substitution, permission resolution, command registry, decision gates | T001–T006 |
| M7-T009 | Documentation: `docs/architecture/kca-cli-architecture.md` explaining Commands vs Skills vs Tools vs Jobs | all |
| M7-T010 | M7 exit criteria validation + `docs/m7-final-review.md` | all |

### Permission policy design

Runtime agent permissions are data, not ad-hoc prompts:

```json
{
  "operation": "kaggle.submit",
  "default_decision": "ask",
  "reason": "External competition submission",
  "allowed_in_modes": ["human-approved", "competition-finalization"],
  "audit_required": true
}
```

Allow by default: edit workspace files, run tests/benchmark, create artifacts,
summarize logs, call LiteLLM/local models, create branch, commit, create PR.

Decision gate: submit to Kaggle, merge PR, publish dataset/kernel, apply
remote Supabase migration, spend above budget threshold, change model tier,
change competition direction/objective.

Deny: read secrets, write outside workspace, sudo/root, rm outside workspace,
drop database/schema, force push, network exfiltration.

### Recommended directory layout

```text
.kca/
  skills/
    run-milestone/SKILL.md
    triage-log/SKILL.md
    prepare-submission/SKILL.md
    review-pr/SKILL.md
  tools/tools.yaml
  permissions/
    default.yaml
    permissive-dev.yaml
    competition-runner.yaml

tools/kca/
  kca.py
  commands/
    job.py  skill.py  tool.py  decision.py
    workspace.py  kaggle.py  supabase.py
  agent/
    runner.py  skill_loader.py  tool_executor.py
    permission_policy.py  audit.py
```

Exit criteria:

- `kca skill list` shows available skills from `.kca/skills/`.
- `kca skill show <name>` prints parsed metadata and body.
- `kca skill run <name> ... --dry-run` prints planned tool permissions and rendered prompt without executing.
- Permission policy resolves allow/ask/deny for any (operation, mode) pair.
- Audit log records every tool execution with policy decision.
- `.github/workflows/` CI passes on main branch (no-db + lint at minimum).
- `tests/test_m7_smoke.py` passes without API keys or DB.
- Documentation explains Commands vs Skills vs Tools vs Jobs.

---

## M8: product UI shell

Goal: expose the control plane through a human-friendly interface, built and
maintained in Claude Code with this repository as source of truth.

Planned capabilities:

- Project/competition dashboard.
- Prompt/task queue.
- Agent run logs and event timeline.
- Research notes and discussions.
- Experiment/run table.
- Approval inbox for submissions/remote actions.
- Artifact browser.
- Decision gate UI: shows `operation`, `cv_score`, `cost_so_far`, artifact,
  and Approve / Reject / Ask agent to improve actions.

Stack:

- TypeScript-first React app (Next.js or Vite/React).
- Supabase client for data; never bypasses policy gates.
- Developed in Claude Code — same repo, same migrations, same CI.

Exit criteria:

- Human can monitor and approve/reject worker actions through UI.
- Decision gate shows current CV score and artifact before approve/reject.
- Reviewer verdicts and telemetry spans are visible per run.

---

## M9: live end-to-end regression test — Spaceship Titanic

Goal: validate the full platform loop with a real Kaggle submission for
[Spaceship Titanic](https://www.kaggle.com/competitions/spaceship-titanic/overview)
(binary classification, public leaderboard, no cash prize, safe for automated
dry-run + 1 real submission under human approval).

This milestone is the first time a real `kaggle competitions submit` runs
through the approved KCA approval gate and records a public LB score in the DB.

### M9 task sequence

| Task | Description | Depends on |
|---|---|---|
| M9-T000 | Verify Kaggle credentials and competition acceptance in env | — |
| M9-T001 | Download Spaceship Titanic data, verify sha256 manifest | T000 |
| M9-T002 | Agent worker loop: research → baseline LR → CV → submission.csv | T001 |
| M9-T003 | Reviewer gate fires; human approves `kaggle_submit` | T002 |
| M9-T004 | Real submission; record public LB score in `runs` table | T003 |
| M9-T005 | Second experiment (HGB / feature engineering); CV improvement | T004 |
| M9-T006 | Regression assertions: CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB score recorded | T005 |
| M9-T007 | `tests/test_m9_e2e.py` (dry-run path without real submission) | T002, T003 |
| M9-T008 | M9 exit criteria validation + `docs/m9-final-review.md` | all |

Exit criteria:

- Data downloaded and verified (sha256 manifest, no corruption).
- Agent worker completes research → baseline → CV → submission.csv without human intervention in allowed operations.
- Reviewer gate fires and records verdict in `agent_reviews` before `kaggle_submit`.
- Human approves submission via `kca decision approve`.
- Public LB score recorded in `runs` table; `kca run list` shows it.
- Second experiment achieves measurably higher CV than baseline.
- `tests/test_m9_e2e.py` (dry-run) passes in CI without credentials.

---

## M10: authorized CTF/lab workflow

Goal: support CTF-style challenges only inside explicit authorization boundaries.

Planned capabilities:

- Challenge scope and authorization metadata.
- Local container/lab-only execution.
- Solver script generation and testing.
- Writeup generation.
- Hard policy blocks for external scanning, real targets, credential theft, persistence, or unsafe actions.

Exit criteria:

- CTF workflow is useful for local/sandbox labs and safely refuses out-of-scope activity.

---

## M11: Devpost/hackathon workflow

Goal: generalize competition policy modules beyond Kaggle and CTF.

Planned capabilities:

- Hackathon rules and deadline tracking.
- Team discussion and idea board.
- App prototype workflows.
- Demo/video/readme generation.
- Submission checklist and approval gates.

Exit criteria:

- The same platform can represent different competition policies without changing worker core logic.

---

## M12: evaluation, reliability, and regression suite

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

---

## Open design questions

- Should the first platform UI service be TypeScript-only, or TypeScript API + Python worker from day one?
- Which Supabase queue/job mechanism should be used first?
- What is the minimal local sandbox acceptable for Kaggle worker experiments?
- What policy schema best represents Kaggle vs CTF vs hackathon side effects?
- What model-router interface is stable enough for MVP without overengineering?
