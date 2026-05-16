# Platform-Development Coding Agents vs Runtime Competition Code Agents

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
