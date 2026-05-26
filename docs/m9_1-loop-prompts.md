## Plan M9.1 GitHub event + session memory hardening.
Do not implement until you present a plan.

Read first:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones.md
- docs/engineering-practice.md
- docs/github-collaboration.md if present
- .github/workflows/claude.yml
- .github/workflows/claude-code-review.yml
- .claude/settings.json
- .claude/hooks/audit_event.py
- .claude/hooks/guard_tool.py
- tools/legacy/kkr.py
- tools/legacy/kkr.yaml
- tools/kca/
- src/worker/

Mission:
Design a safe GitHub event and session-memory hardening layer for KCA development and future KCA runtime dogfooding.

Questions to answer before implementation:
1. How should Claude Code session transcripts/tool events be mirrored or summarized into project logs without committing secrets?
2. How should GitHub issue/PR comments, reviews, and labels become a human/AI collaboration interface?
3. Which comments can become core memory, and which require human confirmation?
4. Which new agents/skills are needed?
5. How should legacy tools like kkr.py/kkr.yaml be analyzed so hidden requirements such as multi-Kaggle-account support are not missed?

Required plan sections:
- Scope
- Non-goals
- Proposed files
- Security model
- Memory promotion workflow
- GitHub event workflow
- Agent/skill list with responsibilities and Must Not rules
- Tests/smoke checks
- Rollout order
- Risks and approval gates

Important rules:
- Do not read or print secrets.
- Do not run real Kaggle submit/kernel push/upload.
- Do not make GitHub write operations without approval.
- Do not modify production Supabase.
- Do not commit raw Claude transcripts by default.
- Treat GitHub repo files as the source of truth, not hidden AI memory.

Stop after the plan and wait for human approval before editing.