# Design Decisions / ADRs

## ADR-001 — Use Claude Agent SDK for production worker, Claude Code CLI for development

Status: proposed

Decision: Use Claude Code CLI for local dogfooding and project configuration, but implement the durable product worker with Claude Agent SDK.

Rationale: The SDK exposes the Claude Code agent loop programmatically, supports long-running sessions, tools, hooks, permissions, subagents, and structured event streaming. The CLI remains the fastest way to design and test project instructions, skills, hooks, and workflows.

## ADR-002 — Supabase is the control plane, not the execution runtime

Status: proposed

Decision: Use Supabase for Postgres, auth, storage, realtime, webhooks, and job state. Run agent/code execution in isolated workers outside Supabase Edge Functions.

Rationale: Training models, running tests, browser automation, and iterative agent loops need long-lived compute, large file access, and sandbox controls.

## ADR-003 — Human approval gates for external side effects

Status: proposed

Decision: Require approval for Kaggle submissions, git push, deployment, Supabase production writes, broad destructive commands, paid APIs, and CTF activity outside local/specified targets.

Rationale: Competitions have rules and limits; code agents can make mistakes; external side effects should be deliberate.

## ADR-004 — Store code in git, artifacts in storage, metadata in Postgres

Status: proposed

Decision: Keep generated source code and accepted changes in git. Store run outputs, screenshots, logs, model files, and submission files in object storage or artifact directories. Store metadata, metrics, and relationships in Postgres.

Rationale: Git is best for code history; object storage is best for blobs; Postgres is best for querying agent state and audit trails.

## ADR-005 — Use one-change experiment discipline for Kaggle optimization

Status: proposed

Decision: Prefer one hypothesis/change per experiment run, unless the human approves a broader batch.

Rationale: It makes score changes explainable and reduces leaderboard overfitting and confusion.

## ADR-006 — CTF support is authorized and sandbox-only

Status: proposed

Decision: The CTF workflow is limited to sanctioned challenge environments, local labs, and explicitly provided scopes.

Rationale: The goal is competition collaboration and learning, not unauthorized intrusion.

## ADR-007 — Start with an `agent_jobs` table, evaluate Supabase Queues later

Status: proposed

Decision: Use a simple job table first because it is easy to inspect and migrate. Move to Supabase Queues if/when background delivery semantics become the bottleneck.

Rationale: Early product learning matters more than queue sophistication.

## ADR-008 — Artifact storage is local-first in M2

Status: accepted (M2)

Decision: Artifact bytes live under `runs/<comp>/<run_id>/artifacts/` in M2. The `artifacts.storage_path` column uses a URI scheme (`local://<rel-path>`, `supabase://<bucket>/<key>` reserved for M3) so the M3 migration to Supabase Storage is a 1:1 path rewrite. `content_hash` is populated with SHA-256 at write time.

Rationale: M2 has no worker that produces shared artifacts yet. Going to Supabase Storage from day one buys nothing and forces auth/upload code we don't need. Full details and trade-offs: `docs/adr/0008-artifact-storage-local-first.md`.

---

## ADR-0004 — LiteLLM as unified LLM provider layer

Status: accepted (2026-05-19)

Decision: Use `litellm` as the single interface to all LLM providers (Claude, GPT-4o, local vLLM/Ollama). `AgentWorker` calls `litellm.completion()` instead of `anthropic.Anthropic()`. Tool schemas are in OpenAI format. Model and sampling params (temperature, top_p) are set per job type in `JobPolicy`.

Per job type defaults: research (temp=0.8), implement (temp=0.2), experiment (temp=0.1), debug (temp=0.3), eval (temp=0.5), prepare_submission (temp=0.1).

Full details: `docs/adr/0004-litellm-provider-layer.md`.

## ADR-0005 — Job taxonomy and platform terminology

Status: accepted (2026-05-19)

Decision: Formal definitions for project, competition, session, job, experiment, run, submission, human_decision. Job is the smallest schedulable unit; one discrete task per agent worker. Job types: research, implement, experiment, debug, eval, prepare_submission, submit, kernel_push, monitor, analysis, git_commit, git_push.

Full details: `docs/adr/0005-job-taxonomy.md`.

## ADR-0006 — Configurable approval gates — default allow

Status: accepted (2026-05-19)

Decision: All approval gates are configurable per project/competition. Default is **allow (no approval required)** for kaggle_submit, kernel_push, git_push. Default is **require approval** for dataset_upload, git_force_push, supabase_migrate, delete_artifact. Human intervention is reserved for major direction decisions, not routine submission mechanics.

Supersedes: prior implicit "always require approval" policy in M0–M2.

Full details: `docs/adr/0006-configurable-approval-gates.md`.

## ADR-0009 — Separate GitHub repo per competition

Status: accepted (2026-05-19)

Decision: Each registered Kaggle competition gets its own GitHub repo (`harry/kaggle-<slug>`). Branches track experiments (`exp/<hypothesis-slug>`). Agent jobs get git worktrees *within* the competition repo for per-job isolation. Platform code never mixes with competition code.

Transition: M3 uses platform repo worktree as interim (worker skeleton). M4 adds `kca competition register/clone`, migration 0004 (`repo_url`, `local_clone_path`), and `pyproject.toml` so kca is pip-installable from competition repos.

Full details: `docs/adr/0009-competition-repo-strategy.md`.

## ADR-0007 — OpenTelemetry observability strategy

Status: accepted (strategy); implementation deferred to M3/M4

Decision: Adopt OTEL for end-to-end visibility: one root span per job, child spans per turn and per tool call. LiteLLM OTEL callback covers LLM-call spans automatically. Enables model comparison, cost forecasting, platform regression detection.

Full details: `docs/adr/0007-otel-telemetry-strategy.md`.

## ADR-0010 — Per-job-type model routing

Status: accepted (M5).

Decision: route the default model by job type — Haiku for `research`, Sonnet for `implement`/`experiment`, Opus for `eval`/`analysis`/`review`. `--model` on `scripts/run_job.py` remains a hard override; the routing function lives in `src/worker/routing.py`. JSON output now includes the resolved `model`.

Full details: `docs/adr/0010-model-routing.md`.
