# M9.1 — Retired (superseded by M9.3)

**Status: Retired 2026-05-26. Superseded by M9.3.**

The original M9.1 was a broad "GitHub event + session memory hardening" plan
that bundled session-transcript mirroring, channels-bridge integration,
agent-pack migration, several bespoke agents, *and* the two skills below.
It was never implemented as one unit.

The two highest-leverage pieces have shipped under M9.3:

- `design-archaeology` skill — see [`docs/milestones/m9_3/loop-prompts.md`](m9_3-loop-prompts.md) and [`docs/architecture/design-archaeology.md`](architecture/design-archaeology.md).
- `memory-promotion` skill — see [`docs/milestones/m9_3/loop-prompts.md`](m9_3-loop-prompts.md), [`docs/adr/0015-memory-promotion-model.md`](adr/0015-memory-promotion-model.md), and [`docs/architecture/memory-promotion.md`](architecture/memory-promotion.md).

Deferred residual scope (tentatively M9.4 or later — no commitment scheduled here):

- `session-closeout` skill — emit a Tier-2 session summary at end-of-session.
- `scripts/claude_export_session.py` — sanitised transcript mirror to `logs/claude-sessions/`.
- GitHub webhook → Claude Code Channels bridge (research preview).
- `kca-agent-pack` migration packaging — way to copy reusable agents/skills/hooks between projects.
- Bespoke agent wrappers: `requirements-skeptic`, `legacy-archaeologist`, `design-red-team`, `github-decision-extractor`. (The *skills* exist via M9.3; agent wrappers can wait.)
