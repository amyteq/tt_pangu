#!/usr/bin/env bash
# lb1-v1 reproducible pipeline (CPU-only steps; GPU training is a separate handoff).
# Usage: bash run.sh   (run from this directory)
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/5] signature catalog (expect 4205) =="
python3 signature_catalog.py

echo; echo "== [2/5] equation-numeric re-probe (needs train.csv; skipped if absent) =="
TRAIN="${NEMO_TRAIN_CSV:-$HOME/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv}"
if [ -f "$TRAIN" ]; then
  python3 eq_reprobe.py --train "$TRAIN"
else
  echo "  train.csv not found at $TRAIN — skipping re-probe."
  echo "  download: kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>"
fi

echo; echo "== [3/5] bit rule-sequence catalog (count overshoots ~5238; see README) =="
python3 - <<'PY'
import rule_sequence_catalog as R
core = R.build_core_catalog()
print(f"core repair catalog: {len(core)} sequences (tractable subset for repair NN)")
PY

echo; echo "== [4/5] synthetic corpus sample + token histogram (gate: bit median < 5000) =="
python3 synth_gen.py --n 600 --report

echo; echo "== [5/5] preflight self-check (extraction + fail-fast) =="
python3 validate.py --self

echo; echo "== done. GPU training + guarded submit are handed off (see README 'Submit gate'). =="
