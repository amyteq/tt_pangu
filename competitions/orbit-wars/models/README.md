# Orbit Wars — models/

Model-training layer for the hybrid agent (OW-P1-MODEL-TRAIN-001 / prompt 05). The model **ranks
legal candidates and estimates value**; it never owns the continuous angle or the final emission —
`core/oracle.py` (FlightOracle) + `core/rule_engine.py` + `core/action_sanitizer.py` stay the
deterministic authority (see `../core/`, VALIDATION.md gate #7). This directory trains those heads
offline, exports them to a numpy `.npz`, and evaluates imitation fidelity — it does **not** touch
the ladder or Kaggle.

## Why not behavior cloning

A direct policy clone is explicitly out of scope (B7, `insights.md`): the T12 BC student reached
recall@k 0.387 yet scored **0% in the arena** — classic distribution shift (the student never sees
its own induced states). So we model *components* a deterministic engine consumes, not a policy:

- **candidate scorer** (`train_candidate_scorer.py`) — `P(teacher launches this candidate)`, an
  imitation *ranking* signal over engine-legal candidates. Still an imitation target, but it only
  re-orders a FlightOracle-validated candidate set; the rule engine can override.
- **value model** (`train_value_model.py`) — regresses the *realized* future score delta
  (`future_value_delta_h50`), an **outcome** label that needs no policy imitation, so it is robust
  to the BC trap. Used to break ties / prefer high-value launches.

Neither is wired into `agent/main.py` yet — integration is prompt 06 (OW-P1-HYBRID-INTEGRATE), gated
on an arena A/B (VALIDATION.md gate #3), not on offline metrics.

## Files

| File | Role |
|---|---|
| `_featurize.py` | shared candidate→fixed numeric vector (`FEATURES` = the model input contract) |
| `train_candidate_scorer.py` | MLP `N→128→64→1`, BCE on `teacher_selected`, episode-split, AUC + recall@k |
| `train_value_model.py` | MLP regressor on `future_value_delta_h{20,50}`, episode-split, MSE + Pearson r |
| `export_npz.py` | `model.pt` → `scorer.npz` (numpy-only forward, self-checked vs torch) for the ladder runtime |
| `evaluate_offline.py` | pure-numpy eval of `scorer.npz` vs a dataset (recall@k + AUC + 2p/4p) |
| `reports/model_card_<run_id>.md` | per-run card (data / features / metrics / caveats) |
| `reports/training_log.md` | append-only run ledger |
| `artifacts/<run_id>/` | **gitignored** — `model.pt`, `meta.json`, `scorer.npz` |

## Runtime contract

The ladder agent stays **stdlib + numpy** (no torch import on Kaggle). It loads `scorer.npz`
(weights + standardization `mean`/`std` + `FEATURES` order) and runs `export_npz.forward()` — the
reference pure-numpy MLP. `export_npz.py` self-checks that the numpy forward reproduces torch within
`1e-5`, so the deployed scores match training.

## Local first cycle (small, CPU)

Proof-of-life on a handful of our own episodes (env: `~/.venvs/orbit-wars`, torch 2.12.0+cpu):

```bash
source ~/.venvs/orbit-wars/bin/activate
cd competitions/orbit-wars
# 1. fetch a few of OUR episodes read-only (no Kaggle write):
python ops/episode_discover.py --submission-id <id> --limit 12 > /tmp/eps.json
python ops/episode_fetch.py --from /tmp/eps.json --out datasets/cache/replays
# 2. build candidate dataset (FlightOracle labels):
python datasets/build_episode_index.py --replay-root datasets/cache/replays --out-root datasets/artifacts/local
python datasets/build_candidate_dataset.py --replay-root datasets/cache/replays --out-root datasets/artifacts/local --step-stride 10
# 3. train + export + eval:
python models/train_candidate_scorer.py --data-root datasets/artifacts/local --out-root models/artifacts/<run_id>
python models/export_npz.py --run-root models/artifacts/<run_id>
python models/evaluate_offline.py --npz models/artifacts/<run_id>/scorer.npz --data-root datasets/artifacts/local
```

Small-data runs are a **plumbing proof, not a strength claim** — read the run's model card.

## Full corpus (snorlax / RTX-4090)

The 20G replay corpus does not belong on this box or in git. On snorlax
(`docs/tooling/remote-compute-snorlax.md`, `OMP_NUM_THREADS=1` per B8): build the candidate dataset
over the full `--replay-root`, then the same `train_*` / `export_npz` / `evaluate_offline` commands.
GPU is optional — the MLP is tiny; CPU is fine. Copy back only `scorer.npz` + `meta.json` +
the model card (never `model.pt` checkpoints or replays).
