<!--
Source fragment for the generated `AGENTS.md`.

`AGENTS.md` = this file's PREAMBLE part
            + the body of `CLAUDE.md` (verbatim — the shared rules)
            + this file's APPENDIX part.

Edit this file (or `CLAUDE.md`) and run `python scripts/gen_agents.py`.
Never edit `AGENTS.md` directly — `scripts/gen_agents.py --check` (and
`tests/test_instruction_parity.py`) will fail.
-->

<!-- part: preamble -->
# AGENTS.md — cross-harness project instructions

This file is what **Codex / ChatGPT** — and any other `AGENTS.md`-reading harness — loads
when it opens this repository. `CLAUDE.md` is what **Claude Code** loads. They have to say
the same thing: phase 1 runs the same competition workflow from both harnesses so the two
can be compared on different competitions (discussion #185, issue #189).

## How to read this file

- Everything under **Shared rules** is generated verbatim from `CLAUDE.md`. If a rule here
  disagrees with `CLAUDE.md`, `CLAUDE.md` wins and the generator is broken — say so in the
  session instead of following the stale copy.
- Where a shared rule names **"the Claude Code harness"**, read it as **"the harness you are
  running in"**. The protections it describes — ask before destructive host commands, before
  paid-API / credential use, before anything that touches the human's own machine or
  accounts — are *harness* rules, and they bind Codex exactly as they bind Claude Code.
- The distinction that is **not** interchangeable is the one in *Two agents: Claude Code
  harness vs KCA product*. A rule about the KCA product agent is never automatically a rule
  about the harness you are, and vice versa; conflating them is the root cause of issue #65.

## Read first

- `PROJECT_STATE.md`
- `docs/milestones/README.md`, `docs/milestones/*/handoff.md`
- `docs/adr/` — especially `docs/adr/0021-kca-autonomy-model.md` (KCA autonomy model)
- `docs/engineering-practice.md` — the full GitHub collaboration model
- `.agents/README.md` — what of `.claude/` this harness can and cannot consume

## Source of truth

This repository is the durable project memory. No AI product's hidden memory is shared
across harnesses, so any decision that must survive a context reset belongs in a file:
`PROJECT_STATE.md`, `docs/adr/`, `docs/architecture/`, `docs/tooling/`, `docs/testing/`,
`docs/meeting-notes/`, or the GitHub issue / discussion it came from.

<!-- part: appendix -->
# Codex-side notes

These apply only to harnesses reading this file; they are not part of the shared rule set.

## What Codex actually loads from this repo

| Path | Loaded? | How that was established |
|---|---|---|
| `AGENTS.md` | **yes** — as the project doc | appears as `# AGENTS.md instructions for <repo>` in the prompt dump |
| `.agents/skills/<name>/SKILL.md` | **yes** — project skill root | listed under `### Skill roots` as `r1 = <repo>/.agents/skills`, each skill under `### Available skills` |
| `.agents/skills/<name>` as a **symlink** | **yes** — followed | a symlinked skill is listed under its front-matter `name` |
| `.claude/skills/**` | **no** | absent from the same prompt dump |
| `.claude/agents/*.md` (sub-agents) | **no** | an `.agents/agents/*.md` probe produced no sub-agent entry, including with `--enable multi_agent_v2` |
| `.claude/hooks/*.py` | **no** | Codex hooks come from `~/.codex/config.toml` / a managed hooks dir, never from the repo |
| `.claude/settings.json` permissions | **no** | Codex approval policy and sandbox come from per-user config and CLI flags |

Verified against `codex-cli 0.152.1`. The probe commands, the raw output, and what to
re-check after a Codex upgrade are in `docs/tooling/codex-parity.md`.

## The safety asymmetry — read this before acting

Claude Code sessions in this repo run behind `.claude/hooks/guard_tool.py`, a PreToolUse hook
that *mechanically* denies permanent-deletion remote writes (`gh ... delete`, remote branch
deletion, force-push, `scripts/sync_labels.py --apply`) and appends every tool event to
`.agent/audit/tool-events.jsonl`. **Codex has no repo-level equivalent**, and a repo cannot
ship one.

In Codex those rules are enforced only by your having read them here:

- Do not run the permanent-deletion commands listed under *GitHub collaboration* without
  explicit human approval in the session.
- Do not force-push, and do not push to `main`.
- The dev-phase secret policy is **read-for-use, not read-to-share**: a credential value never
  goes into a command that leaves the machine, a log, a PR, or a comment.
- Nothing writes `.agent/audit/tool-events.jsonl` behind you. When you take an action the
  shared rules expect to be auditable, write the evidence where the rule says — the issue/PR
  comment, the run artifact, or `.agent/audit.jsonl` for KCA-policy decisions.

If you cannot honour a rule because this harness lacks the mechanism, say so in the session
rather than proceeding.

## Sub-agents

`.claude/agents/` holds Claude Code sub-agent definitions (`design-red-team`, `safety-guard`,
`milestone-reviewer`, `test-coverage-reviewer`, …). Codex 0.152.1 has no repo-level sub-agent
file format, so they are deliberately **not** mirrored into `.agents/`. When a shared workflow
calls for one, run the equivalent review yourself, in-session, against the same checklist —
the checklist lives in the matching skill or doc, not in the agent file — and say that the
review was not performed by an independent agent.

## Competition work

Per-competition code and config live under `competitions/<slug>/`. The per-competition
`kca-<slug>.yaml` — `autonomy.screen`, budgets, schedules — is the source of truth for what
the KCA product agent may submit without asking; it is not a licence for the harness to skip
the host-level confirmations above.
