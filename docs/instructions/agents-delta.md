<!--
Source fragment for the generated `AGENTS.md`.

`AGENTS.md` = this file's PREAMBLE part
            + the body of `CLAUDE.md` (verbatim — the shared rules)
            + this file's APPENDIX part.

Edit this file (or `CLAUDE.md`) and run `python scripts/gen_agents.py`.
Never edit `AGENTS.md` directly — `scripts/gen_agents.py --check` (and
`tests/test_instruction_parity.py`) will fail.

Markdown here is soft-wrapped (ADR-0024): one paragraph, list item or table row
is one physical line. It is copied into `AGENTS.md`, which carries that rule.
-->

<!-- part: preamble -->
# AGENTS.md — cross-harness project instructions

> Canonical language: **English**. `CLAUDE.md` is the authoritative source of the shared rules below; this file is generated from it. Chinese lives only in `*_zh.md` sidecars ([`CLAUDE_zh.md`](./CLAUDE_zh.md)), which are human-reading mirrors, never authoritative.

This file is what **Codex / ChatGPT** — and any other `AGENTS.md`-reading harness — loads when it opens this repository. `CLAUDE.md` is what **Claude Code** loads. They have to say the same thing: phase 1 runs the same competition workflow from both harnesses so the two can be compared on different competitions (discussion #185, issue #189).

## How to read this file

- Everything under **Shared rules** is generated verbatim from `CLAUDE.md`. If a rule here disagrees with `CLAUDE.md`, `CLAUDE.md` wins and the generator is broken — say so in the session instead of following the stale copy.
- The shared rules were written for the Claude Code harness and name it throughout. Read those mentions in **two different ways**, and do not collapse them into one:
  - **Obligations bind you.** "The Claude Code harness still asks before X", "routing rules binding on every Claude Code session" — these are *harness* duties, and they bind this session exactly as they bind a Claude Code one. Ask before destructive host commands and before paid-API / credential use. Follow the GitHub rules **as written**, in both directions: the permanent-deletion list needs explicit human approval, and the non-destructive writes that section auto-allows — including pushing a feature branch and the phase-1 self-merge — are auto-allowed here too. Do not invent a wider approval rule than the shared rules state; a Codex session that asks where Claude Code proceeds is not running the same workflow, which is the whole point of phase 1.
  - **Mechanisms are not yours.** `.claude/hooks/guard_tool.py`, `.claude/settings.json` permissions, the `.agent/audit/tool-events.jsonl` trail — these describe machinery that runs in Claude Code and **does not exist in this harness**. Never read a mention of them as a statement that something is being enforced or recorded for you. Where a shared rule leans on one, you honour it unaided; *The safety asymmetry* below says exactly where that bites.
- The distinction that is **not** interchangeable is the one in *Two agents: Claude Code harness vs KCA product*. A rule about the KCA product agent is never automatically a rule about the harness you are, and vice versa; conflating them is the root cause of issue #65. In particular, that section's "Claude Code harness" bullet describes Claude Code's governance, not yours — yours is this file plus whatever approval mode the human has set.

## Read first

- `PROJECT_STATE.md`
- the competition's **tracking issue** and `competitions/<slug>/` — in phase 1 those two are the state of record, not a milestone doc and not Supabase
- `docs/adr/` — especially `docs/adr/0022-long-run-competition-operating-model.md` (the long-run operating model, its §5 autonomy grant and the activation conditions that grant is still waiting on) and `docs/adr/0021-kca-autonomy-model.md` (the KCA autonomy model it widens, and the four-scenario daily submission strategy in §4)
- `docs/engineering-practice.md` — the full GitHub collaboration model
- `.agents/README.md` — what of `.claude/` this harness can and cannot consume

**Precedence.** The **Shared rules** below win over every other document in this repository. Several docs predate the phase-1 rewrite (#188, #200) and still describe the older model — approval for every remote write, or the Claude Agent SDK as the production worker. Where one of them carries a *Superseded* note, believe the note. Where you find a contradiction with no note, the Shared rules are current, and saying so in the session is more useful than following the older text.

## Source of truth

This repository is the durable project memory. No AI product's hidden memory is shared across harnesses, so any decision that must survive a context reset belongs in a file: `PROJECT_STATE.md`, `docs/adr/`, `docs/architecture/`, `docs/tooling/`, `docs/testing/`, `docs/meeting-notes/`, or the GitHub issue / discussion it came from.

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

Verified against `codex-cli {{CODEX_VERSION}}`. The probe commands, the raw output, and what to re-check after a Codex upgrade are in `docs/tooling/codex-parity.md`.

## The safety asymmetry — read this before acting

Claude Code sessions in this repo run behind `.claude/hooks/guard_tool.py`, a PreToolUse hook that refuses a *pattern list* of destructive commands — force-push, remote branch deletion, `gh <resource> delete`, `scripts/sync_labels.py --apply`, and some host-destructive shell — and `.claude/hooks/audit_event.py`, a PostToolUse hook registered for `Bash`, `Edit` and `Write` (plus config changes) that appends those events to `.agent/audit/tool-events.jsonl`. **Codex has no repo-level equivalent of either**, and a repository cannot ship one: Codex hooks are per-user config, never repo-shipped.

Two things follow, and the second is easy to get wrong:

1. **In this harness those rules are enforced only by your having read them here.** Nothing will stop you.
2. **Even in Claude Code the hook is a backstop, not a proof.** It matches patterns, not intent: it recognises `gh issue delete …` but not every spelling of it (a global flag before the subcommand, for one), and the audit trail covers `Bash`/`Edit`/`Write`, not every tool. So "the hook would have caught it" is never a reason to attempt something — in either harness.

Concretely, in this session:

- Do not run the permanent-deletion commands listed under *GitHub collaboration* without explicit human approval in the session.
- Do not force-push, and do not push to `main`. Neither is approvable: the shared rules deny force-push outright rather than gating it.
- The dev-phase secret policy is **read-for-use, not read-to-share**: a credential value never goes into a command that leaves the machine, a log, a PR, or a comment.
- Nothing writes `.agent/audit/tool-events.jsonl` behind you. When you take an action the shared rules expect to be auditable, write the evidence where the rule says — the issue/PR comment, the run artifact, the competition's own submission record, or KCA's audit log (`.agent/kca/audit.jsonl` today; the path is phase-2 work, see [#203](https://github.com/amyteq/tt_pangu/issues/203)) for KCA-policy decisions.

If you cannot honour a rule because this harness lacks the mechanism, say so in the session rather than proceeding.

## Sub-agents

`.claude/agents/` holds Claude Code sub-agent definitions (`design-red-team`, `safety-guard`, `milestone-reviewer`, `test-coverage-reviewer`, …). Codex {{CODEX_VERSION}} has no repo-level sub-agent file format, so they are deliberately **not** mirrored into `.agents/`. When a shared workflow calls for one, run the equivalent review yourself, in-session, against the same checklist — the checklist lives in the matching skill or doc, not in the agent file — and say that the review was not performed by an independent agent.

## Competition work

Per-competition code and config live under `competitions/<slug>/`; in phase 1 that directory plus the competition's tracking issue are the state of record. The file `competition.yaml:autonomy_config` names — conventionally `kca-<slug>.yaml` — holds that competition's `autonomy` block, budgets and schedules, and it describes what the **KCA product agent** would be permitted to submit without asking.

Read it as configuration, not as permission, and never as a licence for the harness — you — to skip the confirmations above. The wide grant switches on only for a competition that satisfies ADR-0022 §5's activation conditions **A1-A7**; no competition satisfies them, ADR-0021 §2's screened fallback is unimplemented, and no code reads the `autonomy:` block at all. So in this session, **ask before every Kaggle submission and every kernel push**, exactly as *Operating principles* → 6 says. A kernel push is not a leaderboard submission (#77), and both are asked for.

Phase 1 exists to compare harnesses, so say which one you are in the tracking issue when you record a result — a run driven from Codex and one driven from Claude Code are different data points, not interchangeable ones.
