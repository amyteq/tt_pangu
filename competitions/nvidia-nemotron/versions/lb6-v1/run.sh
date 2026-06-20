#!/usr/bin/env bash
# lb6-v1 reproducible pipeline (CPU-only steps; GPU Unsloth SFT is a separate
# handoff — see README + train_lb6.py). Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/6] equation-numeric re-probe (plan checklist #1, shared; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (marked unavailable)."
fi

echo; echo "== [2/6] LB6 equation solver (add/sub/mul + maxmodmin families) =="
python3 equation_solver.py --n 300

echo; echo "== [3/6] LB6 template bit solver (shl/shr/rotr x pairwise/ternary, hex cheatsheet) =="
python3 bit_template_solver.py --n 200 | head -5

echo; echo "== [4/6] LB6 DFS cryptarithm solver (reversed search + pruning) =="
python3 cryptarithm_dfs.py --n 120

echo; echo "== [5/6] DUMMY-masking per-domain attribution probe + bit/cryptarithm trade-off CV =="
python3 dummy_probe.py --n 120
python3 tradeoff_cv.py

echo; echo "== [6/6] validation self-check (full-train-as-val + DUMMY probe + preflight) =="
python3 validate.py --self

echo; echo "== done. GPU Unsloth SFT + guarded submit are handed off (README). =="
