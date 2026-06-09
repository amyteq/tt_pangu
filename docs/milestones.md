# kaggle-code-agent Milestones

Status: M0–M10 done; M9.2 ✓ done (/save-log operator-tooling skill); M11 in planning (authorized CTF/lab workflow)  
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
4. Write `docs/handoffs/m{x}-handoff.md` — a per-milestone, ready-to-paste context prompt for the next AI tool / session that will start M{x+1}. Use `docs/handoff-prompt.md` as the canonical template; populate the "State at handoff", "Read these files first", and "Current task" sections from the M{x} final review and the M{x+1} entry in this file. The generic `docs/handoff-prompt.md` stays as the template; the per-milestone instances live under `docs/handoffs/`.

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

## M7: KCA CLI architecture — command / skill / tool / job / permission policy ✓ done

_Shipped 2026-05-21: four-layer CLI scaffold (command/skill/tool/job), skill loader, tool registry (16 tools), three permission profiles, `kca skill list/show/run` + `kca tool list/audit/doctor`, four seed skills, audit JSONL, 15 smoke tests, and `docs/architecture/kca-cli-architecture.md`. 28/28 exit checks PASS — see `docs/m7-final-review.md`._

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

## M8: product UI shell ✓ done

_Shipped 2026-05-23. See `docs/m8-final-review.md` (28/28 checks PASS).
Summary: Vite+React+TS UI on `ui/`; typed Supabase read client;
decision_api FastAPI service; Approval Inbox + Decision Gate; OTEL
swim-lane Run Timeline; `agent_tool_audit` table (migration 0007);
SKILL.md JSON-Schema gate; ToolSpec enforcement in
`src/worker/worker.py::_tool_call`; 13 vitest + 4 Playwright + 13 M8
Python smoke tests; UI/lint CI job; live-db CI gated on push/main and
same-repo PRs._

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

## M8.5: pre-M9 hardening ✓ done

Goal: get CI back to green, give humans and Claude Code a shared GitHub
Issues / PR / labels interface, and draft M9 — all before any M9 code
runs.

### M8.5 task sequence

| Task | Description | Result |
|---|---|---|
| M8.5-T001 | CI repair — Python deps + `kca skill` registration + pnpm workspace | PR #4 (`2d4f0cc`) |
| M8.5-T002 | Engineering practice docs + GitHub labels / issue forms / PR template + agents/skills + sandbox / hook revision | PR #5 (`5497b9b`) |
| M8.5-T003 | M9 planning only — `docs/m9-loop-prompts.md` + nine `docs/tasks/M9-T*.md` specs | PR #6 (`cade09f`) |

Exit criteria:

- CI green on `no-db pytest`, `live-db pytest`, `ruff`, `ui build + lint
  + typecheck + test` for all three M8.5 PRs.
- `.github/labels.yml` synced to `origin` (33 labels visible).
- `docs/engineering-practice.md`, `AGENTS.md`, `CLAUDE.md` describe the
  AI pickup rule + remote-write approval requirement.
- `docs/m9-loop-prompts.md` covers the 10 M9 planning topics; each
  non-trivial Loop Prompt has a matching task spec.
- No M9 code implemented.

See `docs/m8_5-final-review.md` for the full validation roll-up.

---

## M9: live end-to-end regression test — Spaceship Titanic ✓ done

_Shipped 2026-05-24. See `docs/m9-final-review.md` (30 PASS / 1 SKIP / 0 FAIL).
The SKIP is UI pnpm gates (M9 did not modify UI; covered by M8.5 green
state on `main`).

Summary: first live end-to-end Kaggle regression. LR baseline CV
**0.79144 ±0.0086**; HGB + FE CV **0.81192 ±0.00753** (+0.02048). One
approved real Kaggle submission: public LB **0.78676**
(`external_submission_id=52955657`,
`submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`). New scripts:
`baseline_lr_spaceship.py`, `hgb_fe_spaceship.py`,
`m9_t003_drive_reviewer_gate.py`. New tests: `tests/test_m9_smoke.py`
(4 DB-gated assertions) and `tests/test_m9_e2e.py` (5 dry-run tests,
0 net / 0 DB / 0 creds). `data/spaceship-titanic/manifest.json` with
4 sha256 entries (raw data gitignored)._

Goal: validate the full platform loop with a real Kaggle submission for
[Spaceship Titanic](https://www.kaggle.com/competitions/spaceship-titanic/overview)
(binary classification, public leaderboard, no cash prize, safe for automated
dry-run + 1 real submission under human approval).

This milestone is the first time a real `kaggle competitions submit` runs
through the approved KCA approval gate and records a public LB score in the DB.

### M9 task sequence

| Task | Description | Result |
|---|---|---|
| M9-T000 | Verify Kaggle credentials and competition acceptance in env | PASS — `competitions.id=b6059835-…` |
| M9-T001 | Download Spaceship Titanic data, verify sha256 manifest | PASS — `manifest.json` with 4 sha256 entries |
| M9-T002 | Agent worker loop: research → baseline LR → CV → submission.csv | PASS — CV 0.79144 |
| M9-T003 | Reviewer gate fires; human approves `kaggle_submit` | PASS — `agent_reviews.id=a7208e96-…` + `human_decisions.id=43e116bb-…` |
| M9-T004 | Real submission; record public LB score in `submissions` table | PASS — LB **0.78676** |
| M9-T005 | Second experiment (HGB / feature engineering); CV improvement | PASS — CV 0.81192 (+0.02048) |
| M9-T006 | Regression assertions: CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB recorded | PASS — all four assertions |
| M9-T007 | `tests/test_m9_e2e.py` (dry-run path without real submission) | PASS — 5 tests, 1.14s |
| M9-T008 | M9 exit criteria validation + `docs/m9-final-review.md` | PASS — this milestone |

Exit criteria — all met:

- Data downloaded and verified (sha256 manifest, no corruption).
- Agent worker completes research → baseline → CV → submission.csv without human intervention in allowed operations.
- Reviewer gate fires and records verdict in `agent_reviews` before `kaggle_submit`.
- Human approves submission via `kca decisions approve`.
- Public LB score recorded for the M9-T004 submission; `kca run list --competition spaceship-titanic --json` shows both runs with CV scores.
- Second experiment achieves measurably higher CV than baseline (+0.02048).
- `tests/test_m9_e2e.py` (dry-run) passes in CI without credentials.

Post-M9 follow-ups (cross-cutting items A–E; see
`docs/handoffs/m9-handoff.md`). These are tracked as their own issues
and may land in parallel with M10. Issue #11 (item B) is a **hard
pre-req for M10-T007**; the rest are soft pre-reqs.

1. **A** — `competitions.repo_url` schema drift (`type:bug`, `area:kaggle`).
2. **B** — Secrets-file hygiene in pytest subprocess (issue #11, P0; M10-T007 blocker).
3. **C** — `decision_api`: no `GET /decisions` endpoint (`type:feature`, `area:supabase`).
4. **D** — `reviewer_decision` literal event_type alignment (`type:docs`, `area:worker`).
5. **E** — Migration 0004 optional `submissions` columns not applied to local DB (`type:bug`, `area:supabase`).

---

## M9.2: `/save-log` skill — Claude Code session transcript export ✓ done

_Shipped 2026-05-26. See `docs/m9_2-final-review.md` (26 PASS / 0 SKIP / 0 FAIL)._
_`/save-log <name|id>` Claude Code project skill landed at `.claude/skills/save-log/SKILL.md`
backed by `scripts/save_claude_session_log.py` (16 KB, chmod +x). Skill is
operator-only (`disable-model-invocation: true`). Renders Claude Code transcript
JSONL into Markdown via `uvx claude-code-log@latest --detail low --format md
--compact` and refuses to write if any of ten secret-like patterns match
(Anthropic / OpenAI / GitHub / Kaggle / Supabase / private-key / generic
assignment). Positive smoke wrote `docs/logs/M9.md` (103 KB, 1284 lines, 0 ANSI);
three negative paths (running session, ambiguous selector, secret pattern) all
refused as designed; `--allow-secret-like` override works. `docs/logs/`
trackability secured by a `!docs/logs/**` carve-out after the existing
`**/logs/*` rule._

_Operator-tooling milestone; sat between M9 (done) and M10 (in planning).
Did not renumber M10–M13._

Goal: add a `/save-log <name|id>` Claude Code project skill that exports
a stopped or completed background-session transcript to
`docs/logs/<session-name>.md` via `claude-code-log` (run through
`uvx`). Canonical spec: `docs/meeting-notes/2026-05-26-r1.md`.

The motivation is recorded in the meeting notes: `claude logs
<session-id>` only emits terminal output with ANSI cursor/control
sequences; clean Markdown for handoff packs must come from the
transcript JSONL under `~/.claude/projects/`. The skill is operator-
local (`disable-model-invocation: true`), backed by a Python script
with a nine-pattern secret-scan refusal, terminal-state gate, and
atomic overwrite.

### M9.2 task sequence

| Task | Description |
|---|---|
| M9.2-T000 | Create `.claude/skills/save-log/SKILL.md`, `scripts/save_claude_session_log.py`, `docs/logs/.gitkeep`. Implement the script verbatim from meeting-notes §3. Confirm `--help` parses, `ruff` clean, `uvx claude-code-log@latest --help` reachable. No real export. |
| M9.2-T001 | Smoke against a real stopped/completed session + three negative paths (running session refusal, ambiguous-selector refusal, secret-pattern refusal with `--allow-secret-like` override). Add `/save-log` mention to `README.md`. Confirm `docs/logs/` is **not** gitignored. |
| M9.2-T002 | M9.2 exit criteria + `docs/m9_2-final-review.md` + milestones / PROJECT_STATE / README updates + `docs/handoffs/m9_2-handoff.md`. Run `worktree-milestone-pr` to commit per-Loop-Prompt, push, open PR. |

Each task's full scope, acceptance criteria, allowed/forbidden paths,
and closeout format live in the matching `docs/tasks/M9_2-T00N-*.md`
spec. Loop Prompts: `docs/m9_2-loop-prompts.md`.

Exit criteria (full list in `docs/m9_2-loop-prompts.md`):

- `.claude/skills/save-log/SKILL.md`, `scripts/save_claude_session_log.py`,
  `docs/logs/.gitkeep` exist; `ruff` clean; `--help` prints the four
  flags.
- A real `/save-log <name|id>` export against a stopped/completed
  session writes `docs/logs/<name>.md` with the header block and an
  ANSI-free Markdown body.
- Running-session, ambiguous-selector, and secret-pattern refusals
  all exit non-zero with the expected messages; `--allow-secret-like`
  override works.
- `docs/logs/` is not in `.gitignore`.
- `docs/m9_2-final-review.md` exists and follows the M9 / M8.5
  layout.
- `python -m pytest tests/ -q` still passes (no new tests required;
  M9.2 is operator tooling).

Out-of-scope follow-ups (file as issues if surfaced):

- A `/save-log --all` mode that exports every terminal-state project
  session in one shot.
- Promoting `docs/logs/<name>.md` exports into Supabase
  `agent_run_artifacts` (would need a migration; out of scope here).
- A `claude-code-log` Markdown post-processor that strips tool-call
  noise or redacts file paths above an opt-in threshold.

---

## M9.3: memory-promotion + design-archaeology skills ✓ done

_Sub-milestone shipped 2026-05-26. Replaces the broader M9.1 plan
(unbuilt) and retires `docs/m9_1-loop-prompts.md` with a pointer
notice. Loop prompts: `docs/m9_3-loop-prompts.md`._

Goal: ship two project skills that harden the discipline around legacy
migrations and canonical-memory updates — both surfaced as recurring
gaps from M7–M9.

- `design-archaeology` — forces a structured 10-section pre-implementation
  report for legacy migrations (workflows, hidden assumptions, owners,
  state files, config dimensions, side effects, preserve/change/drop,
  open questions, parity test sketch, evidence). Read-only on the
  legacy artifact tree; blocks code work until `§8` is acknowledged.
  Canonical worked example: `docs/archaeology/kkr.md` (kkr.py + kkr.yaml).
- `memory-promotion` — distils GitHub issue/PR/review/meeting-notes
  content into propose-only patches against canonical memory
  (`PROJECT_STATE.md`, `docs/milestones.md`, `docs/handoffs/`,
  `docs/adr/`). Writes proposals under `docs/proposals/` with an
  unchecked human-approval checkbox; never auto-applies.

Codified by:

- [`docs/adr/0015-memory-promotion-model.md`](adr/0015-memory-promotion-model.md) — canonical memory list (the four files above), propose-only rule, boundary with `memory/` (user auto-memory; out of scope).
- [`docs/architecture/memory-promotion.md`](architecture/memory-promotion.md) — data-flow (evidence → extraction → proposal → human gate → canonical) with ASCII diagram.
- [`docs/architecture/design-archaeology.md`](architecture/design-archaeology.md) — rationale, asymmetric-cost argument, worked-example pointer.

Dogfooded in T003:

- `docs/archaeology/kkr.md` — real archaeology of `tools/legacy/kkr.py` + `kkr.yaml`; surfaces multi-owner support (`harrysun2006` / `firefly2006`) and the `_load_env_for_owner` three-step resolution as preserve-candidates; `§8` Q1 is "should KCA M10+ re-introduce multi-account quota pooling as a first-class feature?".
- `docs/proposals/memory-2026-05-26-m10-pr18.md` — memory-promotion proposal derived from PR #18 (M10 planning); confirms the new `## Related issues` per-task-spec convention; one proposed PROJECT_STATE.md patch (unchecked).

Deferred to M9.4+ (not scheduled): session-closeout skill, claude_export_session.py, channels bridge, kca-agent-pack migration, bespoke agent wrappers. See the retirement notice in `docs/m9_1-loop-prompts.md`.

### M9.3 task sequence

| Task | Description |
|---|---|
| M9.3-T001 | Ship `.claude/skills/design-archaeology/SKILL.md` (10-section template, 7 Must / Must-not rules, worked-example pointer). |
| M9.3-T002 | Ship `.claude/skills/memory-promotion/SKILL.md` (4-phase workflow, 7 extraction keys, 7 Must / Must-not rules) + ADR-0015 + `docs/architecture/memory-promotion.md` + `docs/proposals/` staging. |
| M9.3-T003 | Dogfood — write `docs/archaeology/kkr.md` + `docs/proposals/memory-2026-05-26-m10-pr18.md` + `docs/architecture/design-archaeology.md`; retire `docs/m9_1-loop-prompts.md`; milestone close. |

---

## M10: notebook-submission regression — Petals to the Metal ✓ done

_Shipped 2026-05-28 (issue #12 decisions confirmed 2026-05-24). Branch
`worktree-m10-petals-to-the-metal`. Validation matrix **26 PASS / 1 SKIP
/ 0 FAIL** (see `docs/m10-final-review.md`). The kernel-push loop ran
end-to-end correctly under the approval gates — the milestone's
acceptance criterion. **One material deviation: no public LB score was
recorded.** The single human-approved real `kaggle kernels push` was
executed (issue #34), but push #1 stalled QUEUED ~66 min and never ran,
and the approved re-push #2 errored on a missing `metadata.kernelspec`
(root cause fixed in `tools/legacy/py2nb.py`; notebook now push-ready).
Per the issue #12 single-push policy the human chose "accept and
continue"; `submissions.id=03b5d080-…` exists with `public_score` NULL.
No leaderboard pollution occurred. Re-push tracked by issues #34 / #35.
Issue #11 (dotenv-leak / LB pollution; M9 follow-up B) was fixed and
CLOSED during M10 as T007's hard pre-req._

### M10 per-task results

| Task | Description | Result |
|---|---|---|
| M10-T000 | Kaggle creds reachable (booleans only) + `tpu-getting-started` registered (`competition_id=4c69e842-…`) | PASS |
| M10-T001 | `data/tpu-getting-started/manifest.json` (193 entries, remote-only, 4 image-size variants); raw TFRecords gitignored | PASS |
| M10-T002 | Baseline MobileNetV2 notebook; `experiment_run_id=830fc32f-…`; local-slice holdout **0.4310** (full-dataset ref ~0.7707) | PASS |
| M10-T003 | Reviewer gate fired for `kernel_push`; `agent_reviews=a6f47954-…` + `human_decisions=b47e2f16-…` (dry approval) | PASS |
| M10-T004 | ONE approved real `kaggle kernels push` attempted; **no LB recorded** (queue stall + now-fixed kernelspec bug); `submissions=03b5d080-…` `public_score` NULL | PASS-with-deviation |
| M10-T005 | Alt backbone EfficientNetB0; `experiment_run_id=c3339154-…`; holdout **0.3966** (−3.4pp, within 10pp guard); local only | PASS-with-note |
| M10-T006 | `tests/test_m10_smoke.py` — 4 DB-gated assertions (floor 0.30; alt within guard; T004 row exists `public_score` NULL; kernel_push event) | PASS |
| M10-T007 | `tests/test_m10_e2e.py` dry-run + 0-real-push audit sentinel; issue #11 closed; `KCA_SKIP_DOTENV` leak guard honored | PASS |
| M10-T008 | Exit criteria + `docs/m10-final-review.md` + tracking docs + PR | PASS |

_Promoted to `ai:ready` 2026-05-24 (issue #12). Decisions confirmed:
target competition `tpu-getting-started`; ONE real kernel push under
human approval; sequenced after issue #11 (dotenv leak) for the
dry-run leg; per-milestone worktree per `docs/milestone-loop-protocol.md` §5._

Goal: validate the full platform loop with a real Kaggle **kernel push**
(notebook submission) for
[Petals to the Metal — Flower Classification on TPU](https://www.kaggle.com/competitions/tpu-getting-started)
(multi-class image classification, public leaderboard, no cash prize,
safe for repeated dry-run + 1 real kernel push under human approval).

M9 validated the **CSV-submission** path (`kca kaggle submit` →
`kaggle competitions submit`). M10 validates the **notebook-submission**
path (`kca kaggle push` → `kaggle kernels push` + kernel-run wait + LB
record) end-to-end against a real competition. The `kernel_push`
reviewer-gate / approval-inbox round-trip gets the same regression
treatment that `kaggle_submit` got in M9-T003.

---

## M9.4: Discovery / Debate Gate agents ✓ done

_Shipped 2026-05-26. Planning + scaffolding milestone. Sits in parallel
with M10 and M9.2 / M9.3; does not renumber M10–M13._

Goal: add three role-isolated subagents — `requirements-skeptic`,
`legacy-archaeologist`, `design-red-team` — that run before
implementation work on `arch:` or `legacy-migration:` tasks. Each
agent has a canonical, byte-checkable acceptance line; the union of
the three lines is the gate. Origin: the `tools/legacy/kkr.py`
migration missed multi-Kaggle-account / owner / env semantics because
no agent role was responsible for asking
(`docs/meeting-notes/2026-05-24-r3.md` §6).

### M9.4 task sequence

| Task | Description | Result |
|---|---|---|
| M9.4-T001 | Scaffold `.claude/agents/requirements-skeptic.md` (question-only; ≥5 questions across ≥3 categories + explicit_unknowns) | PASS |
| M9.4-T002 | Scaffold `.claude/agents/legacy-archaeologist.md` (10-section report; multi-account/owner/env named explicitly) | PASS |
| M9.4-T003 | Scaffold `.claude/agents/design-red-team.md` (≥3 alternatives; ≥1 dropped capability with file:line evidence; 4 cost axes; actionable open_disagreements) | PASS |
| M9.4-T004 | `docs/architecture/discovery-debate-gate.md` + additive §7 of `docs/milestone-loop-protocol.md`. Deviation: skill + design-archaeology architecture doc deferred to M9.3 (which owns them). | PASS (with deviation) |
| M9.4-T005 | Replay kkr.py / kkr.yaml through the gate; 3 evidence transcripts under `docs/evidence/m9_4-kkr-replay/`; `tests/test_m9_4_agents.py` (10 passed, 1 skipped) | PASS |
| M9.4-T006 | `docs/m9_4-final-review.md`; PROJECT_STATE / milestones updates; one commit per Loop Prompt; PR against main | PASS |

Exit criteria — all met:

- Three new agents exist under `.claude/agents/`; YAML front-matter
  parses; each carries its canonical acceptance line verbatim.
- `docs/architecture/discovery-debate-gate.md` contains the union of
  all three acceptance lines, the `arch:` / `legacy-migration:` tag
  convention, and the closeout-evidence path convention.
- `docs/milestone-loop-protocol.md` has a new §7 with §1–§6
  byte-identical to the pre-M9.4 version.
- The kkr.py replay surfaces multi-account / owner / env mapping
  (the load-bearing gate) — `harrysun2006`, `firefly2006`,
  `.env.{owner}`, `_load_env_for_owner` all named with file:line
  evidence.
- `tests/test_m9_4_agents.py` passes with no DB / no creds / no
  network (10 PASS, 1 SKIP — the SKIP is the
  `design-archaeology` skill loader, deferred to M9.3-T001 by
  design).

See `docs/m9_4-final-review.md` for the full validation matrix.

Out-of-scope follow-ups (file as issues if wanted):

- Hook-based enforcement of the gate (a PreToolUse hook refusing
  `Edit` on `src/**` for `arch:` tasks without `discovery/` evidence).
- Runtime / SDK version of the three agents inside `src/worker/`.
- Replace the soft-skip in `tests/test_m9_4_agents.py` with a hard
  assertion once `.claude/skills/design-archaeology/SKILL.md` lands
  via M9.3-T001.

---

### M10 task sequence (proposed)

| Task | Description |
|---|---|
| M10-T000 | Verify Kaggle credentials + register `tpu-getting-started` in the local control plane. READ_ONLY Kaggle calls. |
| M10-T001 | Data discovery + manifest for a non-CSV competition. Record `kaggle competitions files` output; document the TFRecord-style data the kernel will read at runtime. |
| M10-T002 | Author baseline notebook (transfer learning from a pretrained ImageNet backbone); local CV / holdout score recorded via `kca run`. No kernel push yet. |
| M10-T003 | Reviewer gate fires for the `kernel_push` target_op; human approves via `kca decisions approve` (NOT via real Kaggle kernel push). |
| M10-T004 | **ONE** real `kca kaggle push` under explicit human approval. Wait for the kernel run to complete; record the resulting public LB score in the `submissions` table. |
| M10-T005 | Second experiment (different backbone or augmentation policy); local only. Second real kernel push is out of scope unless explicitly re-decided. |
| M10-T006 | Regression assertions: local CV thresholds (TBD), LB recorded, kernel-push round-trip recorded in `submissions` / `runs`. |
| M10-T007 | `tests/test_m10_e2e.py` mirroring `tests/test_m9_e2e.py`: notebook ↔ percent-format round-trip via `kg-nb`, kernel-push refusal without credentials, decision_api approval round-trip — all without real Kaggle calls. **Hard pre-req: issue #11 (dotenv leak) merged.** |
| M10-T008 | M10 exit criteria validation + `docs/m10-final-review.md`. |

Exit criteria (proposed — final list lands in `docs/m10-loop-prompts.md`):

- `tpu-getting-started` registered; data manifest recorded; baseline notebook
  authored and runs locally to a recorded CV/holdout score.
- Reviewer gate fires for `kernel_push` and records `agent_reviews` +
  `human_decisions` rows before the kernel push.
- Exactly ONE real `kca kaggle push` runs under human approval; the
  resulting kernel run completes; public LB score recorded.
- Second experiment achieves measurably higher local CV than baseline,
  or surfaces a documented reason why not.
- `tests/test_m10_e2e.py` (dry-run, no credentials) passes in CI; the
  dotenv leak from issue #11 is no longer reachable from the test
  subprocess.
- `docs/m10-final-review.md` PASS, mirroring the M8 / M8.5 / M9 layout.

Gaps this milestone is expected to close (or scope to a follow-up):

- `kca kaggle push` plumbing parity with `cmd_submit` (credentials gate,
  policy-from-env gate, refusal path).
- `kg-nb` skill notebook ↔ percent-format round-trip exercised both
  directions.
- `kernel_push` reviewer-gate wiring in `src/worker/reviewer.py`.
- Submission-format detection (related: issue #7) — natural to design
  inside M10's T001 / T002 scope if the user wants it bundled.
- Daily-limit guardrails for kernel push (related: issue #8).

---

## M11: authorized CTF/lab workflow

_Renumbered from old M10 on 2026-05-24 to make room for the
notebook-submission regression milestone (new M10)._
_Status: T000–T006 + T008 done (2026-06-09); T007 deferred pending human-supplied live-event credentials + approval comment._

Goal: support CTF-style challenges only inside explicit authorization boundaries.

Planned capabilities (all delivered except T007 live submission):

- Challenge scope and authorization metadata (`ctf_events`, `ctf_challenges`, `ctf_attempts`, `ctf_scopes`).
- Local container/lab-only execution (docker-compose web + in-process crypto).
- Solver script generation and testing (`kca ctf solver run`).
- Hard policy blocks for external scanning, real targets, credential theft, persistence, or unsafe actions (`challenge_run` / `flag_submit` / `network_egress` gates).

Exit criteria:

- CTF workflow is useful for local/sandbox labs and safely refuses out-of-scope activity.

### M11 landed deliverables (T000–T006 + T008, 2026-06-09)

- Discovery / Debate Gate: 3 subagent reports under `docs/evidence/m11/discovery/`.
- `supabase/migrations/0008_m11_ctf.sql` — 4 ctf_* tables; applied to cloud.
- `src/db/ctf.py` — 6 DB helpers.
- ADR-0016 (CTF data model) + ADR-0017 (CTF approval gates).
- `tools/kca/ctf.py` — 12 subcommands across 5 namespaces.
- `data/ctf/kca-fixtures-2026/` — web-1 (cookie-tamper) + crypto-1 (tiny RSA).
- `challenge_run`, `flag_submit`, `network_egress` in all 3 permission profiles.
- T005 local solves: web `flag_length=21`, crypto `flag_length=17`; 2 `ctf_attempts(accepted=true)` in cloud.
- T006 reviewer-gate round-trips: `challenge_run` approve + `flag_submit` approve + `network_egress` reject.
- `tests/test_m11_e2e.py` (8/8 PASS), `tests/test_m11_smoke.py` (7/7), `tests/test_m11_db.py` (13/13).
- `docs/architecture/m11-ctf-workflow.md` (7 sections).
- `docs/m11-final-review.md` — 23 PASS / 1 SKIP-BLOCKED / 0 FAIL.

### M11 T007 deferred — punch list for human

1. `KCA_ALLOW_REMOTE=1` set in session.
2. Register on a live CTFtime event; populate `~/.ctf/<slug>.json`.
3. `kca ctf event register` + `kca ctf scope set` for the live event.
4. Comment "approved to submit" on T007 closing issue + `decision:confirmed`/`ai:ready` labels.
5. Re-run M11-T007 Loop Prompt.

### M11 follow-ups (file as GitHub issues)

- **A** — `agent_jobs.competition_id` schema drift on cloud (P2, `type:bug`, `area:supabase`).
- **B** — `kca ctf flag submit` non-dry-run env-check before reviewer-gate (P1, `type:bug`, `area:security`).
- **C** — T004 fixture-authoring trail contains deterministic crypto flag (P1, `type:security`).
- **D** — `expected.sha256` web-1 churn (P2, `type:test-gap`, `area:ctf`).
- **E** — gh CLI hook denial blocks `decision:confirmed` verification (P2, `type:bug`).
- **F** — httpx-level `network_egress` interceptor for subprocess egress (P1, `type:feature`, `area:security`).
- **G** — per-challenge rate-limit column on `ctf_scopes` (P3, `type:feature`, `area:ctf`).

---

## M12: Devpost / hackathon workflow

_Renumbered from old M11 on 2026-05-24. Planning landed 2026-05-26 —
`docs/m12-loop-prompts.md` + ten `docs/tasks/M12-T00x-*.md` specs._

Goal: validate the full platform loop with a real Devpost-style
**hackathon submission** end-to-end, and in doing so generalize the
competition-policy layer beyond Kaggle so M11 (CTF) and future
platforms can reuse it. M9 validated the **CSV-submission** path on
Spaceship Titanic; M10 validates the **notebook / kernel-push** path on
Petals to the Metal; M12 validates the **hackathon-submission** path on
a hackathon picked in M12-T000 under human approval.

The `arch:` task in this milestone is **M12-T001**: a Discovery /
Debate Gate run (`docs/milestone-loop-protocol.md` §7) that produces
ADR-0016 defining the generalized `competition_type` enum and
team-scoped policy resolver. CTF-friendly enum values (`ctf`) ship in
M12 so M11 can plug in without a second schema migration.

### M12 task sequence

| Task | Description | Depends on |
|---|---|---|
| M12-T000 | Survey 2–3 candidate Devpost / hackathon events; human picks target slug. READ_ONLY; no DB writes. | — |
| M12-T001 | `arch:` Discovery / Debate Gate on competition-policy generalization; ADR-0016 (`competition_type` enum, team-scoped resolver). | T000 |
| M12-T002 | Migration `0008_m12_competition_type_teams.sql` — `competitions.competition_type` enum (default `kaggle`), `teams`, `team_memberships`, `competitions.deadline`, `competitions.submission_format`. Policy resolver refactor. Backwards-compatible. | T001 |
| M12-T003 | `tools/kca/devpost.py` + `kca devpost register/fetch/info` (READ_ONLY). Lightweight HTTP first; Playwright fallback per `tools/kca/research_fetch.py` pattern. | T002 |
| M12-T004 | `.kca/skills/hackathon-experiment-loop/SKILL.md` + `.kca/permissions/hackathon-runner.yaml` + `submission_checklist` tool. | T002, T003 |
| M12-T005 | UI: `ui/src/pages/HackathonDeadline.tsx` + `ui/src/pages/SubmissionChecklist.tsx`; routes; vitest + Playwright smoke. Reuse `ApprovalInbox` / `DecisionGate`. | T002 |
| M12-T006 | Worker runs `hackathon-experiment-loop` end-to-end locally; produces `runs/<slug>/<run_id>/submission_pack/` (README, demo plan, source link). No external write. | T003, T004 |
| M12-T007 | Reviewer gate fires for `devpost_submit`; human approves via `kca decisions approve`; **ONE** real Devpost submission; record row in `submissions` (platform=`devpost`). | T006 |
| M12-T008 | `tests/test_m12_e2e.py` (dry-run, no creds) + `tests/test_m12_smoke.py` (DB-gated). Mirror M9 / M10 patterns. | T002–T007 |
| M12-T009 | Exit criteria validation + `docs/m12-final-review.md` + PROJECT_STATE / README / milestones updates + handoff + `worktree-milestone-pr`. | all |

Planned capabilities:

- **Generalized competition-policy layer** (ADR-0016): `competition_type`
  enum (`kaggle`, `devpost`, `hackathon_devpost`, `ctf`, `generic`);
  policy resolver routes on type; M11 reuses the schema.
- **Minimal team model**: `teams` + `team_memberships` tables; idea
  board / submission scope by team. No invite / role flow in M12.
- **Hackathon rules and deadline tracking**: `competitions.deadline`
  + `competitions.submission_format` (jsonb); UI deadline countdown.
- **Idea / discussion board** reusing `research_items`; no new table.
- **App prototype workflows** as a hackathon-flavoured skill;
  produces a structured submission pack.
- **Submission checklist + approval gates**: templated checklist
  page in UI; new `devpost_submit` reviewer gate.
- **Real Devpost submission** under explicit human approval — one
  per milestone, mirroring M9 `kaggle_submit` discipline.

Regression target: hackathon slug picked in M12-T000 from a candidate
list of 2–3 Devpost events. Human selects via comment on the closing
GitHub issue before T001 begins. The picked slug is recorded in
`docs/evidence/m12/t000-candidates.md` and referenced from every
later task closeout.

Exit criteria — proposed (final list in `docs/m12-loop-prompts.md`):

- Candidate hackathon picked; entry registered in `competitions` with
  `competition_type='devpost'` (or `hackathon_devpost`).
- ADR-0016 merged; the three Discovery / Debate Gate reports under
  `docs/evidence/m12/t001/discovery/` carry their canonical
  acceptance lines verbatim.
- Migration `0008_m12_competition_type_teams.sql` applied; all
  existing Kaggle competitions still resolve their policy correctly
  (`competition_type` defaults to `kaggle`).
- `kca devpost fetch --slug <picked>` returns metadata; no submit /
  upload / write action runs in T003.
- `hackathon-experiment-loop` skill runs locally and produces a
  submission pack at `runs/<slug>/<run_id>/submission_pack/`.
- Reviewer gate fires for `devpost_submit`; human approves; exactly
  ONE real Devpost submission lands; `submissions` row written with
  `platform='devpost'` + external submission URL.
- `tests/test_m12_e2e.py` passes in CI without credentials; the
  Devpost adapter refuses to submit without env vars present.
- `docs/m12-final-review.md` PASS, mirroring the M9 / M10 layout.

Out-of-scope follow-ups (file as issues if surfaced):

- Hook-level enforcement of the Discovery / Debate Gate (deferred from M9.4).
- Full team-invite / role-based permission flow.
- Other hackathon platforms (HackerEarth, MLH, Devfolio).
- Auto-generated demo video / readme from agent run logs.
- CTF wiring against `competition_type='ctf'` (owned by M11).

---

## M13: evaluation, reliability, and regression suite

_Renumbered from old M12 on 2026-05-24._

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
