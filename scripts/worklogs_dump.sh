#!/usr/bin/env bash
# Daily Claude worklogs dump — runs as the user who owns the Claude sessions.
#
# Designed to be driven by the systemd *user* timer in scripts/systemd/, so it
# runs under your own account with natural read access to ~/.claude and the
# repo — no cross-user ACLs, no GitHub self-hosted-runner permissions. It:
#   1. exports this project's session transcripts to Markdown (masked) via
#      scripts/exp_cc.py, into a throwaway git worktree off origin/main so your
#      working tree / current branch is never touched;
#   2. if anything changed, commits on a branch, pushes, opens a PR, and (by
#      default) merges it once the build is green.
#
# Configuration (all optional; sensible defaults below):
#   WORKLOG_REPO_DIR   repo checkout to operate on        (default: ~/test/tt_pangu)
#   WORKLOG_MAMBA_ENV  micromamba env to activate         (default: v3.12.12)
#   WORKLOG_BASE       branch to dump from / merge into   (default: main)
#   WORKLOG_MERGE_MODE pr | direct                        (default: pr)
#   WORKLOG_CI_TIMEOUT seconds to wait for a green build  (default: 1800)
#   WORKLOG_GIT_NAME / WORKLOG_GIT_EMAIL  commit identity
#   GH_REPO            owner/name for gh + push           (default: amyteq/tt_pangu)
#   SKIP_RUFF_GATE=1   bypass the local pre-push ruff hook (md-only dumps are clean)
set -uo pipefail

log() { printf '[worklogs %s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() {
  log "ERROR: $*"
  exit 1
}

REPO_DIR="${WORKLOG_REPO_DIR:-$HOME/test/tt_pangu}"
MAMBA_ENV="${WORKLOG_MAMBA_ENV:-v3.12.12}"
BASE="${WORKLOG_BASE:-main}"
MERGE_MODE="${WORKLOG_MERGE_MODE:-pr}"
CI_TIMEOUT="${WORKLOG_CI_TIMEOUT:-1800}"
GH_REPO="${GH_REPO:-amyteq/tt_pangu}"
GIT_NAME="${WORKLOG_GIT_NAME:-tt-pangu-worklogs}"
GIT_EMAIL="${WORKLOG_GIT_EMAIL:-bot@ayla-app.com}"

# systemd user services start with a minimal PATH; make sure the usual tools
# (gh, git, micromamba, python shims) are reachable.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

command -v gh >/dev/null 2>&1 || die "gh CLI not found on PATH"
command -v git >/dev/null 2>&1 || die "git not found on PATH"
[ -d "$REPO_DIR/.git" ] || die "repo checkout not found at $REPO_DIR"

# Activate the micromamba env so exp_cc.py finds the right python + uvx.
# A systemd service env does NOT have MAMBA_ROOT_PREFIX (your shell profile sets
# it interactively), and `micromamba shell hook` expands it unguarded — under
# `set -u` that aborts the whole script before anything runs. So provide a
# default and relax nounset across the hook eval + activate.
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
MAMBA_EXE="$(command -v micromamba || echo "$HOME/.local/bin/micromamba")"
if [ -x "$MAMBA_EXE" ]; then
  set +u
  eval "$("$MAMBA_EXE" shell hook --shell bash)" || log "WARN: micromamba shell hook failed"
  micromamba activate "$MAMBA_ENV" || log "WARN: could not activate env $MAMBA_ENV"
  set -u
else
  log "WARN: micromamba not found; relying on PATH python"
fi

# Use gh as the git credential helper for this run only — no token in argv, no
# persistent gitconfig change, no dependency on an ssh-agent in the timer.
GIT_AUTH=(-c "credential.helper=!gh auth git-credential")

cd "$REPO_DIR" || die "cannot cd into $REPO_DIR"

# Fetch the base branch and lay down a detached, throwaway worktree on it so we
# never disturb the user's working tree or current branch.
git "${GIT_AUTH[@]}" fetch --quiet "https://github.com/${GH_REPO}.git" "$BASE" \
  || die "fetch of $BASE failed"
WT="$(mktemp -d -t worklogs-dump-XXXXXX)"
cleanup() {
  cd "$REPO_DIR" 2>/dev/null && git worktree remove --force "$WT" >/dev/null 2>&1
  rm -rf "$WT" 2>/dev/null
}
trap cleanup EXIT
git worktree add --force --detach "$WT" FETCH_HEAD >/dev/null 2>&1 \
  || die "could not create worktree at $WT"

# Dump this project's sessions into the worktree (masked). CLAUDE_PROJECT_DIR is
# the path the sessions ran in, so only THIS project's transcripts are dumped.
# Prefer the repo copy so the committed behaviour is always what runs.
EXP_PY="$REPO_DIR/scripts/exp_cc.py"
log "dumping worklogs -> $WT/worklogs"
CLAUDE_PROJECT_DIR="$REPO_DIR" \
  python "$EXP_PY" --all --allow-any-state --allow-secret-like \
  --output-dir "$WT/worklogs"
log "exp_cc.py exit code: $? (0=exported, 1=all failed, 2=no candidates)"

cd "$WT" || die "cannot cd into worktree"
git add worklogs
if git diff --cached --quiet; then
  log "no worklog changes since last run — nothing to commit."
  exit 0
fi

STAMP="$(TZ=Australia/Melbourne date '+%Y-%m-%d %H:%M %Z')"
git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" \
  commit --quiet -m "chore(worklogs): daily Claude session dump ($STAMP)"

# Direct mode: push straight to the base branch and stop.
if [ "$MERGE_MODE" = "direct" ]; then
  if git "${GIT_AUTH[@]}" push "https://github.com/${GH_REPO}.git" "HEAD:$BASE"; then
    log "pushed worklogs directly to $BASE."
    exit 0
  fi
  log "direct push to $BASE rejected — falling back to a PR."
fi

# PR mode (default): branch -> push -> PR -> merge after green build.
BR="chore/worklogs-$(TZ=Australia/Melbourne date '+%Y%m%d-%H%M%S')"
git switch -c "$BR" >/dev/null 2>&1 || git checkout -b "$BR"
git "${GIT_AUTH[@]}" push "https://github.com/${GH_REPO}.git" "HEAD:refs/heads/$BR" \
  || die "push of $BR failed"

PR_URL="$(gh pr create --repo "$GH_REPO" --base "$BASE" --head "$BR" \
  --title "chore(worklogs): daily Claude session dump ($STAMP)" \
  --body "Automated daily worklogs dump from scripts/exp_cc.py via the systemd user timer. Secrets are masked at write time. No human approval required; merges automatically once the build is green." \
  2>&1)" || die "gh pr create failed: $PR_URL"
log "opened PR: $PR_URL"

# Best-effort GitHub native auto-merge first. This needs the repo's "Allow
# auto-merge" setting AND a required check (branch protection). On a free
# private repo neither is available, so this almost always falls through to the
# polling path below — which is the real workhorse.
if gh pr merge "$BR" --repo "$GH_REPO" --squash --delete-branch --auto >/dev/null 2>&1; then
  log "native auto-merge enabled; GitHub will merge $BR when the build is green."
  exit 0
fi

# Poll until the build is green, then merge. Important: `gh pr checks --watch`
# returns IMMEDIATELY with a "no checks" error if it runs before the workflow
# has registered on the new PR (a race in the first seconds after opening it) —
# the old code mistook that for "checks failed" and bailed. So loop: keep
# retrying while no checks exist yet; once they appear, --watch blocks until
# they finish; only a genuine failure or the overall timeout stops us.
log "watching checks for $BR (timeout ${CI_TIMEOUT}s)."
deadline=$(( $(date +%s) + CI_TIMEOUT ))
green=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  checks_out="$(gh pr checks "$BR" --repo "$GH_REPO" --watch --fail-fast 2>&1)"
  checks_rc=$?
  if [ "$checks_rc" -eq 0 ]; then
    green=1
    break
  fi
  if printf '%s' "$checks_out" | grep -qiE 'no checks|no required check'; then
    sleep 15 # checks not registered yet — wait for the workflow to start
    continue
  fi
  log "checks failed for $BR — leaving PR open for review: $PR_URL"
  exit 0
done

if [ -z "$green" ]; then
  log "timed out after ${CI_TIMEOUT}s waiting for checks — leaving PR open: $PR_URL"
  exit 0
fi

# Green. Merge, retrying briefly while GitHub settles the merge-state status.
for _ in 1 2 3 4 5; do
  if gh pr merge "$BR" --repo "$GH_REPO" --squash --delete-branch >/dev/null 2>&1; then
    log "merged $BR after green build."
    exit 0
  fi
  sleep 10
done
log "build green but merge did not succeed after retries — left open: $PR_URL"
