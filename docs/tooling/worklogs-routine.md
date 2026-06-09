# Worklogs dump routine

`scripts/exp_cc.py` exports Claude Code session transcripts for this project to
Markdown. The `.github/workflows/worklogs-dump.yml` workflow runs it on a daily
schedule and merges the dumps into `main`.

## What runs

- **Schedule:** ~02:00 `Australia/Melbourne`, every day. GitHub cron is UTC-only
  and DST-unaware, so the workflow fires at **15:00 and 16:00 UTC** and a gate
  step proceeds only when the runner's local Melbourne hour is `02` — exactly
  once per day across AEDT/AEST.
- **Runner:** `runs-on: ${{ vars.CI_RUNNER || 'ubuntu-latest' }}`. With
  `vars.CI_RUNNER = arch-ci` this lands on the self-hosted Arch host
  (`HARRY-ARCH`), the same machine the Claude Code CLI runs on. On any other
  runner the gate finds no host Claude state and skips cleanly.
- **Command:** `exp_cc.py --all --allow-any-state --allow-secret-like`
  (default output dir is now `worklogs/`).
- **Merge:** commits the worklogs to `main` with no human approval — direct push
  to `main`, falling back to an auto-merged PR if `main` is protected.

## Why a fresh clone instead of the host checkout

The self-hosted runner runs as `gha-runner` inside a container; its home is
`/home/gha-runner`, and the repo's `origin` is SSH (`git@github.com:...`), whose
key belongs to the human and must not be used by the runner. So the workflow:

1. Sets `CLAUDE_CONFIG_DIR=/home/harry/.claude` and
   `CLAUDE_PROJECT_DIR=/home/harry/test/tt_pangu` and runs the exporter against
   the **host** state (read-only). The project dir matters because `exp_cc.py`
   filters sessions to those whose working directory is the project root.
2. Commits via a **fresh `https://x-access-token:$GITHUB_TOKEN@github.com/...`
   clone** of `main`, copying the dumped `worklogs/` in with `cp -a`. The human's
   live working tree is never staged, branch-switched, or pushed from.

## Runner prerequisites (the "broaden permissions" question)

The runner only needs **read** access to the host state — it never writes to the
human's home. Make sure the container/runner can:

| Need | Path / item | Notes |
|---|---|---|
| Read Claude sessions | `/home/harry/.claude/projects/**`, `/home/harry/.claude/jobs/**` | Bind-mount read-only into the container. |
| Resolve project dir | `/home/harry/test/tt_pangu` | Used as the discovery root; read access is enough. |
| Python env | micromamba env `v3.12.12` | Same env as `self-hosted-smoke.yml`; must contain (or be able to `pip install`) `uv`. |
| Markdown render | `uvx` / `uv` | `exp_cc.py` shells out to `uvx claude-code-log@latest`. |
| Push | `github.com` over HTTPS | Uses the job's `GITHUB_TOKEN`; no SSH key needed. |

The `claude` CLI is **optional** — it improves discovery of named agents, but
`exp_cc.py` falls back to reading `jobs/*/state.json` directly when it is absent.

If the container runs as a uid that can't read `/home/harry/.claude`, the simplest
fixes (pick one):

- bind-mount those paths read-only and run the container with `--user harry` (or
  a uid that matches the file owner), **or**
- add the runner's user to a group that has `r-x` on `/home/harry/.claude` and the
  relevant subtrees, **or**
- mount a read-only snapshot/copy of `~/.claude` at the path the workflow expects.

All host paths are overridable with repo/org **Variables** so nothing is
hard-coded if the layout changes:

| Variable | Default | Purpose |
|---|---|---|
| `CI_RUNNER` | `ubuntu-latest` | Runner label (already `arch-ci`). |
| `HOST_REPO_DIR` | `/home/harry/test/tt_pangu` | Discovery root / `CLAUDE_PROJECT_DIR`. |
| `HOST_CLAUDE_DIR` | `/home/harry/.claude` | `CLAUDE_CONFIG_DIR`. |
| `WORKLOG_MAMBA_ENV` | `v3.12.12` | micromamba env to activate. |

## Secret masking

`--allow-secret-like` no longer writes raw secrets. Any matched secret body is
masked before the file is written — first/last 3 chars kept, the rest replaced
with `*` — and private-key blocks collapse to a single `[REDACTED]` marker. The
refusal-without-the-flag behaviour is unchanged, so interactive runs still get an
explicit "inspect this" prompt; automation passes the flag and gets masked output.

## Suggestions / caveats for the dump routine

- **Every run produces a diff.** The dump re-exports all sessions and each file's
  header carries an `Exported at` timestamp, so expect a commit most days even
  when conversation content is unchanged. If that noise is unwanted, options are:
  drop the timestamp from the header, or only commit files whose body (excluding
  the header) changed.
- **Filenames are by session name.** Two sessions sharing a name overwrite each
  other within a run (pre-existing behaviour). Prefer `--id`-based naming if
  collisions matter.
- **Growth.** `worklogs/` accumulates one file per session indefinitely. Consider
  a periodic prune (e.g. keep the last N days) if the directory gets large.
- **Masking is heuristic.** It catches the known key/token shapes in
  `SECRET_PATTERNS`; it is a safety net, not a guarantee. Treat worklogs as
  internal even though they are masked.
