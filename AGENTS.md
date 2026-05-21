# AGENTS.md — Cross-Tool Project Instructions

This repository builds a hybrid human + AI coding agent for Kaggle-style competitions and authorized CTF/lab challenges.

## Two meanings of "code agent"

**Platform-development coding agents** are external AI tools — Claude Code (primary), ChatGPT, Cursor — used to build this repository. They write source code, update docs, run local tests, and open PRs under human supervision.

**Runtime competition code agents** are agents launched by the finished platform to help a human user compete. Initial runtime: Claude Agent SDK in an isolated Python worker. Future: model router for Claude, GPT-style, and local models.

Never confuse the two. A platform-development agent editing this repo is not the same as a runtime agent running a Kaggle experiment. See `docs/architecture/platform-vs-runtime-agents.md` for details.

## Source of truth
Use this repository as the durable project memory. Do not rely on hidden memory in any single AI product. Important decisions must be written to:
- `PROJECT_STATE.md`
- `docs/adr/`
- `docs/architecture/`
- `docs/tooling/`
- `docs/testing/`
- `docs/meeting-notes/`

## Architecture
- Claude Code CLI/Desktop is used for interactive repository development.
- Claude Agent SDK is the intended core production worker.
- Worker execution is Python-first for Kaggle/ML/CTF tasks.
- Control plane and future UI are TypeScript/Supabase, developed in Claude Code (same repo, same migrations, same CI).
- Supabase stores metadata, messages, research notes, runs, results, artifacts, approvals, and audit events.
- Git stores code and agent instructions.
- Large datasets and generated artifacts should not be committed unless explicitly required.

## Branch and worktree rules
- Every AI task that modifies code should use a dedicated branch or worktree.
- `main` must remain stable and protected.
- Do not allow multiple AI sessions to edit the same branch or files simultaneously.
- Do not push branches or create PRs without explicit human approval.
- Do not force-push, reset --hard, or run destructive git operations without explicit human approval.

## Development rules
- Make small, reviewable changes. One meaningful change per task.
- Return a plan and wait for human approval before editing files.
- Update docs and ADRs when changing architecture or workflow assumptions.
- Prefer deterministic tests and local validation before external submissions.
- Never read, print, or commit secrets, `.env`, `kaggle.json`, API keys, or private keys.
- Do not submit to Kaggle or push remote kernels without explicit human approval.
- CTF support is restricted to explicitly authorized challenges, local labs, or sandboxed environments.

## Competition loop
Follow this loop unless a task says otherwise:
1. Understand rules, metric, data, limits, and submission format.
2. Create or verify validation strategy.
3. Establish a baseline.
4. Run one controlled experiment at a time.
5. Record config, metrics, artifacts, logs, and conclusions.
6. Decide whether to iterate, stop, or request human approval for submission.

## Tooling
Existing Kaggle scripts should be wrapped behind stable commands or typed tools. Every tool must document:
- Purpose.
- Inputs and outputs.
- Side effects.
- Safety class: read-only, local-write, remote-write, or submission.
- Required approval policy.
