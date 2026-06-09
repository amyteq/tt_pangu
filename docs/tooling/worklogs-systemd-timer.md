# Worklogs dump — systemd user timer (active)

The daily worklogs dump runs as a **systemd user timer** under the account that
owns the Claude sessions (e.g. `harry`). Running as that user is what makes this
simple: it has natural read access to `~/.claude` and the repo, so there are
**no cross-user ACLs** and no "expose every project's transcripts to a CI
runner" trade-off. (This supersedes the GitHub Actions approach in
[`worklogs-routine.md`](./worklogs-routine.md), which is now disabled.)

## Pieces (all source-controlled)

| File | Role |
|---|---|
| `scripts/worklogs_dump.sh` | the actual job: dump → commit → PR → merge-after-green |
| `scripts/systemd/worklogs-dump.service` | oneshot unit that runs the script |
| `scripts/systemd/worklogs-dump.timer` | fires daily at 02:00 `Australia/Melbourne` |

## What the job does

1. `git fetch` the base branch and lay down a **throwaway detached worktree** on
   `origin/main` — your working tree and current branch are never touched.
2. Run `scripts/exp_cc.py --all --allow-any-state --allow-secret-like` into that
   worktree's `worklogs/` (secrets masked at write time; only **this** project's
   sessions, via `CLAUDE_PROJECT_DIR`).
3. If nothing changed, exit quietly (the timestamp-free headers mean unchanged
   sessions produce no diff).
4. Otherwise commit on a branch, push, open a PR, and **merge it once the build
   is green** (GitHub native auto-merge if enabled, else it watches the checks
   and merges). Set `WORKLOG_MERGE_MODE=direct` to push straight to `main`
   instead.

Auth uses your existing `gh` login as a one-shot git credential helper
(`gh auth git-credential`) — no SSH-agent dependency, no token on the command
line, no change to your global gitconfig.

## Install (user timer — recommended, no root)

```bash
cd ~/test/tt_pangu
chmod +x scripts/worklogs_dump.sh        # already +x in git, but just in case

# 1. Link the units into the user systemd dir (symlink => updates with git pull).
mkdir -p ~/.config/systemd/user
ln -sf "$PWD/scripts/systemd/worklogs-dump.service" ~/.config/systemd/user/
ln -sf "$PWD/scripts/systemd/worklogs-dump.timer"   ~/.config/systemd/user/

# 2. Reload + enable the timer.
systemctl --user daemon-reload
systemctl --user enable --now worklogs-dump.timer

# 3. Let user services run even when you're not logged in (needed for 02:00).
#    This one needs sudo (it's a system-level setting for your user).
sudo loginctl enable-linger "$USER"

# Verify
systemctl --user list-timers worklogs-dump.timer
```

Prerequisites on the machine (already true on HARRY-ARCH): `gh` logged in
(`gh auth status`), `micromamba` with env `v3.12.12`, and the repo at
`~/test/tt_pangu` (override with `WORKLOG_REPO_DIR`). The unit files use `%h`
(your home), so no path is hard-coded to a specific user.

### Test it now (no waiting until 02:00)

```bash
systemctl --user start worklogs-dump.service      # run once immediately
journalctl --user -u worklogs-dump.service -n 100 --no-pager   # see the log
# or run the script directly to watch output live:
~/test/tt_pangu/scripts/worklogs_dump.sh
```

### Configuration

Override defaults via the environment (e.g. uncomment `Environment=` lines in
the `.service`, or export before a manual run). See the header of
`scripts/worklogs_dump.sh` for the full list: `WORKLOG_REPO_DIR`,
`WORKLOG_MAMBA_ENV`, `WORKLOG_BASE`, `WORKLOG_MERGE_MODE` (`pr`|`direct`),
`WORKLOG_CI_TIMEOUT`, `WORKLOG_GIT_NAME`/`WORKLOG_GIT_EMAIL`, `GH_REPO`.

### Alternative: system service (runs without linger)

If you prefer a system-level service instead of a user timer + linger, copy the
units to `/etc/systemd/system/`, add `User=<you>` / `Group=<you>` and
`Environment=HOME=/home/<you>` under `[Service]`, then
`sudo systemctl enable --now worklogs-dump.timer`. The user-timer route above is
preferred (no root, no `/etc` edits, units track the repo via symlink).

## Uninstall

```bash
systemctl --user disable --now worklogs-dump.timer
rm ~/.config/systemd/user/worklogs-dump.{service,timer}
systemctl --user daemon-reload
# optional: sudo loginctl disable-linger "$USER"
```

## Troubleshooting

- **Service fails instantly with no log output** (`status=1/FAILURE`,
  `journalctl` shows only systemd's own lines): almost always a
  variable/PATH that your interactive shell sets but a systemd service env does
  not. A systemd `--user` service starts with a minimal environment — it does
  **not** source `~/.bashrc`/`~/.profile`, so things like `MAMBA_ROOT_PREFIX`
  are absent. `scripts/worklogs_dump.sh` defaults `MAMBA_ROOT_PREFIX` and relaxes
  `set -u` around the micromamba hook for exactly this reason. To debug any
  variant, run the script directly (`~/test/tt_pangu/scripts/worklogs_dump.sh`)
  or under a stripped env (`env -i HOME="$HOME" PATH=/usr/bin:/bin
  scripts/worklogs_dump.sh`) to see the real error.
- **`gh: command not found` / auth errors** under the service: ensure `gh` is on
  the PATH the script builds, and that `gh auth status` is logged in for your
  user (the service runs as you and reads `~/.config/gh`).

## Caveats

- **Build cost.** `WORKLOG_MERGE_MODE=pr` opens a PR daily, which triggers the
  full CI suite for a Markdown-only change. If that's wasteful, set
  `WORKLOG_MERGE_MODE=direct` to commit straight to `main` (skips CI/PR).
- **Machine must be on.** A user timer only fires when the host is up;
  `Persistent=true` catches a missed run on the next boot.
- **Masking is heuristic** (see `SECRET_PATTERNS` in `exp_cc.py`). Treat worklogs
  as internal even though secrets are masked.
