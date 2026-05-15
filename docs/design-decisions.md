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
