#!/usr/bin/env bash
set -euo pipefail

# Example launcher for M1 tasks. Copy commands one-by-one rather than running this blindly.
# Keep one active implementation branch at a time unless you are sure tasks do not overlap.

repo_dir="${1:-$HOME/work/kaggle-code-agent}"
cd "$repo_dir"

git status --short
git fetch origin
git checkout main
git pull --rebase

cat <<'MSG'
Ready. Recommended next command:

  git checkout -b claude/arch/M1-T000-legacy-tool-inventory
  claude --bg --name "M1-T000-legacy-tool-inventory" --permission-mode auto --model opus --effort high \
    "/goal Execute docs/tasks/M1-T000-legacy-tool-inventory.md until acceptance criteria pass, or stop after 40 turns and summarize blockers. Do not implement tools/kca yet. Do not run real Kaggle commands. Do not read or print secrets."

Monitor with:

  claude agents

MSG
