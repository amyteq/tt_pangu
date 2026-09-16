# Platform-Development Coding Agents vs Runtime Competition Code Agents

> **Partly superseded (2026-09-14, issue #189).** The *distinction* below still holds and is the live one — it appears as "Two agents: Claude Code harness vs KCA product" in `CLAUDE.md` and `AGENTS.md`, and in `docs/adr/0021-kca-autonomy-model.md`. What is stale is §2's runtime direction: **KCA is not built on the Claude Agent SDK** (discussion #185). The approval-gate rows in the table below are superseded on paper by ADR-0021 §2's screened autonomy as widened by ADR-0022 §5 — but read that as design, not as current permission: the wide grant applies only to a competition meeting ADR-0022 §5's activation conditions **A1-A7**, none does, the ADR-0021 §2 fallback is unimplemented, and no code reads the `autonomy:` block. So a Kaggle submission or kernel push is asked for every time (`CLAUDE.md` → *Operating principles* 6). The full rewrite of this document's runtime half belongs to issues #188 / #190.

This document defines two related but distinct meanings of "code agent" used in this project. Confusing them leads to incorrect scope assumptions, unsafe tool use, and broken multi-tool workflows.

## 1. Platform-development coding agents

These are external AI tools used by the human developer to **build this repository**.

Examples:
- Claude Code CLI, VS Code extension, Desktop app, or Web
- ChatGPT Pro / Codex
- Cursor
- Lovable (expected for UI shell later)
- GitHub Actions / Claude Code Routines for cloud automation

Role:
- Write and review this product's source code and docs
- Update architecture decisions, task specs, and test configuration
- Run local tests, lint, and CI repair loops
- Open branches and PRs under human supervision

Key constraint: **these tools do not share hidden memory across sessions or products.** The GitHub repository is the only reliable shared memory. Any decision that needs to survive a context reset must be written to repo files.

## 2. Runtime competition code agents

These are agents that the **finished platform** launches to help a human user compete.

Initial runtime direction:
- Claude Agent SDK as the first core worker harness
- Isolated workspace or container per job
- Python / notebook-first for Kaggle workflows
- Future model router: Claude (Sonnet/Opus), GPT-style models, local vLLM/Ollama, specialist tools

Runtime agents operate under competition-specific policy:
- Sandboxing and resource limits
- Budget and turn limits
- Human approval gates for remote side effects (Kaggle submissions, kernel pushes)
- Audit logging of every tool call and decision

## Why this distinction matters

| Concern | Platform-development agent | Runtime competition agent |
|---|---|---|
| Modifies this repo's source | Yes — primary job | No — modifies competition workspace |
| Needs GitHub push rights | Yes, under human approval | No — separate competition workspace |
| Runs in developer's terminal | Yes | No — isolated container/worker |
| Memory source | GitHub repo files | Competition workspace + Supabase records |
| Safety rules | `CLAUDE.md` + `.claude/settings.json` | Competition policy module |
| Approval gates | Human reviews PRs, commits, pushes | Human approves Kaggle submissions, remote writes |

## Rule

When writing agent instructions, skills, hooks, or tool policies, always specify which agent type is in scope. Do not write rules that apply to both without making the dual-applicability explicit.
