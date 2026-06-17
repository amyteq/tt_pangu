# Orbit model card: 20260617-cs-ladder310 (real ladder corpus → hybrid_v0)

> The candidate scorer deployed in `agent/hybrid_weights.json` and wired into the hybrid re-ranker
> (prompt 06). Trained on REAL ladder replays. **Verdict: offline AUC 0.88, but the arena A/B shows
> it does NOT improve strong-tier results — NOT promotable. Use = reject/retrain.** This is the third
> confirmation of the BC/imitation lesson: offline fidelity ≠ ladder strength.

## Purpose

- candidate scorer — `P(a real ladder player launches this candidate)`. Re-orders the v3.2 candidate
  list before the greedy commit (`agent/main.py` `_hybrid_rerank`). Never emits angles/ship counts;
  FlightOracle + RuleEngine + ActionSanitizer stay final authority.

## Training data

- replay corpus: **REAL Kaggle ladder replays** — 310 episodes fetched read-only from the public
  episode store (`ops/episode_discover.py` + `ops/episode_fetch.py`) for our submissions 53582503
  (kuni05-adapted, μ→1103) and 53730511 (v4, μ→843). 1.3 GB raw JSON (gitignored).
- date range: episodes played through 2026-06-17; fetched 2026-06-17.
- number of episodes: 310 (156 2p + 154 4p; 63k steps).
- 2p/4p split: balanced (156/154 episodes).
- top-player filter: none available — these are OUR submissions' matches, so opponents are
  similar-skill (matchmaking is similar-skill from game 1, INS-005). `seat_is_winner` is recorded; a
  `--winners-only` variant (imitate the winning seat) was trained and tied (see Metrics).
- train/valid split: episode-split 80/20 (1.96M train / 0.52M valid candidates); no step/episode
  leakage. FlightOracle labels are deterministic from board state.
- leakage prevention: split by `episode_id`; built with `build_candidate_dataset.py --shard i/8`
  (parallel) at stride 3.

## Features

24 features, shared `core.features.feature_vector` (the SINGLE source of truth — offline trainer and
online scorer import the same function; verified bit-identical on 5000 rows). Planet-pair (strategic
value / roi / holdability / pressure / frontier / centrality / comet / reinforcement / threat-window
/ owner flags), FlightOracle path (valid / eta / min-sun / near-sun / first-hit-is-target), global
(remaining_steps / phase / src ships+slack+hub+bank / ships / ship_bucket). No short-history; no
explicit 4p one-hot (owner flags + per-seat state only).

## Labels

- imitation: `teacher_selected` — a real ladder player launched this (FlightOracle-decoded src→first-hit
  target). Positive rate 0.19% (4786 / 2.48M; 4526 decision points).
- value: `future_value_delta_h50` recorded (value model not retrained this cycle).
- safety: FlightOracle `oracle_valid / first_hit_type / min_sun` per row (features, not dropped).
- outcome: `terminal_outcome` + `seat_is_winner` recorded.

## Model

- architecture: MLP `24 → 128 → 64 → 1` (ReLU), sigmoid. ~12k params.
- framework: PyTorch 2.12.0+cpu (training only, ~30 s on HARRY-ARCH CPU; no GPU/snorlax needed).
- export: `scorer.npz` (numpy, offline eval) + `scorer.json` (252 KB, pure-Python) → deployed as
  `agent/hybrid_weights.json`. Both self-checked vs torch: `max_err = 0.0`.
- online runtime: `agent/hybrid_model.py` — stdlib + `core` only (no numpy/torch on the ladder).
  Pure-Python forward matches numpy to 3e-16. p99 **44 ms/turn** in-agent (p50 9 ms) — under the 50 ms
  local target and 20× under Kaggle's 1000 ms. Re-ranker scores only the top-80 candidates/turn.

## Metrics

Offline (held-out episodes), all-teacher run `20260617-cs-ladder310`:

- valid AUC **0.882** (2p 0.875 / 4p 0.886; winner-seat 0.887 / loser-seat 0.878).
- recall@k vs teacher: @1 0.237, @3 0.481, @5 0.592 (4526 decision points).
- pure-numpy eval over full corpus (deployed path): AUC 0.885 — matches torch.
- winners-only variant `…-win`: AUC 0.888 — statistically tied; all-teacher deployed (more data).

**Arena A/B (the real test — `agent/main.py` OW_HYBRID re-ranker vs frozen v3.2; 240 games/cell):**

| matchup | control (v3.2) | hybrid β0.25 | hybrid β0.5 | read |
|---|---|---|---|---|
| vs **evogen1093** (μ1093) | 13.8% | 14.6% (+0.8) | 13.8% (+0.0) | **flat — cliff intact** |
| vs **kuni05** (μ1240) | 0.8% | — | 0.8% (+0.0) | crushed (avg 17 vs 2315) |
| vs v3.2 (near-mirror) | 33% (80T) | 46% / 111W-113L | 46% / 111W-129L | tie-conversion, net ≈even/behind |
| vs pub_tactical (weak) | 97.9% | — | 97.9% (+0.0) | **non-regression ✓** |
| 4p FFA (avg_rank) | 1.77/4 | — | 1.77/4 | identical, non-regression ✓ |

- safety false-negative rate: n/a (scorer doesn't gate safety; FlightOracle does). Crash-safety: 0
  crashes / 8 games / 3650 steps.
- The +7pt strong-tier gate (VALIDATION #3) is **NOT met** (flat vs evogen, crushed by kuni05).

## Integration

- agent version: `agent/versions/hybrid_v0.py` = `main.py` with `OW_HYBRID=1`. Re-ranker in
  `_hybrid_rerank` blends model rank into the v3.2 commit order (rank blend, `OW_HYBRID_BETA`).
- fallback: `OW_HYBRID=0` or any load/inference failure → plain v3.2 order. **β=0 is byte-identical
  to v3.2** (verified on a 499-turn obs replay) — strictly additive, never worse by construction.
- rule-engine / FlightOracle: unchanged; the model only reorders already-legal, already-sized,
  already-path-checked candidates. Emission still passes `core.action_sanitizer`.

## Risks

- **distribution shift / teacher ceiling (PRIMARY, CONFIRMED).** The imitation teacher is similar-skill
  ladder play (μ~1077), not strong-tier. AUC 0.88 offline did NOT translate to strong-tier wins — the
  third confirmation (after T12 BC 0% and the local-data run) that offline fidelity ≠ ladder strength.
- the strong-tier gap is **strategic**, not a candidate-ranking problem: a re-ranker over v3.2's own
  candidates cannot add strategy v3.2 doesn't generate (consistent with B6 — 13 single levers refuted).
- 2p/4p: 4p AUC ok offline but the re-ranker was inert in the 4p arena sample.

## Decision

**reject / retrain.** Do NOT promote `hybrid_v0` to the ladder. Keep the integration (safe, inert at
β=0, non-regressive) as the substrate for a better model. To have a chance at the cliff the corpus
needs **genuine strong-tier teachers** (μ>1240 players' episodes — e.g. multifocus / real kuni05
submission ids), and likely a target beyond imitation (value/outcome distillation, or a search-based
policy). Next run: discover top-player submission ids → fetch their episodes → retrain winner-seat /
top-player-only → re-run this same A/B. No Kaggle submit performed.
