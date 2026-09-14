# Claude Code ↔ Codex parity

Phase 1 runs the same competition workflow from **Claude Code CLI** and from **Codex /
ChatGPT desktop** against the same repo state, so the two harnesses can be compared on
different competitions (discussion #185, issue #189).

This document records what each harness actually loads, how that was established, and the
smoke check to run before trusting a competition to the Codex side.

## What maps to what

| Concern | Claude Code | Codex | Same content? |
|---|---|---|---|
| Project instructions | `CLAUDE.md` | `AGENTS.md` | **yes** — `AGENTS.md` is generated from `CLAUDE.md` + `docs/instructions/agents-delta.md` by `scripts/gen_agents.py` |
| Skills | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` | **yes** — `.agents/skills/<name>` is a symlink to the `.claude/` body; one file on disk |
| Sub-agents | `.claude/agents/*.md` | — | **no counterpart** (see below) |
| Tool gating | `.claude/hooks/guard_tool.py` (PreToolUse) | — | **no counterpart** — the safety asymmetry |
| Formatting gate | `.claude/hooks/format_gate.py` (PreToolUse) | — | **no counterpart**; run `ruff format --check .` by hand |
| Tool audit trail | `.agent/audit/tool-events.jsonl` (written by `audit_event.py`) | — | **no counterpart** — nothing is written behind a Codex session |
| Pre-approved commands | `.claude/settings.json` → `permissions.allow` | per-user `~/.codex/config.toml` + CLI flags | **no** — the repo cannot pre-approve commands for Codex |

`.agents/README.md` carries the same table from the mirror's side, generated.

## Evidence

Everything below was established against **`codex-cli 0.152.1`** with
`codex debug prompt-input`, which renders the exact model-visible prompt without making a
network call, spending usage, or touching the repo. An isolated `CODEX_HOME` keeps the
human's own Codex config and user-level skills out of the result:

```sh
mkdir -p /tmp/codex-probe-home
CODEX_HOME=/tmp/codex-probe-home codex debug prompt-input "Start work on competitions/arc-agi2" > probe.json
```

### 1. `AGENTS.md` is loaded, in full

`probe.json` contains a `user` message:

```
# AGENTS.md instructions for <repo>

<INSTRUCTIONS>
<!-- GENERATED FILE — DO NOT EDIT BY HAND. ...
```

17 115 bytes on disk, 17 149 characters in the prompt — i.e. **not truncated**, including
the last section and the submission-strategy table.

> **Budget:** Codex truncates the project doc at `project_doc_max_bytes` (32 KiB by default)
> and says so in its log, *not* in the prompt. A silently half-loaded `AGENTS.md` would drop
> whichever rules sort last. `tests/test_instruction_parity.py` fails if `AGENTS.md` crosses
> 32 KiB; keep `CLAUDE.md` lean (issue #188) rather than raising the limit.

### 2. `.agents/skills/` is a real Codex skill root, and symlinks are followed

```
### Skill roots
- `r0` = `<CODEX_HOME>/skills/.system`
- `r1` = `<repo>/.agents/skills`
```

All 17 mirrored skills appear under `### Available skills` as
`- <name>: <description> (file: r1/<name>/SKILL.md)` — every one of them a symlink into
`.claude/skills/`. Skills keep the name from their front matter, not the directory name, and
Claude-Code-only front-matter keys (`allowed-tools`, `argument-hint`) do not stop a skill
being listed.

### 3. `.claude/` is invisible to Codex

A probe fixture with a skill under `.claude/skills/` and an identical one under
`.agents/skills/` lists only the `.agents/` one. This is why the mirror exists at all.

### 4. Sub-agents have no repo-level format

A `.agents/agents/<name>.md` fixture (Claude Code's sub-agent shape) produced no sub-agent
entry in the prompt, with default features and with `--enable multi_agent_v2`. Codex
sub-agents come from user config / plugins, not from repo files, so `.claude/agents/` is
deliberately not mirrored.

### 5. Hooks have no repo-level format

Codex does support hooks, but they are configured in `~/.codex/config.toml` or a managed
hooks directory — per-user, never shipped by a repository. `.claude/hooks/guard_tool.py`
therefore protects Claude Code sessions only. In Codex the deletion / force-push / secret
rules are enforced only by the agent having read them in `AGENTS.md`, and no tool-event
audit trail is written. Treat that as a known gap, not as an accident.

## Smoke check

### A. Loader-level — automated, no account needed

```sh
python scripts/gen_agents.py --check                             # AGENTS.md + .agents/ are current
python -m pytest tests/test_instruction_parity.py -q             # parity + mirror invariants
mkdir -p /tmp/codex-probe-home
CODEX_HOME=/tmp/codex-probe-home codex debug prompt-input "x" \
  | grep -c 'file: r1/'                                          # == number of mirrored skills
```

The first two run in CI (`.github/workflows/test.yml` → `no-db pytest`). The third needs a
local `codex` binary, so it stays a manual/local step.

### B. Task-level — run by the human, once per Codex upgrade

Needs an interactive Codex login and spends the human's Codex usage, so it is not automated.
Pick a competition whose next step is cheap and read-only, and run the *same* task in both
harnesses from the same commit:

```sh
git rev-parse HEAD                       # same repo state for both runs

# Claude Code
claude "Using the kg-run skill, initialise a run directory for competitions/arc-agi2 and stop before training."

# Codex
codex "Using the kg-run skill, initialise a run directory for competitions/arc-agi2 and stop before training."
```

Record, in the competition's tracking issue:

- whether each harness found and used the skill by name;
- whether each produced the same `runs/<competition>/<run_id>/` layout;
- every point where Codex proceeded without the confirmation Claude Code's hook would have
  forced — those are the asymmetry, and they belong in the comparison write-up.

## After a Codex upgrade

Re-run smoke check A and confirm:

- `.agents/skills` still appears in the skill-roots table;
- the mirrored skill count is unchanged;
- `AGENTS.md` still loads untruncated;
- `.claude/agents/`-shaped files are still unsupported — if Codex gains a repo-level
  sub-agent format, mirroring them becomes a real option and this document (and
  `scripts/gen_agents.py`) should change.

Note the observed `codex --version` in the PR that records the result.
