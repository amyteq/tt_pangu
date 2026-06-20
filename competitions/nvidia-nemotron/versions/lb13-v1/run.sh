#!/usr/bin/env bash
# lb13-v1 reproducible pipeline (CPU-only steps; GPU 3-stage SFT is a separate
# handoff — see README + train_3stage.py). Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/5] equation-numeric re-probe (plan checklist #1, shared; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (marked unavailable)."
  echo "  download: kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>"
fi

echo; echo "== [2/5] LB13 equation solver (exclusivity + global majority-vote reversal + robust agg) =="
python3 equation_solver.py --n 300

echo; echo "== [3/5] LB13 3-input bit verifier (MAJ/XNOR3 + bit-position search + left-edge fallback) =="
python3 bit_3input_verify.py --n 300

echo; echo "== [4/5] keep-failures 1:1 rebalance + robust aggregation + cryptarithm-from-equation =="
python3 rebalance.py

echo; echo "== [5/5] validation self-check (teacher oracle + robust>strict + rebalance + preflight) =="
python3 validate.py --self

echo; echo "== done. GPU 3-stage SFT + guarded submit are handed off (README). =="
