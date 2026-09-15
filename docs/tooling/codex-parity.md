# Claude Code ↔ Codex parity

Phase 1 runs the same competition workflow from **Claude Code CLI** and from **Codex /
ChatGPT desktop** against the same repo state, so the two harnesses can be compared on
different competitions (discussion #185, issue #189).

This document records what each harness actually loads, how that was established, and the
smoke check to re-run before trusting a competition to the Codex side.

## What maps to what

| Concern | Claude Code | Codex | Same content? |
|---|---|---|---|
| Project instructions | `CLAUDE.md` | `AGENTS.md` | **yes** — `AGENTS.md` is generated from `CLAUDE.md` + `docs/instructions/agents-delta.md` by `scripts/gen_agents.py` |
| Skills | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` | **yes** — `.agents/skills/<name>` is a symlink to the `.claude/` body; one file on disk |
| Sub-agents | `.claude/agents/*.md` | — | **no counterpart** (see below) |
| Tool gating | `.claude/hooks/guard_tool.py` (PreToolUse) | — | **no counterpart** — the safety asymmetry |
| Formatting gate | `.claude/hooks/format_gate.py` (PreToolUse) | — | **no counterpart**; run `ruff format --check .` by hand |
| Tool audit trail | `.agent/audit/tool-events.jsonl` (`audit_event.py`, PostToolUse on `Bash`/`Edit`/`Write`) | — | **no counterpart** — nothing is written behind a Codex session |
| Pre-approved commands | `.claude/settings.json` → `permissions.allow` | per-user `~/.codex/config.toml` + CLI flags | **no** — the repo cannot pre-approve commands for Codex |

`.agents/README.md` carries the same table from the mirror's side, generated.

### What the Claude-side guard does and does not do

The asymmetry is real but it is not "Claude Code is safe, Codex is not". `guard_tool.py`
matches a **pattern list** (`.claude/hooks/guard_tool.py:120-145`): force-push, remote branch
deletion, `gh <resource> delete`, `scripts/sync_labels.py --apply`, and some host-destructive
shell. It recognises the spellings it lists, not the intent — a global flag placed before the
subcommand (`gh --repo <owner/repo> issue delete …`) does not match the `gh` deletion pattern.
`audit_event.py` is registered for `Bash`, `Edit`, `Write` and config changes
(`.claude/settings.json:240-260`), so it is not a log of *every* tool call.

Treat the hook as a backstop against an obvious slip, never as a proof that an action was
permitted or recorded — in either harness. The pattern gap is tracked separately in
[#204](https://github.com/amyteq/tt_pangu/issues/204).

## Evidence

Established with `codex debug prompt-input`, which renders the exact model-visible prompt
without a network call, without spending usage, and without touching the repo. An isolated
`CODEX_HOME` keeps the human's own Codex config and user-level skills out of the result:

```sh
mkdir -p /tmp/codex-probe-home
CODEX_HOME=/tmp/codex-probe-home codex debug prompt-input "Start work on competitions/arc-agi2" > probe.json

# commit the excerpt; refuses to write unless AGENTS.md at <commit> is the file it measured
python scripts/render_codex_probe.py probe.json AGENTS.md \
  docs/evidence/issue-189-codex-parity/loader-probe.txt "$(git rev-parse --short HEAD)"
```

Last run: **`codex-cli 0.154.0`** against a clean worktree at **`4d295d8`**. That attribution is
checked rather than asserted — the evidence file is only written if `4d295d8` is HEAD, its
`AGENTS.md` is byte-identical to the file whose load was measured, **and** the rendered dump
actually carries that same file, so the numbers reproduce from that commit.
Commits after it touch only this document, the evidence under
`docs/evidence/issue-189-codex-parity/` and the writer scripts — outputs of the run and the tools
that record it, never inputs to it. That is the claim that matters, and it is checkable rather
than taken on trust:

```sh
git diff --name-only 4d295d8 HEAD -- AGENTS.md CLAUDE.md .agents .claude   # must be empty
```

If that prints anything, the numbers below describe a file that no longer exists and the probe
needs re-running. It is deliberately **not** a CI test: re-collecting needs a local `codex`
binary, and making every `CLAUDE.md` edit depend on one would cost more than the staleness it
catches. Raw excerpt at `docs/evidence/issue-189-codex-parity/loader-probe.txt`.

### 1. `AGENTS.md` is loaded, in full

The prompt carries a `user` message beginning:

```
# AGENTS.md instructions for <repo>

<INSTRUCTIONS>
<!-- GENERATED FILE — DO NOT EDIT BY HAND. ...
```

`AGENTS.md` is **20 445 bytes / 20 305 characters** on disk; the project-doc message in the
prompt is **20 434 characters**. The difference is Codex's own wrapper — the
`# AGENTS.md instructions for <absolute path>` header and the `<INSTRUCTIONS>` tags — so that
total is path-dependent and is **not** a checksum of the file. What shows the file loaded whole
is the pair of sentinels: the opening banner and the closing line of the appendix are both
present, and no truncation marker appears.

> **Budget:** Codex truncates the project doc at `project_doc_max_bytes` (32 KiB by default)
> and says so in its log, *not* in the prompt. A silently half-loaded `AGENTS.md` would drop
> whichever rules sort last. `tests/test_instruction_parity.py` fails if `AGENTS.md` crosses
> 32 KiB; keep `CLAUDE.md` lean rather than raising the limit.

### 2. `.agents/skills/` is a real Codex skill root, and symlinks are followed

```
### Skill roots
- `r0` = `<CODEX_HOME>/skills/.system`
- `r1` = `<repo>/.agents/skills`
```

All **17** mirrored skills appear under `### Available skills` as
`- <name>: <description> (file: r1/<name>/SKILL.md)` — every one of them a symlink into
`.claude/skills/`. A skill is listed under its front-matter `name`, not its directory name
(which is why `gen_agents.py` fails when the two disagree), and Claude-Code-only front-matter
keys (`allowed-tools`, `argument-hint`) do not stop a skill being listed.

### 3. `.claude/` is invisible to Codex

In a fixture repo holding both `.claude/skills/cc-probe/` and `.agents/skills/kg-probe/`, only
the `.agents/` one is listed. Adding `.agents/skills/cc-probe-link ->
../../.claude/skills/cc-probe` makes the same body appear — sourced explicitly from
`r1/cc-probe-link/SKILL.md`. That is the whole reason the mirror exists.

### 4. Sub-agents have no repo-level format

An `.agents/agents/<name>.md` fixture (Claude Code's sub-agent shape) produces no sub-agent
entry, with default features and with `--enable multi_agent_v2`. Codex sub-agents come from
user config / plugins, not repo files, so `.claude/agents/` is deliberately not mirrored.

### 5. Hooks have no repo-level format

Codex does support hooks, but they are configured in `~/.codex/config.toml` or a managed hooks
directory — per-user, never shipped by a repository.

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

### B. Task-level — the same task in both harnesses

**Run it read-only.** An earlier draft of this check proposed `kg-run` "initialise a run
directory", which *writes*: the second harness would then see a repo the first one had already
modified, and the comparison would be of two different states. Either keep the task read-only,
or give each harness its own worktree checked out at the same SHA.

**Collect it from a clean worktree.** Record the commit only when `git status` is clean —
evidence gathered from a dirty tree names a commit whose files are not the ones that were
measured, which is worse than naming no commit at all because it looks checkable. The same
goes for the loader probe above.

Both writers enforce that through one shared check, `scripts/evidence_provenance.py`, which
refuses unless the named commit is HEAD and nothing differs from it — modified, staged or
**untracked** — except the three files the writers themselves emit. Untracked counts because an
untracked `.agents/skills/<name>/SKILL.md` is loaded by Codex and inflates a measured skill
count without appearing in `git diff`. The exemption is that explicit list of three outputs, not
the evidence directory: `smoke-prompt.txt` is an *input*, and the smoke header's "prompt
unmodified" claim is worthless if an edited prompt is exempt from the check that backs it.

It is one shared function because three consecutive review rounds found this section claiming a
guarantee the scripts did not implement — first neither compared its commit argument to HEAD,
then the renderer never looked at the working tree at all while this paragraph said both writers
did. Two implementations meant two chances to be wrong.

On top of that shared check, each writer verifies what only it can:

- `scripts/render_codex_probe.py` — that `AGENTS.md` at the named commit is byte-identical to
  the file being measured, **and** that the dump's project-doc message contains that same file,
  which is what catches a stale `probe.json` rendered after an edit. The binary version in the
  header is read at render time, so render right after probing.
- `scripts/write_codex_smoke_evidence.py` — that both answer files exist and are non-empty.

Neither can check which binary produced a dump or an answer file, or that an answer file came
from the run you believe it did. Those stay attestations; pass the paths explicitly so the
provenance is at least visible at the call site.

Prompt (`docs/evidence/issue-189-codex-parity/smoke-prompt.txt`) asks, read-only, which skill
initialises a run directory for `competitions/arc-agi2`, what the dev-phase secret policy
permits for `~/.kaggle/kaggle.json`, and which files said so — exercising project-doc loading
and skill discovery at once.

```sh
git status --porcelain        # must be empty: both harnesses read the working tree
prompt=docs/evidence/issue-189-codex-parity/smoke-prompt.txt

time codex exec -m gpt-5.6-sol -c model_reasoning_effort=low --sandbox read-only \
  -o /tmp/smoke-codex.txt - < "$prompt"

time claude -p --model 'claude-opus-5[1m]' "$(cat "$prompt")" > /tmp/smoke-claude.txt

# commit both answers with a header whose commit claim is verified, not asserted
python scripts/write_codex_smoke_evidence.py \
  --codex  /tmp/smoke-codex.txt  --codex-seconds  15 \
  --claude /tmp/smoke-claude.txt --claude-seconds 16
```

**Result — clean worktree at `4d295d8`, 2026-09-15**, both harnesses run from the same commit
(full outputs, with their own provenance headers, under `docs/evidence/issue-189-codex-parity/`):

| | Codex (`codex-cli 0.154.0`, `gpt-5.6-sol`) | Claude Code (`claude-opus-5[1m]`) |
|---|---|---|
| Skill found | `kg-run` | `kg-run` |
| Run path | `runs/arc-agi2/<run_id>/` | `runs/arc-agi2/<run_id>/`, run id UTC `YYYYMMDD_HHMMSS`, with `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` gitignored |
| Secret policy | may read to use the credentials; forbids printing, sharing, logging or copying them externally | may **read** for use; never echo or copy into web fetches, logs, public PRs, comments ("read-for-use, not read-to-share") |
| Cited instruction file | `AGENTS.md` | `CLAUDE.md:65` — *Dev-phase secret policy* |
| Cited skill file | `.agents/skills/kg-run/SKILL.md` | `.claude/skills/kg-run/SKILL.md` |
| Wall clock | 15 s | 16 s |

Both harnesses reached the same rules through their own surface, and each cited the surface it
actually reads — which is exactly what the mirror is supposed to produce. The Claude side
answered in more detail; that is a model/harness difference, not an instruction difference.

When a competition is actually driven from both harnesses, record the paired result in that
competition's tracking issue, and note every point where Codex proceeded without a
confirmation Claude Code's hook would have forced.

## After a Codex upgrade

Codex updates itself; this document was already refreshed once from 0.152.1 to 0.154.0 when the
binary moved under it. Re-run smoke check A and confirm:

- `.agents/skills` still appears in the skill-roots table;
- the mirrored skill count is unchanged;
- `AGENTS.md` still loads untruncated;
- `.claude/agents/`-shaped files are still unsupported — if Codex gains a repo-level sub-agent
  format, mirroring them becomes a real option and this document (and `scripts/gen_agents.py`)
  should change.

Record the observed `codex --version` in the PR that carries the result, and bump
`CODEX_VERSION` in `scripts/gen_agents.py` — the single place `AGENTS.md` and
`.agents/README.md` take it from — then regenerate.
