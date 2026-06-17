# Orbit Wars — model training log

Append-only ledger of model runs (OW-P1-MODEL-TRAIN-001 / prompt 05). One row per run.
Artifacts live under the gitignored `models/artifacts/<run_id>/`; metrics are copied here + into
the per-run model card so the numbers survive without the checkpoints.

| run_id | date | model | data | n_train / n_valid | headline metric | export | card |
|---|---|---|---|---|---|---|---|
| `20260617-cs-local20` | 2026-06-17 | candidate scorer (MLP 24→128→64→1, BCE) | local self-play ×20 eps (16×2p+4×4p), stride 2 | 102450 / 41828 | valid AUC **0.922** (2p 0.936 / 4p 0.903); recall@1/3/5 = 0.28/0.50/0.63 | `scorer.npz` (97KB, numpy fwd self-check err 0.0) | [model_card_20260617-cs-local20.md](model_card_20260617-cs-local20.md) |
| `20260617-vm-local20` | 2026-06-17 | value model (MLP 24→128→64→1, MSE on h50 Δscore) | local self-play ×20 eps, stride 2 | 92725 / 38941 | valid Pearson **r=0.683** (Δscore_h50) | — (not promising enough to export) | (same card) |

## Notes per run

### `20260617-cs-local20` + `20260617-vm-local20` (first cycle — plumbing proof-of-life)

- **Data is LOCAL self/cross-play, not ladder teachers.** No ladder replays were cached, so
  `datasets/gen_local_episodes.py` generated 20 episodes among the strongest locally available
  agents (kuni05 ~1240, evogen ~1093, v4, v3.2, pub_tactical) across seeds 7000–7003, 2p + 4p.
  `teacher_selected` therefore means "this local agent launched it", **not** "a ladder player
  launched it". The full ladder-teacher corpus is the snorlax path (datasets/README.md).
- End-to-end pipeline exercised: gen → episode index → candidate dataset (FlightOracle labels) →
  featurize → train (scorer + value) → export npz → pure-numpy offline eval (matches torch exactly).
- Headline offline metrics are **healthy but must not be read as strength** — see the model card's
  distribution-shift section (T12 BC: recall 0.387 / arena 0%). Promotion is gated on an arena A/B
  (VALIDATION.md #3), which this cycle did not run (no integration yet).
- Runtime: candidate dataset build 200s (CPU); each train run ~16s (CPU, torch 2.12.0+cpu).
