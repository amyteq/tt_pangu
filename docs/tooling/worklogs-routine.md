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
  (`HARRY-ARCH`). On any other runner the gate finds no readable host Claude
  state and skips cleanly.
- **Command:** `exp_cc.py --all --allow-any-state --allow-secret-like
  --output-dir "$GITHUB_WORKSPACE/worklogs"`. (`--output-dir` is the only
  addition to the bare command — see "Why write into the checkout" below.)
- **Merge:** commits the worklogs to `main` with no human approval — direct push
  to `main`, falling back to an auto-merged PR if `main` is protected.

## The runner is native, not a container

The self-hosted runner runs as a **native systemd service** under user
`gha-runner` (`/opt/actions-runner/kca/runsvc.sh`) — it is **not** a Docker
container. So there is nothing to bind-mount; the only requirement is ordinary
**read** access on the host filesystem for the `gha-runner` user. `gha-runner`
is not a member of `harry`'s group, and `/home/harry` is mode `0700`, so out of
the box the runner can see nothing under it. The instructions below grant the
minimum read access with POSIX ACLs (the host is `ext4`, ACLs supported).

## Why write into the checkout (not the human's tree)

`exp_cc.py` must *read* the host transcripts, but it *writes* into the
gha-runner-owned Actions checkout (`$GITHUB_WORKSPACE`) via an absolute
`--output-dir`. That checkout is what gets committed and pushed (with the job's
`GITHUB_TOKEN`). Consequences:

- the runner needs **read-only** access to the host paths — never write;
- the human's live working tree at `HOST_REPO_DIR` is never staged, branched, or
  pushed from;
- `CLAUDE_PROJECT_DIR=HOST_REPO_DIR` is still required: `exp_cc.py` filters
  candidates to sessions whose working directory is inside it, so **only this
  project's** transcripts are dumped — not every project on the host.

## Runner permissions — exact setup ("broaden permissions")

Run these **once on the host as `harry`** (or anyone who can `setfacl` the
paths). They grant `gha-runner` read+traverse on just the Claude state and
traverse to the repo — nothing else under `/home/harry` becomes readable.

```bash
RUNNER=gha-runner
CLAUDE="$(readlink -f ~/.claude)"   # /home/harry/.claude-ayla

# 1. Let the runner TRAVERSE (pass through, not list) the home dir + repo path.
setfacl -m u:${RUNNER}:--x /home/harry
setfacl -m u:${RUNNER}:--x "${CLAUDE}"
setfacl -m u:${RUNNER}:--x /home/harry/test          # /home/harry/test/tt_pangu is already 0755

# 2. Grant recursive read+traverse on the session state this project needs.
#    Scoped to THIS project's transcript dirs (main + worktrees) so other
#    projects' transcripts stay private. jobs/ holds the session index.
setfacl -R -m  u:${RUNNER}:rX "${CLAUDE}/jobs"
setfacl -R -d -m u:${RUNNER}:rX "${CLAUDE}/jobs"     # default ACL -> new files inherit
setfacl -m u:${RUNNER}:r-x "${CLAUDE}/projects"      # list project dir names only
for d in "${CLAUDE}"/projects/-home-harry-test-tt-pangu*; do
  setfacl -R -m  u:${RUNNER}:rX "$d"
  setfacl -R -d -m u:${RUNNER}:rX "$d"               # default ACL -> new transcripts inherit
done

# 3. Verify as the runner user.
sudo -u ${RUNNER} bash -c 'ls ~harry/.claude/jobs >/dev/null && echo OK-jobs;
  ls ~harry/.claude/projects/-home-harry-test-tt-pangu/ >/dev/null && echo OK-transcripts'
```

The **default ACLs** (`-d`) matter: Claude writes new transcript/job files
continuously, and without an inherited ACL each new file would be unreadable to
the runner until you re-run `setfacl`.

Broader, simpler alternative (if scoping per-project dir is fiddly): grant
`setfacl -R -m u:${RUNNER}:rX "${CLAUDE}/projects"` plus the matching `-d`
default. **Security note:** that exposes *every* project's transcripts on the
host to the runner (and thus to any workflow that runs on it), so prefer the
scoped loop above. Either way the committed worklogs are limited to this
project (the `CLAUDE_PROJECT_DIR` filter) and secrets are masked at write time.

Other host requirements:

| Need | Item | Notes |
|---|---|---|
| Python env | micromamba env `v3.12.12` | Same env as `self-hosted-smoke.yml`. |
| Markdown render | `uvx` / `uv` | Auto-installed into the env by the workflow if missing. |
| Push | `github.com` over HTTPS | Uses the job `GITHUB_TOKEN`; no SSH key needed. |
| Discovery (optional) | `claude` CLI | Improves named-agent discovery; absent → falls back to `jobs/*/state.json`. |

## Repo variables to set

All host paths + the env name are overridable as repo (or org) **Variables**
(Settings → Secrets and variables → Actions → Variables). Only `CI_RUNNER` is
required for routing; the rest are only needed if the defaults below are wrong.

| Variable | Current / default value | Required? | Purpose |
|---|---|---|---|
| `CI_RUNNER` | `arch-ci` | yes (already set) | Self-hosted runner label. |
| `HOST_REPO_DIR` | `/home/harry/test/tt_pangu` | no (default in workflow) | Discovery root / `CLAUDE_PROJECT_DIR`. |
| `HOST_CLAUDE_DIR` | `/home/harry/.claude` | no (default in workflow) | `CLAUDE_CONFIG_DIR` (symlink → `.claude-ayla`). |
| `WORKLOG_MAMBA_ENV` | `v3.12.12` | no (default in workflow) | micromamba env to use. |

```bash
# To pin them explicitly (optional; matches the defaults):
gh variable set HOST_REPO_DIR     --body /home/harry/test/tt_pangu
gh variable set HOST_CLAUDE_DIR   --body /home/harry/.claude
gh variable set WORKLOG_MAMBA_ENV --body v3.12.12
```

## Secret masking

`--allow-secret-like` no longer writes raw secrets. Any matched secret body is
masked before the file is written — first/last 3 chars kept, the rest replaced
with `*` — and private-key blocks collapse to a single `[REDACTED]` marker. The
refusal-without-the-flag behaviour is unchanged, so interactive runs still get an
explicit "inspect this" prompt; automation passes the flag and gets masked output.

## Behaviour notes / caveats

- **No spurious commits.** The dump header carries no `Exported at` timestamp,
  so an unchanged session re-exports to byte-identical Markdown — the commit
  step no-ops and only real content changes produce a commit. (If the
  `claude-code-log` renderer itself ever emits a generation timestamp, residual
  churn would come from there, not this tool.)
- **No filename collisions.** Sessions with the same name no longer overwrite
  each other: the first keeps `<name>.md`, the rest get a stable
  `<name>_<short session id>.md` (id-based, not date-based, so filenames are
  stable across runs).
- **Growth.** `worklogs/` accumulates one file per session indefinitely.
  Consider a periodic prune (e.g. keep the last N days) if it gets large.
- **Masking is heuristic.** It catches the known key/token shapes in
  `SECRET_PATTERNS`; it is a safety net, not a guarantee. Treat worklogs as
  internal even though they are masked.
