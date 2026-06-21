#!/usr/bin/env bash
# lb25-v1 reproducible pipeline (CPU-only). The LB25 method was already realized as
# v16-evalfix (0.832/0.828); the GPU run is a documented, optional handoff (README).
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/5] eval/submission parity audit (LB25 lever #1, the headline fix) =="
python3 eval_parity.py

echo; echo "== [2/5] equation reversal symmetry (LB25 lever #2; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reversal.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (download: kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>)"
fi

echo; echo "== [3/5] reorganized, verified bit CoT (LB25 lever #5) =="
python3 bit_cot.py

echo; echo "== [4/5] easy-category + cipher-prefix synth (LB25 levers #3/#4; no-regression guard) =="
python3 easy_cat_synth.py --n 150 --report

echo; echo "== [5/5] preflight self-check (extraction + fail-fast) =="
python3 validate.py --self || true

echo; echo "== done. The LB25 method's LB result already exists (v16-evalfix 0.832/0.828); see README 'Submit gate'. =="
