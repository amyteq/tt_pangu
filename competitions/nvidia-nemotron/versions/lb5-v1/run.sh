#!/usr/bin/env bash
# lb5-v1 reproducible pipeline (CPU-only steps; GPU 3-phase soup training is a
# separate handoff — see README + train_phases.py). Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/6] equation-numeric re-probe (plan checklist #1, shared; needs train.csv) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping (marked unavailable)."
  echo "  download: kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>"
fi

echo; echo "== [2/6] LB5 2-world/4-family/13-rule equation solver =="
python3 equation_solver.py --n 300

echo; echo "== [3/6] LB5 ternary byte-level bit solver (raw bits, 7-example cut) =="
python3 bit_ternary_solver.py --n 300 | head -6

echo; echo "== [4/6] HEX-vs-raw-bits tokenizer probe (LB5 negative lesson) =="
python3 tokenizer_probe.py

echo; echo "== [5/6] no-leakage statistics-matched generator =="
python3 generator.py --n 200

echo; echo "== [6/6] private-tracking (no-leakage) validation self-check + adapter preflight =="
python3 validate.py --self

echo; echo "== done. GPU 3-phase soup training + guarded submit are handed off (README). =="
