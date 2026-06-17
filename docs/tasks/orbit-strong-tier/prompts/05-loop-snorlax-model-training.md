---
id: OW-P1-MODEL-TRAIN-001
title: Snorlax model-training loop for Orbit Wars candidate scorer/value model
kind: claude-code-loop
status: ready
scope: model-training-and-reports
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: none
preferred_host: snorlax
hardware_notes: RTX 4090 GPU for PyTorch training; arena is CPU-bound
allowed_paths:
  - competitions/orbit-wars/**
  - docs/tasks/competition-tracking/orbit-strong-tier/**
forbidden_paths:
  - .kca/**
  - tools/**
  - src/**
  - services/**
  - supabase/**
  - ui/**
  - tests/**
  - .github/workflows/**
  - .env
  - .env.*
  - kaggle.json
  - .kaggle/kaggle.json
  - secrets/**
---

# Loop: Snorlax model training for Orbit Wars hybrid policy

## Mission

Use snorlax to train models that improve candidate ranking/value estimation for Orbit Wars. This loop may run in parallel with live ladder episode analysis, but it must not perform Kaggle submit/push.

Target model role:

```text
model scores/ranks legal candidates or estimates value/posture
model does not directly emit continuous angles
FlightOracle + RuleEngine remain final authority
```

## Read first

- `competitions/orbit-wars/datasets/README.md`
- `competitions/orbit-wars/datasets/schema.md`
- `competitions/orbit-wars/datasets/reports/dataset_quality.md`
- `competitions/orbit-wars/core/features.py` if present
- `competitions/orbit-wars/arena/distill_train.py`
- `competitions/orbit-wars/agent/versions/student.py`
- `docs/tasks/competition-tracking/orbit-strong-tier/templates/model_card_template.md`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/promotion_gate.yaml`

## Training priorities

### Model v0 — candidate scorer

Input:

```text
candidate features + BattlefieldState summaries + ArrivalLedger features + short history + 2p/4p context
```

Output:

```text
candidate score
optional ship_bucket / ship_fraction adjustment
posture hint
```

Architecture:

```text
MLP 128 -> 64 -> heads
```

Export:

```text
npz/json weights usable by pure Python runtime
```

### Model v1 — value model

Input:

```text
state + candidate/action-set features
```

Output:

```text
future Δvalue / placement or win probability / collapse risk
```

## Files to create/update

```text
competitions/orbit-wars/models/README.md
competitions/orbit-wars/models/train_candidate_scorer.py
competitions/orbit-wars/models/train_value_model.py
competitions/orbit-wars/models/export_npz.py
competitions/orbit-wars/models/evaluate_offline.py
competitions/orbit-wars/models/reports/model_card_<run_id>.md
competitions/orbit-wars/models/reports/training_log.md
```

Generated artifacts should go under a gitignored path such as:

```text
competitions/orbit-wars/models/artifacts/<run_id>/
```

Do not commit large model checkpoints unless they are tiny exported runtime weights and intentionally versioned.

## Loop behavior

Each cycle:

1. Check dataset quality and freshness.
2. Train or resume one model run.
3. Evaluate on held-out episodes.
4. Export a small runtime artifact if promising.
5. Generate/update a model card.
6. If model is promising, create a follow-up task for hybrid integration.
7. Stop the cycle; do not submit to Kaggle.

## Dataset freshness

If live-loop has downloaded new episodes:

- include them in a separate `live_eval` split, not training immediately;
- use them to test distribution shift;
- do not leak first 10/20 episode outcomes into training for the same submitted version.

## Metrics

Report:

- candidate ranking AUC / MAP / NDCG if implemented;
- recall@k against teacher actions;
- value model error / AUC if implemented;
- safety false-negative rate;
- 2p vs 4p split metrics;
- top-player vs non-top-player split metrics;
- calibration by phase;
- runtime cost of exported model.

Recall@k alone is not enough. The previous BC student had high recall but 0% arena, so every model card must explicitly assess distribution-shift risk.

## Export requirements

Exported model must support:

```text
pure Python or minimal runtime
no torch dependency in ladder agent unless explicitly runtime-smoked
fallback to rules-only if weights fail to load
p99 inference time documented
```

## Validation commands

Run as appropriate:

```bash
python -m py_compile competitions/orbit-wars/models/*.py
python competitions/orbit-wars/models/train_candidate_scorer.py --help
python competitions/orbit-wars/models/evaluate_offline.py --help
python competitions/orbit-wars/models/export_npz.py --help
```

If dataset exists:

```bash
python competitions/orbit-wars/models/train_candidate_scorer.py \
  --data-root <dataset_artifact_root> \
  --out-root competitions/orbit-wars/models/artifacts/<run_id> \
  --max-epochs <bounded>
```

## Acceptance criteria per cycle

- At least one model run is trained or a precise data blocker is documented.
- A model card is created/updated.
- Offline metrics are reported with 2p/4p split.
- Export is produced only if promising.
- Follow-up task is created for hybrid integration if the model is promising.
- No Kaggle submit/push is performed.
- No secrets are read.

## Stop conditions

Stop if:

- dataset is missing or quality is too poor;
- FlightOracle labels are unavailable and model would learn unsafe labels;
- model overfits or fails validation;
- running would exceed reasonable snorlax budget;
- changes would touch forbidden paths.

## Final response requirements

Report:

- data used;
- model architecture;
- metrics;
- export path;
- model card path;
- recommended integration decision;
- blockers and next run suggestions.
