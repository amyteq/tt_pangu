# Initial Architecture — Competition Code Agent

## Strong recommendation

Start with a **hybrid local-first architecture**:

- Use Claude Code directly for early development and dogfooding.
- Use Claude Agent SDK for the production-style worker loop.
- Use Supabase as the control plane and audit database, not as the code execution environment.
- Run code, browser automation, and agent sessions inside isolated worker containers.
- Add Lovable later as the product shell/admin UI once the worker loop and data model are stable.

## Why this shape

The agent needs long-running state, file edits, shell commands, browser automation, test loops, and human approvals. That is closer to a persistent worker than a serverless request handler. Supabase is excellent for state, queues, auth, realtime, and storage, but the actual code agent should run in a sandboxed machine or container.

## Components

### 1. Human interface

MVP:

- Terminal/CLI plus Claude Code.
- Optional lightweight dashboard querying Supabase.

Later:

- Lovable-built product shell with task creation, discussion, live logs, artifacts, score charts, and approvals.

### 2. API / Orchestrator

Responsibilities:

- Create projects, sessions, jobs, and approvals.
- Enqueue agent work.
- Stream or store agent events.
- Enforce rate limits and policy gates.
- Coordinate GitHub branches/PRs and artifact storage.

Implementation options:

- Supabase Edge Function for lightweight job creation and webhooks.
- Separate Python or Node service for heavier orchestration.
- For MVP, a local `agentctl` CLI can write rows to Supabase and start workers.

### 3. Supabase control plane

Use Supabase for:

- Postgres tables: projects, competitions, sessions, messages, research, experiments, runs, submissions, human decisions, artifacts, events.
- Auth and RLS when a UI exists.
- Realtime updates for task logs and approvals.
- Storage buckets for logs, screenshots, generated submissions, reports, and run artifacts.
- Queues or `agent_jobs` table for durable background work.

### 4. Agent worker

The worker runs in a sandboxed container or VM and contains:

- Claude Agent SDK.
- Project repository checkout.
- Python/R/Node environment required by the competition.
- Kaggle CLI/API tooling when authorized.
- Browser automation runtime: local Playwright or remote Browserless.
- Git tooling.
- Supabase client for event and artifact writes.

Recommended session modes:

- `plan`: read-only exploration and proposal.
- `research`: web/browser research with source logging.
- `experiment`: code edits plus tests and local validation.
- `review`: read-only or limited-write review before commit/submission.

### 5. Claude Code configuration layer

Project-controlled files:

- `CLAUDE.md`: durable project instructions and safety boundaries.
- `.claude/settings.json`: baseline permissions, sandbox, hooks.
- `.claude/hooks/*`: deterministic safety and audit behavior.
- `.claude/skills/*`: reusable workflows.
- `.claude/agents/*`: subagents for isolated research, experiment execution, review, and safety.

### 6. Browser and research tools

Recommended path:

- Use Playwright for local browser automation where visual state, screenshots, or interaction matter.
- Optionally use Browserless for hosted browser sessions when workers cannot run browsers reliably.
- Wrap browser access as a scoped MCP server or custom SDK tool so screenshots and extracted text can be logged.

Research record fields:

- URL, title, fetched_at, source_type, trust_level, summary, extracted quotes/snippets, screenshot path, related task/session.

### 7. Kaggle integration

Capabilities:

- Download/list competition files when authorized.
- Run local cross-validation and training.
- Create submission files.
- Submit only after human approval.
- Fetch and store public leaderboard score when available.

Policy:

- Do not automate over-submission.
- Store credentials outside the repo.
- Record every external submission as a human decision plus submission row.

### 8. CTF integration

Capabilities:

- Work on local challenge folders and authorized endpoints.
- Start challenge containers if provided.
- Write solvers and writeups.
- Capture commands, outputs, and artifacts.

Policy:

- No public target scanning unless target scope is explicitly provided and authorized.
- No persistence, malware, credential theft, or exfiltration from non-challenge systems.

## Event flow: experiment loop

1. Human creates task: “Improve tabular model for competition X.”
2. Orchestrator creates `agent_sessions` and `agent_jobs` rows.
3. Worker starts isolated workspace and checks out repo branch.
4. Agent reads `CLAUDE.md`, skills, current leaderboard/validation state.
5. Agent proposes plan and optionally asks for approval.
6. Agent edits code and runs a narrow validation.
7. Hooks audit tool calls and block unsafe actions.
8. Worker stores logs, metrics, artifacts, and code diff metadata.
9. Agent analyzes result versus baseline.
10. Agent either iterates, reverts, asks human, or prepares a submission candidate.
11. Human approves or rejects submission/commit/push.

## Design decisions to revisit

- Worker language: Python-first for Kaggle/ML vs TypeScript-first for UI/backend integration.
- Browser: local Playwright vs Browserless vs both.
- Queue: Supabase Queues vs custom `agent_jobs` table first.
- Container provider: local Docker, E2B, Modal, Fly Machines, Daytona, or self-hosted.
- Git flow: commits per accepted experiment vs branch snapshots per run.
- Memory: database-backed project memory vs Claude subagent memory.
- Submission policy: manual approval always vs semi-auto under strict daily cap.
