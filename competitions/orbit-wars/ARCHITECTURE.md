# Orbit Wars — agent architecture (hybrid design)

> The competition agent is a **hybrid**: the deterministic **v3.2 "Forecast"** planner with an
> *optional* trained candidate-scorer layered on top. One principle governs the whole stack:
>
> **The model only scores/ranks already-legal candidates — it never emits a launch angle or a ship
> count. The deterministic FlightOracle + RuleEngine + ActionSanitizer are always the final authority,
> and if the model (or `core/`) fails to load, the agent degrades to pure rules (v3.2).**
>
> Deployed entrypoint: `agent/main.py`. Hybrid toggle: `OW_HYBRID` (default **0** — see *Current
> status*). The submission is `main.py` + `core/` (+ `hybrid_model.py` + `hybrid_weights.json` when the
> model is enabled), packaged as a tar.gz; it stays **stdlib-only at runtime** (no numpy/torch online).

## Data flow

```
obs  (raw kaggle_environments observation: planets / fleets / initial_planets / angular_velocity / step)
 │
 │  [0] geometry primitives      core/geometry.py            engine-exact physics — underpins every layer
 ▼
 [1] state perception            core/state.py               obs -> typed BattlefieldState
 ▼
 [2] projection / ledger         core/ledger.py + project()  do-nothing forecast; arrival & threat windows
 ▼
 [3] candidate generation        agent/main.py (v3.2)        intercept-solved legal launches, value-sim ranked
 ▼
 [4] features                    core/features.py            candidate -> 24-dim feature_vector (one contract)
 ▼
 [5] model scorer   (optional)   agent/hybrid_model.py       pure-Python MLP; rank-blends into commit order
 ▼
 [6] rule engine                 core/rule_engine.py         ECA guardrails + tactical re-weighting
 ▼
 [7] oracle + sanitizer          core/oracle.py + core/action_sanitizer.py   first-hit/path validate; final emission gate
 ▼
actions  [[src, angle, ships], ...]
```

## Layers

| # | Layer | Module(s) | Function | Authority |
|---|---|---|---|---|
| 0 | **Physics primitives** | `core/geometry.py` | Engine-exact geometry/physics: `fleet_speed`, `planet_pos`, swept collision, `solve_intercept`, `project` — frame-aligned to the orbit_wars interpreter. **The B11 planet-rotation phase fix lives here** (`ang_vel*max(0, step-1)`); every prediction, intercept and safety check builds on it. | deterministic (foundation) |
| 1 | **State perception** | `core/state.py` (`build_battlefield_state`) | Parse raw obs into a typed `BattlefieldState`: per-planet owner / production / 1–100 strategic value / ROI / holdability / frontier & hub flags; per-player and global (phase, remaining steps). | deterministic |
| 2 | **Projection / ledger** | `core/ledger.py` (`ArrivalLedger`, `ThreatLedger`) + `project()` | "Do-nothing" forward simulation: each planet's owner/ship trajectory over a horizon, fleet arrival turns, and incoming-threat windows. Drives value estimation and defensive reserves. | deterministic |
| 3 | **Candidate generation** | `agent/main.py` (v3.2 Forecast) | For each *my-planet → non-mine target*, solve a fixed-point intercept (angle, ships, ETA), size to capture-and-hold, and score by terminal differential value under budget/defense constraints. Emits legal candidates `(value, src, tgt, angle, ships)`. | deterministic |
| 4 | **Features** | `core/features.py` (`candidate_features` → `feature_vector`) | Encode each candidate as a fixed **24-dim** vector (source/target strategic quantities + FlightOracle path quantities). This is the **single train/serve feature contract** — the offline trainer and the online scorer import the same `feature_vector` (verified bit-identical). | deterministic |
| 5 | **Model scorer** *(optional)* | `agent/hybrid_model.py` + `agent/hybrid_weights.json` | Pure-Python MLP (stdlib only; no numpy/torch online) that scores candidates and **rank-blends** into the v3.2 greedy commit order (`OW_HYBRID_BETA`, default 0.5; `β=0` is byte-identical to v3.2). Only re-orders — never changes ships, angle, or safety. Fail-safe: missing/bad weights → rules-only. | model (advisory) |
| 6 | **Rule engine** | `core/rule_engine.py` | ECA-style guardrails + tactical re-weighting (over-extension caps, safety constraints): hard-filters / down- or up-weights candidates. A guardrail, **not** a strategy. | deterministic |
| 7 | **Oracle + sanitizer** | `core/oracle.py` (FlightOracle) + `core/action_sanitizer.py` | FlightOracle does deterministic first-hit / path classification (target / friendly / sun / oob; strict-sun vs near-sun). ActionSanitizer is the **final emission gate** — every action passes through it; provably-fatal sun/oob launches are dropped. | deterministic (final) |

## Design principles

- **Model ranks, rules execute.** The model can only re-order legal candidates the deterministic stack
  already generated, sized, path-checked and (will) emit-gate. It cannot pick an unsafe move.
- **Deterministic last word.** RuleEngine + FlightOracle + ActionSanitizer are the final authority,
  regardless of the model.
- **Fail-safe by construction.** `OW_HYBRID=0` or any model/`core` import or inference failure →
  byte-identical pure v3.2. The hybrid is *strictly additive* — never worse than v3.2 by design.
- **One feature contract.** Offline training and online scoring share `core.features.feature_vector`,
  so there is no train/serve skew.
- **Engine-exact substrate, anti-BC.** `core/geometry.py` is verified against the real engine; the model
  scores *components* a deterministic engine consumes (candidate ranking / value), **not** a direct
  policy clone — behavior cloning was refuted (high offline recall, 0% arena; see `bugs.md` B7).

## Current status (2026-06-18)

The hybrid **infrastructure is complete and fallback-safe, but the model scorer (layer 5) is OFF by
default** (`OW_HYBRID=0`):

- The arena A/B (prompt 06) showed the model re-ranker gave **no strong-tier gain** (vs evogen
  13.8% → 13.8–14.6%, flat), and that model was trained on features from a *buggy* oracle.
- The real breakthrough came from **layer 0**: the **B11 planet-rotation off-by-one fix** lifted the
  pure-deterministic `fixed-v3.2` from **13.8% → 45%** vs evogen (and 0% sun-bound launches, down from
  ~9%). See `bugs.md` B11 / `insights.md` INS-009.

So the **currently deployed / strongest agent is the pure-deterministic v3.2-rotfix** (model layer
inert; submissions 53769740 / 53769744). Layer 5 is retained as an additive, reversible "future-gain
slot": it should be re-trained on **fixed-simulation** features (the strong-tier teacher corpus
`datasets/strong_corpus/` is ready) and re-evaluated by arena A/B before being switched on.

## File map

```
agent/main.py                 layers 2–3 + 7 wiring; _hybrid_rerank (5), _emit_gate (7); OW_HYBRID/OW_HYBRID_BETA
agent/versions/hybrid_v0.py   = main.py with OW_HYBRID=1 (named A/B opponent)
agent/hybrid_model.py         layer 5 scorer (pure-Python MLP loader + forward)
agent/hybrid_weights.json     exported scorer weights (features + mean/std + per-layer W/b)
core/geometry.py              layer 0
core/state.py                 layer 1
core/ledger.py                layer 2
core/features.py              layer 4 (feature_vector = train/serve contract)
core/rule_engine.py           layer 6
core/oracle.py                layer 7 (FlightOracle)
core/action_sanitizer.py      layer 7 (final emission gate)
models/                       offline training/export for layer 5 (train_candidate_scorer, export_npz, …)
```

Provenance: prompts 02/03 (core substrate + FlightOracle gate), 04 (dataset/features), 05 (model
training), 06 (hybrid integration); B11 fix + arena results in `tracking.md` / `bugs.md` / `insights.md`.
