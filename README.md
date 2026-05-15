# Kaggle / CTF Code Agent Source Bundle

Initial source scaffold for a Claude Code / Claude Agent SDK based competition assistant.

This repository is intentionally **local-first** and **audit-first**. The agent should not merely chat and execute code; every research finding, idea, experiment, code edit, test result, submission, and human decision should be traceable.

## Contents

- `CLAUDE.md` — project-level instructions for Claude Code.
- `.claude/settings.json` — initial permissions, sandbox, and hooks.
- `.claude/hooks/guard_tool.py` — deterministic pre-tool guardrails.
- `.claude/hooks/audit_event.py` — tool event audit log writer.
- `.claude/skills/*/SKILL.md` — reusable workflows for research, Kaggle experiments, CTF sandbox work, and iteration review.
- `.claude/agents/*.md` — project subagents for research, experiment execution, review, and safety checks.
- `docs/requirements.md` — initial product requirements.
- `docs/architecture.md` — initial architecture and design decisions.
- `docs/design-decisions.md` — ADR-style decisions to revise as the project evolves.
- `supabase/migrations/0001_init.sql` — first-pass Supabase/Postgres schema.

## Immediate next steps

1. Copy this bundle into your real project repository.
2. Review `.claude/settings.json` and `.claude/hooks/*` before trusting the workspace.
3. Start Claude Code from the repository root and run `/skills` and `/agents` to verify discovery.
4. Use `/kaggle-experiment-loop` or ask the main agent to start from a competition brief.
5. Treat CTF functionality as authorized, sandboxed challenge solving only.
