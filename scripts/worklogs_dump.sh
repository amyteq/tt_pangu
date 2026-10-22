#!/usr/bin/env bash
# Retained as a harmless target for already-installed systemd timers.
# Session exports must never be committed, pushed, or auto-merged: token masking
# cannot remove all credentials, personal data, or private conversation context.
# For an intentional local export, run scripts/exp_cc.py manually; its default
# destination is the ignored .agent/worklogs directory and its secret check stays on.
set -euo pipefail
printf '%s\n' 'Automatic transcript publication is retired. Disable worklogs-dump.timer on every host.'
