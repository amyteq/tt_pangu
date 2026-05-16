# kaggle-code-agent

A hybrid human + AI workbench for competitive programming: Kaggle competitions, authorized CTF/lab challenges, Devpost hackathons, and similar code contests.

The platform is **local-first and audit-first**. Every research note, experiment, code change, test result, approval, and submission is traceable.

## Two meanings of "code agent"

This project uses two related but distinct concepts.

**Platform-development coding agents** are external AI tools — Claude Code, ChatGPT, Cursor, Lovable — used to build this repository. They write source code, update docs, run local tests, and open PRs under human supervision.

**Runtime competition code agents** are agents launched by the finished platform to help a human user compete. Initial runtime: Claude Agent SDK in an isolated Python worker. Future: model router for Claude (Sonnet/Opus), GPT-style models, and local vLLM/Ollama models.

See `docs/architecture/platform-vs-runtime-agents.md` for the full breakdown.

## Source of truth

**GitHub repository files are the durable project memory.** AI tools do not share hidden memory reliably across sessions or products. All decisions, architecture, task specs, and safety rules must live in repo files.

Key files:
- `PROJECT_STATE.md` — current project snapshot and open decisions
- `AGENTS.md` — cross-tool instructions for ChatGPT, Codex, Cursor, and other agents
- `CLAUDE.md` — Claude Code-specific instructions and safety boundaries
- `docs/adr/` — architecture decision records
- `docs/milestones.md` — product plan from M0 through M10

## Repository layout

```
CLAUDE.md                    Claude Code project instructions
AGENTS.md                    Cross-tool agent instructions
PROJECT_STATE.md             Current project snapshot

.claude/
  settings.json              Permissions, sandbox, hooks
  hooks/                     Pre/post tool safety and audit hooks
  agents/                    Subagents: researcher, experimenter, reviewer, safety-guard

docs/
  milestones.md              Product plan M0–M10
  architecture.md            Component architecture overview
  architecture/
    model-routing.md         Model routing tiers and logging policy
    platform-vs-runtime-agents.md  Two meanings of "code agent"
  adr/                       Architecture decision records
  tasks/                     Task specifications (M0-T001, M1-T001, ...)
  testing.md                 Test commands and current blockers
  testing/                   Competition-level regression test cases
  meeting-notes/             Summarized decisions and discussions

scripts/                     Local utilities and experiment runners
tools/
  legacy/                    Existing Kaggle helper scripts (pre-wrapper, M1 scope)
supabase/migrations/         Postgres schema migrations

data/                        Local data mount — do not commit competition data
artifacts/                   Generated run artifacts — do not commit unless reviewed
runs/                        Run outputs — do not commit
```

## Quick start for a new AI session

1. Read `PROJECT_STATE.md` for current status and open decisions.
2. Read `AGENTS.md` or `CLAUDE.md` depending on your tool.
3. Read the relevant task spec under `docs/tasks/`.
4. Return a plan and wait for human approval before editing files.
5. Never read `.env`, `kaggle.json`, `secrets/`, or private keys.
6. Never submit to Kaggle, push kernels, or perform any remote write without explicit human approval.

## Current milestone: M0 — project baseline

Status: in progress.

Goal: make the repository safe and legible for multi-tool AI-assisted development before MVP-1 feature work begins. See `docs/milestones.md` for the full product plan.

## Safety rules summary

- Secrets never enter repo, prompts, logs, or screenshots.
- Kaggle submissions, kernel pushes, and dataset uploads require explicit human approval.
- CTF/lab work must be local/sandboxed or explicitly authorized.
- Every AI task that modifies code should use a branch or worktree so `main` remains stable.
- Do not allow multiple AI sessions to edit the same branch or files simultaneously.
