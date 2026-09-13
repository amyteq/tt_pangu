# Orbit Wars — agent architecture (layered hybrid design)

> The competition agent is a **hybrid**: the deterministic **v3.2 "Forecast"** planner with an
> *optional* trained candidate-scorer and an *optional* rule-engine layered on top. One principle
> governs the whole stack:
>
> **The model only scores/ranks already-legal candidates — it never emits a launch angle or a ship
> count. The deterministic FlightOracle + RuleEngine + ActionSanitizer are always the final authority,
> and if the model (or `core/`) fails to load, the agent degrades to pure rules (v3.2).**
>
> Deployed entrypoint: `agent/main.py` (a **thin** shim since OW-ARCH-001). The layered policy lives in
> `core/policy.py`. Hybrid toggle: `OW_HYBRID` (default **0**). The submission is `main.py` + `core/`
> (+ `agent/config_baked.py`, and `hybrid_model.py` + `hybrid_weights.json` when the model is enabled),
> packaged as a tar.gz; it stays **stdlib-only at runtime** (no numpy/torch/PyYAML online).

## Data flow

```
obs  (raw kaggle_environments observation: planets / fleets / initial_planets / angular_velocity / step)
 │
 │  [cfg] config resolution      core/config.py             env OW_* -> baked profile -> inline literal
 │  [0]  geometry primitives     core/geometry.py           engine-exact physics — underpins every layer
 ▼
 [1] state perception            core/state.py              obs -> typed BattlefieldState (fleets decoded
 ▼                                                            from CURRENT position, not relaunched)
 [2] projection / ledger         core/ledger.py + project() do-nothing forecast; arrival & threat windows
 ▼
 [3] candidate generation        core/policy.py (v3.2)      intercept-solved legal launches, value-sim ranked
 ▼                                                            (typed form: core/candidates.py CandidateAction)
 [4] features                    core/features.py           candidate -> 25-dim feature_vector (one contract)
 ▼
 [6] rule engine    (pass-thru)  core/rule_engine.py        ECA guardrails + tactical re-weighting (OW_RULE_ENGINE)
 ▼
 [5] model scorer   (optional)   agent/hybrid_model.py      pure-Python MLP; rank-blends into commit order
 ▼
 [7] emit + sanitize             core/action_emitter.py  ->  core/action_sanitizer.py (+ core/oracle.py)
 ▼                                                            intended target IDs preserved to the last step
actions  [[src, angle, ships], ...]
```

(Layers [6] and [5] are advisory and **OFF by default**, so the live path is byte-identical to pure
v3.2 Forecast; the greedy budget selector sits between [4] and emission.)

> **Default-path scope (OW-ARCH-001).** With both advisory layers off, the v3.2 commit path computes
> moves from its own inline forward-sim and reads raw obs fleet positions directly (`_incoming_threat`);
> it does **not** consume `BattlefieldState`/`features`/`ledger`. So the layer-1 current-position fleet
> **decode fix** and the layer-4 **own/enemy/neutral** split are correct + unit-tested but only become
> *live in move selection* once `OW_RULE_ENGINE`/`OW_HYBRID` is enabled (they build `BattlefieldState`).
> This is exactly why the default path is byte-identical (golden 0-mismatch). Re-validate those layers
> end-to-end when first enabling [5]/[6]. The byte-identical baseline is the **post-B11** agent (the
> already-merged state this refactor started from), not the frozen pre-B11 `agent/versions/v3_2.py`.

## Layers

| # | Layer | Module(s) | Function | Authority |
|---|---|---|---|---|
| cfg | **Config** | `core/config.py` + `agent/config_baked.py` + `config/*.yaml` | One place resolves every `OW_*` knob: env override → baked profile → inline literal. YAML is the human source; the runtime reads the baked stdlib dict (no PyYAML online). | deterministic |
| 0 | **Physics primitives** | `core/geometry.py` | Engine-exact geometry/physics: `fleet_speed`, `planet_pos`, swept collision, `solve_intercept`, `project` — frame-aligned to the orbit_wars interpreter. **The B11 planet-rotation phase fix lives here** (`ang_vel*max(0, step-1)`); every prediction, intercept and safety check builds on it. `agent/utils.py` is a thin re-export wrapper over this module (no separate physics). | deterministic (foundation) |
| 1 | **State perception** | `core/state.py` (`build_battlefield_state`) | Parse raw obs into a typed `BattlefieldState`: per-planet owner / production / 1–100 strategic value / ROI / holdability / frontier & hub flags; per-player and global (phase, remaining steps). **In-flight fleets are decoded from their current `(x,y)` via `FlightOracle.decode_existing_fleet`, not relaunched from the source planet.** | deterministic |
| 2 | **Projection / ledger** | `core/ledger.py` (`ArrivalLedger`, `ThreatLedger`) + `project()` | "Do-nothing" forward simulation: each planet's owner/ship trajectory over a horizon, fleet arrival turns, and incoming-threat windows. Drives value estimation and defensive reserves. | deterministic |
| 3 | **Candidate generation** | `core/policy.py` (v3.2 Forecast) | For each *my-planet → non-mine target*, solve a fixed-point intercept (angle, ships, ETA), size to capture-and-hold, and score by terminal differential value under budget/defense constraints. Emits legal candidates `(value, src, tgt, angle, ships)`. `core/candidates.py` provides the typed `CandidateAction`. | deterministic |
| 4 | **Features** | `core/features.py` (`candidate_features` → `feature_vector`) | Encode each candidate as a fixed **25-dim** vector. Target ownership is split into **own / enemy / neutral** (`tgt_owner_is_own` added in OW-ARCH-001 — `owner != -1` is no longer treated as enemy). Single train/serve contract: the offline trainer and the online scorer import the same `feature_vector`. | deterministic |
| 5 | **Model scorer** *(optional)* | `agent/hybrid_model.py` + `agent/hybrid_weights.json` | Pure-Python MLP (stdlib only) that scores candidates and **rank-blends** into the greedy commit order (`OW_HYBRID_BETA`, default 0.5; `β=0` is byte-identical to v3.2). Only re-orders — never changes ships, angle, or safety. Fail-safe: missing / **stale-contract** / bad weights → `None` → rules-only. | model (advisory) |
| 6 | **Rule engine** | `core/rule_engine.py` (wired via `_rule_gate`) | ECA-style guardrails + tactical re-weighting: hard-blocks unsafe/invalid candidates and down/up-weights the rest, with human-readable reasons. **Pass-through by default** (`OW_RULE_ENGINE=0`); when enabled it filters/re-weights the candidate list before the commit. A guardrail, **not** a strategy. | deterministic |
| 7 | **Emit + sanitize** | `core/action_emitter.py` → `core/action_sanitizer.py` (+ `core/oracle.py` FlightOracle) | The selected candidates are emitted **with their intended target IDs preserved**; the sanitizer is the final gate — provably-fatal sun/oob launches are always dropped, and wrong-first-hit / landing-target mismatch is dropped when `OW_BLOCK_WRONG_HIT=1`. FlightOracle does deterministic first-hit / path classification (target / friendly / sun / oob; strict-sun vs near-sun) and supports both launch-from-source and trace-from-current-position. | deterministic (final) |

## Design principles

- **Model ranks, rules execute.** The model can only re-order legal candidates the deterministic stack
  already generated, sized, path-checked and emit-gated. It cannot pick an unsafe move.
- **Deterministic last word.** RuleEngine + FlightOracle + ActionSanitizer are the final authority,
  regardless of the model.
- **Fail-safe by construction.** `OW_HYBRID=0` / `OW_RULE_ENGINE=0` (defaults), or any model/`core`
  import or inference failure → byte-identical pure v3.2. Both optional layers are *strictly additive*.
- **One feature contract.** Offline training and online scoring share `core.features.feature_vector`,
  so there is no train/serve skew.
- **Engine-exact substrate, anti-BC.** `core/geometry.py` is verified against the real engine; the model
  scores *components* a deterministic engine consumes (candidate ranking / value), **not** a direct
  policy clone — behavior cloning was refuted (high offline recall, 0% arena; see `bugs.md` B7).
- **Stdlib-only runtime.** No numpy/torch/PyYAML online. Config is baked to a Python dict; the scorer is
  a hand-rolled MLP. `agent/main.py` must not touch `__file__` at load (kaggle execs it in an empty
  namespace) — it locates `core/` by scanning `sys.path` (see `bugs.md` B12).

## Current status (2026-06-18)

The hybrid **infrastructure is complete and fallback-safe; both optional layers (5 model, 6 rules) are
OFF by default**, so the deployed agent is the **pure-deterministic v3.2-rotfix**:

- The arena A/B (prompt 06) showed the model re-ranker gave **no strong-tier gain** (vs evogen
  13.8% → 13.8–14.6%, flat), and that model was trained on features from a *buggy* oracle.
- The real breakthrough came from **layer 0**: the **B11 planet-rotation off-by-one fix** lifted the
  pure-deterministic `fixed-v3.2` from **13.8% → 45%** vs evogen (0% sun-bound launches, down from ~9%).
  See `bugs.md` B11 / `insights.md` INS-009.
- OW-ARCH-001 grew the feature contract to **25 dims** (own/enemy/neutral split), so the deployed
  `hybrid_weights.json` (trained on 24) now **disables cleanly** (load → `None` → rules-only). Re-train
  on the **fixed-simulation** 25-feat contract (corpus `datasets/strong_corpus/` is ready) and re-A/B
  before enabling layer 5. See `tasks.md`.

## File map

```
agent/main.py                 thin entrypoint: locate core/ (no __file__) -> core.policy.get_default_policy().act(obs)
agent/utils.py                thin wrapper re-exporting core.geometry primitives (no separate physics)
agent/config_baked.py         baked default config profile (stdlib dict; the runtime config source)
agent/hybrid_model.py         layer 5 scorer (pure-Python MLP loader + forward; compat-guards the contract)
agent/hybrid_weights.json     exported scorer weights (currently 24-feat -> auto-disabled)
config/default.yaml           layer cfg: canonical knob schema (human reference)
config/profiles/current.yaml  layer cfg: the ACTIVE profile (baked into config_baked.py)
config/profiles/*.yaml        example profiles (hybrid_v0, ladder_probe); config/bake.py + bake --check
core/config.py                layer cfg: env OW_* resolution (geti/getf/getstr/getb/snapshot)
core/geometry.py              layer 0 (single physics source; B11 fix)
core/state.py                 layer 1 (current-position fleet decode)
core/ledger.py                layer 2
core/candidates.py            layer 3 typed CandidateAction
core/policy.py                layers 3 + selector + orchestration (v3.2 Forecast core; data-flow contract)
core/features.py              layer 4 (feature_vector = 25-dim train/serve contract)
core/rule_engine.py           layer 6 (wired via _rule_gate; pass-through default)
core/oracle.py                layer 7 FlightOracle (first_hit / trace_from_position / decode_existing_fleet)
core/action_emitter.py        layer 7 emitter (preserves intended targets into the sanitizer)
core/action_sanitizer.py      layer 7 final emission gate (sun/oob always; wrong-first-hit opt-in)
models/                       offline training/export for layer 5 (train_candidate_scorer, export_npz, …)
tests_orbit/                  layer tests: geometry/oracle, state-fleet-decode, features, policy-smoke,
                              config-layer, rule-engine-wiring, hybrid-model, action-sanitizer, ledger
```

Provenance: prompts 02/03 (core substrate + FlightOracle gate), 04 (dataset/features), 05 (model
training), 06 (hybrid integration), **08 (OW-ARCH-001 layered refactor: main.py→core/policy.py, physics
dedup, config layer, P0 correctness fixes)**; B11 fix + arena results in `tracking.md` / `bugs.md` /
`insights.md`.
