#!/usr/bin/env bash
# lb10-v1 reproducible pipeline (CPU-only steps; GPU SFT is a separate handoff —
# see README + train_lb10.py). Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/5] equation-numeric re-probe (plan checklist #1, shared; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (marked unavailable)."
fi

echo; echo "== [2/5] LB10 rotate/shift key-table bit reasoner (oracle lift) =="
python3 bit_keytable_reasoner.py --n 200

echo; echo "== [3/5] LB10 equation solver (frequency-deduce + two-axis guess) =="
python3 equation_solver.py --n 300

echo; echo "== [4/5] oracle-vs-fidelity + logprob learnability diagnostics =="
python3 learnability.py --self

echo; echo "== [5/5] validation self-check (keep-failures + oracle ceiling + preflight) =="
python3 validate.py --self

echo; echo "== done. GPU SFT (alpha/r=4, 2 epochs) + guarded submit are handed off (README). =="
