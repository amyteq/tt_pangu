#!/usr/bin/env bash
# lb3-v1 reproducible pipeline (CPU-only steps; GPU two-stage training is a separate
# handoff — see README "Training" + kernels/nemo-lb3-v1.py). Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/6] mul-pattern lookup (CSP cryptarithm seed table) =="
python3 mul_pattern_lookup.py

echo; echo "== [2/6] equation-numeric re-probe (plan checklist #1; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (marked unavailable)."
  echo "  download: kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>"
fi

echo; echo "== [3/6] CSP cryptarithm mechanism validation (headline lever) =="
python3 cryptarithm_csp.py --n 150

echo; echo "== [4/6] bit HEX-compression + solver + numeric 13-op solver =="
python3 bit_hex_trace.py --n 300
python3 numeric_solver.py --n 300

echo; echo "== [5/6] stage-1 memorize-drill corpus (two-stage stage 1) =="
python3 drill_gen.py --n 100

echo; echo "== [6/6] private-tracking validation self-check + adapter preflight =="
python3 validate.py --self

echo; echo "== done. GPU two-stage training + guarded submit are handed off (README). =="
