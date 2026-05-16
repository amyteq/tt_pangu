# ADR-0003: GitHub Repository as Durable Project Memory

## Status
Accepted as initial direction.

## Decision
The GitHub repository is the durable source of truth for project memory, architecture, decisions, and cross-tool instructions.

## Rationale
Claude Code, ChatGPT/Codex, Lovable, and other tools each have their own memory/context behavior. Hidden product memory is useful but not reliable as a shared team memory. Committing project memory into GitHub makes the system reviewable, portable, auditable, and tool-agnostic.

## Required files
- `PROJECT_STATE.md`: current project snapshot and open decisions.
- `AGENTS.md`: cross-tool instructions for ChatGPT/Codex/other agents.
- `CLAUDE.md`: Claude Code-specific project memory and rules.
- `docs/adr/`: architecture decision records.
- `docs/meeting-notes/`: summarized discussions and decisions.
- `docs/architecture/`: system architecture and model routing.
- `docs/tooling/`: tooling contracts and wrappers.
- `docs/testing/`: regression competitions and test cases.

## Update rule
After major discussions or architectural changes, produce a short update and commit it. The goal is not to store every chat transcript. The goal is to preserve decisions, assumptions, constraints, and next actions.
