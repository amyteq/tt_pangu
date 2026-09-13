# Orbit Wars — KCA competition workspace

Kaggle **Orbit Wars** ($50,000 Featured, deadline **2026-06-23**, ~4137 teams).
Agent-vs-agent RTS on `kaggle_environments`; **1v1 (2-player)** skill-rating ladder, μ0=600
(LB top ≈ 1732, top-10 ≈ 1500–1600 as of 2026-06-10).

**Architecture:** see [ARCHITECTURE.md](./ARCHITECTURE.md) — the layered hybrid design (deterministic v3.2 core + optional model candidate-scorer; deterministic last word).

## Current status (2026-06-14, KCT-003 consolidation)

> Live tracking now lives in [`tracking.md`](./tracking.md) (issue #87 tables, English) and the docs below;
> the long chronological log is retained further down this file as the historical record.
> Issue #87 is kept open for history but is no longer the place for new status updates.

- **status:** active (deadline **2026-06-23**; final eval ~2 weeks after)
- **direction:** D1=**C** (low-cost continue: replay mining + suite-gated param optimization); incremental path
  largely exhausted (7 single-mechanism levers failed) — strong tier wins as integrated systems.
- **best own real-training agent:** Forecast **v3.2** (t14-tuned: H26/FF5/FD20/CE3.2/CL1.3), 6/6 VALIDATION gates.
- **ladder (refreshed 2026-06-14, read-only Kaggle):**
  - harrysun2006 latest-2: `submission_kuni.tar.gz` (adapted kuni05, **attributed**) **1085.4** + `main.py` v3.2 **660.0**
  - firefly2006 (may) latest-2: `v3_2_coarr.py` **648.8** + `main.py` v3.2 **636.7**
  - retired peaks: adapted-kuni05 **1151.0**, Forecast v3 686.1, v2.1 555.8. Leaderboard top **~1746**.
- **current blocker:** strong-tier cliff — ~100% vs weak agents, **0–15% vs the strong tier**
  (evogen 1093 / multifocus / kuni05 1240). Private LB not released.
- **next:** v4 "Scheduler" (hub-and-hammer; parity with v3.2 so far) next cut = counter-attack window /
  cluster-targeted hammer; freeze best-2 for re-submission in the last 3 days (D2).


## TL;DR — final status (closeout 2026-06-10)

Two tracks; **accepted the split** after rigorously exhausting the incremental path.
- **Live entries (the comp keeps your latest 2 active):**
  - `adapted-kuni05` (LB 1240.5 public agent, **attributed**) — **~1124 and climbing** → our competitive entry.
  - **`Forecast v3`** (our own, from scratch) — **~720** (well above v2.1's ~556; clearly beats every
    weak public agent; ~15% vs the weakest strong one).
- **Our own agent (`agent/main.py`) = Forecast v3.1**: bit-exact forward simulator (validated 0 error
  vs the engine) + differential terminal net-ship value + sim-based defender floors + light defense.
- **The wall:** a hard cliff — we win ~100% vs weak agents, **0–15% vs the strong tier** (evogen 1093,
  multifocus, kuni05 1240). Five bolt-on levers (consolidation, safe_drain, defense, multi-source,
  opening-planner), all measured on a **ladder-predictive opponent suite**, none cross it — the strong
  tier wins as integrated *systems*, not via transplantable mechanisms. Closing it needs a multi-week
  kuni05-class rewrite, judged not worth it vs the split.
- **Reproduce:** `pip install "kaggle-environments>=1.28.0"`; vendored opponents are gitignored —
  rebuild via `arena/_reconstruct_pkg.py` (kuni05) / `arena/_extract_pub.py` (suite) from the public
  notebooks; then `python arena/suite_gate.py main --procs <cores>`.

Detailed log below (chronological; experiments, dead-ends, and evidence).

## Layout

> **Layered since OW-ARCH-001 (2026-06-18):** `agent/main.py` is now a **thin entrypoint** that calls
> `core/policy.py`; the v3.2 strategy, physics (`core/geometry.py`), state/ledger/features/oracle and the
> emit→sanitize gate live under `core/`, and config under `config/` (baked PyYAML-free to
> `agent/config_baked.py`). See [ARCHITECTURE.md](./ARCHITECTURE.md) for the 8-layer map. The submission is
> `main.py` + `core/` (+ `agent/config_baked.py`) as a tar.gz — stdlib-only at runtime.

```
competitions/orbit-wars/
  agent/main.py        # thin Kaggle entrypoint -> core.policy.get_default_policy().act(obs)
  agent/config_baked.py# baked default config profile (stdlib dict; no PyYAML online)
  agent/versions/*.py  # frozen self-contained snapshots (v1..v4, forecast, …) for h2h regression
  config/              # YAML config source + profiles + bake.py (-> agent/config_baked.py)
  core/                # layered policy: geometry, config, state, ledger, candidates, features,
                       #   rule_engine, oracle, action_emitter, action_sanitizer, policy
  tests_orbit/         # layer tests (geometry/oracle, fleet-decode, features, policy-smoke, config, …)
  arena/pool.py        # parallel engine: fans independent games across CPU cores
  arena/arena.py       # round-robin / head-to-head on the REAL engine (offline gate)
  arena/validate.py    # held-out validation on fresh seeds
  arena/sweep.py        # garrison/cap sweep, gated vs v1 snapshot
  arena/sweep_phase.py  # phase-scaled cap sweep, gated vs v2 snapshot
  arena/diagnose.py    # single-game loss tracer
  README.md            # this file
```

The engine is pure-Python and CPU-bound (a GPU does not help); wall-clock is just
running many 500-step games. `arena/pool.py` parallelizes across cores — on a 24-core
box, ~96 games run in ~8s (≈30-40x serial). Results are **deterministic and identical
to serial** (each game is seeded; verified procs=1 vs procs=12), except against the
inherently-random `random` agent. All arena tools take `--games`, `--procs`, `--base`
(first seed). To run on the RTX 4090 box (snorlax), use its CPU cores via `--procs`.

## Ground truth

The engine is installed locally and is the source of truth (do not re-derive from
the web competition page, which is JS-rendered and unreadable by fetchers):

`…/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Key mechanics we exploit (with engine line refs):
- **Deterministic orbits** (`orbit_wars.py:540-546`): a planet's position at any step is
  `angle = atan2(iy-50, ix-50) + angular_velocity * step`. We predict exact arrival
  positions and solve a real intercept instead of aiming at stale coordinates.
- **Exact capture rule** (`:667-674`): a single attacker captures iff
  `ships > garrison_at_arrival` (strict). Neutrals don't produce; enemy planets gain
  `production * travel_ticks` (`:512-514`). So the official `garrison+1` baseline is
  *wrong* for moving/producing targets — we lead the growth.
- **First-hit consumption** (`:588-598`): a fleet is consumed by the FIRST planet its
  swept path touches, and dies on the sun / out-of-bounds (`:602-609`). Launch angles
  must avoid friendly/neutral bodies and the sun, or the whole fleet is wasted.
- **Combat sums same-owner fleets arriving the same tick** (`:642-665`): "largest minus
  second-largest survives"; ties annihilate. Synchronized multi-fleet arrival is a real
  lever (planned for v2).

## Agent versions

### v2.1 — "Phase-Scaled" (current best; `agent/main.py`, snapshot `agent/versions/v2_1.py`)

v2's in-flight cap is flat (1.2×). v2.1 makes it phase-dependent: looser early to win
the land-grab, tighter late to hold and bank — `cap(step) = lerp(CAP_EARLY, CAP_LATE)`.
A gated sweep vs the frozen flat-1.2 v2 snapshot (`OW_CAP_EARLY`/`OW_CAP_LATE` only affect
the candidate; v2.py predates those knobs) found **2.0 → 1.0** best (60% on tuning seeds);
*mild* scaling won, aggressive scaling (2.5-3.0 early / 0.6-0.8 late) all lost.

**Validation on 24 FRESH seeds (4000+, unused in any tuning), x2 orderings:**

| Matchup            | Record  | Win%  |
|--------------------|---------|-------|
| v2.1 vs v2 (the bar)| 26-22-0 | 54.2  |
| v2.1 vs v1         | 39-9-0  | 81.2  |
| v2.1 vs starter    | 39-9-0  | 81.2  |
| v2.1 vs random     | 48-0-0  | 100.0 |

**Confidence note (honest, updated after a 200-game confirmation):** phase-scaling is a
**wash on win-rate, not a real improvement.** vs-v2: 60% (40g tuning) → 54.2% (48g held-out)
→ **52.5% (200g confirmation)**; aggregate 155-133 = 53.8% over 288 games (one-sided
p ≈ 0.10, 95% CI on the 200g run ≈ [45.6%, 59.4%] — includes 50%). The edge shrank toward
50% as n grew (regression to the mean). v2.1 *does* end with a higher avg ship count
(1709 vs 1469), but LB reward is win/loss, not margin. Kept only because it's harmless and
slightly more flexible — **cap-tuning has hit diminishing returns; further gains need a
structurally different lever (consolidation, synchronized strikes, search) tested against
STRONGER/more diverse opponents, not flat-1.2 self-play.** Defaults `CAP_EARLY=2.0`,
`CAP_LATE=1.0` (`OW_*`-overridable).

### v2 — "Hold What You Take" (superseded; snapshot `agent/versions/v2.py`)

Diagnosis of v1's only losses (deterministic on map seed 1007, both seat orderings):
v1 captured 41 planets but *lost 39*, peaking at **756 ships in flight** while holding
only **~13 ships/planet** (starter held ~30). Root cause: v1's reserve was 0 whenever no
fleet was *currently* inbound and it sent "exactly enough", so every captured planet sat
at ~0 garrison and was retaken — a capture-churn loop that bled ships in transit while
starter banked and out-produced (classic leaky expansion).

A first heavy-handed fix (large garrison + 0.55 in-flight cap) **over-corrected** — it lost
to v1 (21.9%) because it killed the fast expansion that wins most maps. An arena sweep
(gate: must beat the frozen v1 snapshot head-to-head) found the real lever is a **mild
in-flight cap** plus a *small* frontier garrison:

- `INFLIGHT_CAP_FRAC = 1.2` — total in-flight ships may not exceed 1.2× ships-on-planets
  (v1 reached ~5×). Preserves aggression, kills over-commitment. **This is the decisive lever.**
- `FRONTIER_FLOOR = 10` — planets within 28 units of an enemy keep a small standing garrison.
- `REAR_FLOOR = 0` — rear planets stay fully aggressive.

(All tunables are `OW_*` env-overridable for sweeps; baked defaults are the tuned values.)

**Validation on 20 FRESH seeds (3000-3019, unused in tuning), x2 orderings:**

| Matchup            | Record  | Win%  |
|--------------------|---------|-------|
| v2 vs `starter`    | 37-3-0  | 92.5  |
| v2 vs `random`     | 40-0-0  | 100.0 |
| v2 vs v1 (h2h)     | 30-10-0 | 75.0  |
| seed 1007 (was a loss) | win both orderings | ✅ |

### v1 — "Intercept Economist" (superseded; snapshot `agent/versions/v1.py`)

Economic expansion with: deterministic position prediction → fixed-point intercept
solver → exact capture math (neutral static vs enemy growth) → sun/planet path
avoidance → light inbound-fleet defensive reserve → greedy global allocation (each
target committed once, ranked by production-per-ship discounted by travel time).
Wrapped so any error returns `[]` (passive but alive — never forfeits on a crash).

**Offline results** (`python arena/arena.py --games 8`, 16 games/matchup, real engine):

| Matchup            | Record    | Win%  | Avg score      |
|--------------------|-----------|-------|----------------|
| v1 vs `random`     | 16-0-0    | 100.0 | 2453 vs 0      |
| v1 vs `starter`    | 14-2-0    |  87.5 | 1924 vs 636    |
| `starter` vs `random` (sanity) | 16-0-0 | 100.0 | — |

Per-turn cost ≈ **0.72 ms** on the densest state (28 planets / 60 fleets); budget is
1000 ms → ~1380× headroom for future search.

### Roadmap (v3+ ideas, by expected impact)

1. ~~Investigate the 2 losses to `starter`~~ — **done → v2** (leaky expansion; fixed by
   in-flight cap + frontier garrison; see v2 above).
2. ~~Per-game-phase cap scaling~~ — **done → v2.1** (2.0→1.0; small consistent edge, ~wash
   on a 200g confirmation). A finer frontier-param sweep is still open.
3. ~~Consolidation (forward idle rear surplus)~~ — **TRIED → REJECTED, default OFF**
   (`arena/sweep_consol.py`). Never beats v2.1: −20pts when aggressive (min=12: 30% vs v2.1),
   neutral when rare (min≥30: 40-40). Forwarding wastes transit, starves the in-flight cap,
   and funnels launch points; our aggression already uses rear ships well. Code kept,
   env-gated (`OW_CONSOLIDATE=1`) for reproducibility. **Calibration note:** identical-mirror
   matches tie often (~18/80), so the "no-edge" win% is ~39%, not 50% — read decisive W-L.
4. **Real targeted defense** — predict inbound impact planet + tick precisely (swept test)
   and reinforce the *specific* threatened planet from neighbors, vs the current flat floor.
5. **Synchronized strikes** — exploit same-tick same-owner summing: stage fleets from several
   planets to co-arrive on a hard target (distinct from consolidation — keep launch points,
   just time the arrivals; bigger fleets are also faster).
6. **Comet play** — capture/deny comets near our territory for temp production (they leave
   with their ships at the path end; bounded investment).
7. **Time-bounded lookahead** — with ~1000× budget headroom, a 1–3 ply search with a
   production-weighted control eval over a small `(target × ship-fraction)` action set.

## Sparring opponents

Self-play vs our own variants has low information about real standing, so we pull strong
public agents as gate opponents (`arena/_extract_pub.py <notebook.ipynb> <out.py>` lifts a
notebook's `%%writefile submission.py` cell into a runnable file).

- **`agent/versions/pub_tactical.py`** — sigmaborov "Tactical Heuristic 2026" (lead-aim,
  sun-avoidance waypoint routing, comet prediction, a full planet-future combat simulator,
  net-defense reserve). Pure heuristic, **1.6 ms/turn**, runs clean (0 errors in audit).
  Baseline (120 games each, 60 seeds x2): **v2.1 beats it 90.8%** (avg 5449 vs 291),
  v1 89.2%, and it beats `starter` 55-45. So strength order is `v2.1 > pub_tactical > starter`
  — a legitimate non-trivial opponent, but we already dominate it, so it weakly discriminates
  small tweaks. Useful as a sanity gate; not a hard teacher.

### 4-player coverage (`arena/arena4.py`)

The env supports 2 AND 4 players (`make("orbit_wars").specification.agents == [2, 4]`), so we
test both. 4p metric = hero win-rate (placed 1st of 4; ties-for-first count) + avg finishing
rank (1=best). The hero is rotated through all 4 seats per seed for fairness.

Baseline (120 games each, 30 seeds x4 seats, base 6000):

| Hero = v2.1, field | Win% | Avg rank |
|--------------------|------|----------|
| vs 3x random       | 100  | 1.00 |
| vs 3x pub_tactical | 90.8 | 1.09 |
| vs 3x starter      | 65.8 | 1.34 |
| vs [pub,v1,starter]| 41.7 | 1.62 |
| vs 3x v2.1 (mirror)| 57.5 | 1.59 |
| pub_tactical vs 3x starter | 25.8 | 1.79 |

**Resolved:** our 2p strength transfers — v2.1 wins 1.7-2.6x its fair share vs every non-trivial
4p field and finishes near rank 1. Aggression works in crowds too.

**Two calibration notes:**
- The 4-identical **mirror gives ~57.5%, not 25%** — a seat tied for first counts as a win and
  symmetric play yields frequent top-ties. So in 4p, **~57% is the "no-edge" null** for comparing
  near-identical agents; prefer `avg_rank` as the discriminator there.
- **pub_tactical ≈ random-level in 4p** (25.8% vs starters); its careful 2p play doesn't scale to
  crowds. For 4p stress-testing, `3x starter` is the harder field.

**RESOLVED — the scored ladder is 1v1 (2-player).** From the rendered competition pages
(`kaggle competitions pages orbit-wars --content`, kaggle CLI >= 2.x):
- Abstract: *"...AI bots to play a novel multi-agent **1v1 or 4p FFA** game..."* — the engine
  supports both modes.
- Evaluation / skill-rating update: *"If one Submission won, we'll increase its μ and decrease
  **its opponent's** μ ... move **the two μ values** closer towards their mean."* The update is
  **pairwise** (singular "opponent", "the two μ values"), and the validation episode plays
  "against copies of itself" — i.e. the ranked ladder runs **2-player** episodes.

Implication: our extensive **2p** testing is the right LB proxy (v2.1 beats the strongest public
agent we found ~91% in 2p). The 4p arena is kept for robustness/optional, not the primary gate.
(Competition id 138420; deadline 2026-06-23, final eval ~2 weeks after; up to 5 submissions/day,
latest 2 tracked, μ0=600 skill-rating ladder.)

### REALITY CHECK — not competitive with top public agents (the 2p caveat above is now moot)

Pulling agents whose titles state real LB ratings exposed our offline "dominance" as an
artifact of weak opponents. Strongest agents are mostly package-based (`orbit_lite`) or load a
private model; the cleanly-reconstructable one is **kuni05 "Producer Agent" (LB 1240.5)** →
`agent/versions/kuni05/` (main.py + orbit_lite/, needs `torch`; arena adds its dir to sys.path).

- **v2.1 vs kuni05: 0W-60L (0.0%), avg 0 vs 2489** — eliminated every game (~turn 100). v2.1
  keeps pace ~40 turns, then kuni05 out-expands it (more planets faster) and overwhelms.
- pub_tactical vs kuni05: 0-40 (also wiped). So **kuni05 is the real gate**; pub_tactical (we
  beat 91%) was far too weak to be informative.

Closing a 0% gap needs more than heuristic tweaks. Prior session's submissions topped out at
693.1 (one adapted from romantamrazov LB-1224). Next: study kuni05's modules (planner_core,
garrison_launch, intercept_aim) to learn its expansion, and/or a real lookahead planner.
(debatreyabiswas-1300 = private model; romantamrazov agents import an unshipped orbit_lite —
neither reconstructable from its notebook.)

### Design study — why kuni05 (LB 1240.5) beats us (drives v3)

kuni05 is a vectorized (torch) **one-step planner over an 18-turn forward simulation**, not a
deep search. Source `agent/versions/kuni05/` (read planner_core.py / garrison_launch.py).

- **Value = simulated differential.** Each candidate launch is scored by a forward flow
  projection: `score = Δnet_me − Σ Δnet_opp`, net = (produced − combat-losses) over H=18,
  diffed against the do-nothing baseline. (We use a static `prod/(needed·time)` ROI.)
- **`safe_drain` sizing.** Send the MAX a source can shed while the projection keeps it held
  over H (worst held-turn garrison ≥ 0) — maximal safe commitment, not "exactly needed".
- **`capture_floor` per arrival turn** — defenders grow with k (production + reinforcement),
  owner-aware (floor 1 if we'll own it).
- **Forward model tracks in-flight enemy fleets** (so threats/defense are real, not guessed).
- **Regroup** leftover ships up an enemy-pressure gradient toward stressed owned planets
  (consolidation done right — gradient + still-owned-at-arrival check; ours was naive→rejected).
- Greedy best ≤6 waves/turn, source-budget aware, role mutex (reinforced planet ≠ source).

The gap is architectural. **v3 plan ("Forecast Planner"):** clean-room reimplement this in plain
Python (no torch, keep single-file submission): (1) a do-nothing forward sim producing per-planet
(owner, ships) trajectories over H using the exact engine rules; (2) touched-planet recompute +
differential net-ship scorer; (3) candidate gen (nearest enemy/neutral + flipping-own) with
safe_drain sizing + intercept aim + capture-floor gate; (4) greedy ≤W waves; (5) optional regroup.
Gate every step vs the kuni05 snapshot in 2p (avg_rank/decisive W-L). Realistic goal: go from 0%
to *competitive* (survive + win some), then climb — not necessarily beat kuni05 immediately.

### v3a (safe_drain increment) — TRIED → REJECTED

Adopted kuni05's `safe_drain` sizing + per-arrival-turn defender floor onto v2.1's greedy
(`agent/versions/v3a.py`, env-gated, not promoted). Result: **vs v2.1 36.2%, vs kuni05 0%,
vs starter 82.5% — worse across the board.** safe_drain frees too many ships for our
ROI-ranked greedy → over-expands thin. Lesson: kuni05's pieces only work *with* its forward-sim
differential value function, which gates launches to net-positive moves. **The value function is
the irreducible core; heuristic increments (consolidation, safe_drain) regress without it.**
main.py stays v2.1. Closing the kuni05 gap needs the full forward-sim differential planner
(big build, uncertain vs a 1240 agent) — or pragmatically adapting a public agent.

### Track 2 (adapt public) + Track 1 (build our own) — in progress

Decision (user): ship an adapted public agent for a real LB score NOW, build our own planner meanwhile.

- **Track 2 — DONE (submitted):** reconstructed **kuni05 (LB 1240.5)** repackaged as a tar.gz
  (main.py + orbit_lite/, torch) with **clear attribution**, self-play-clean, submitted. Expect
  it to climb toward ~1240. (v2.1's own ladder score came in at **601 ≈ baseline** — confirms our
  heuristic is bottom-tier; this is the strong reference under our account.)
- **Track 1 — "Forecast" planner v3: DONE, PROMOTED TO main, SUBMITTED.** `agent/main.py` is now
  the Forecast planner (single-file; `forecast_sim` inlined). Architecture: bit-exact do-nothing
  forward sim (per-planet owner/ships over H=18; `agent/versions/forecast_sim.py`, validated 0
  error vs engine over 3672 cells) → per-candidate value = **differential TERMINAL net-ship
  advantage** (replay the 2 touched planets with the launch, diff `Σ(my−opp ships at H)` vs the
  do-nothing baseline) → sim-based defender floor at the arrival turn → v2.1's greedy/cap/sizing.
  - **Key bug found & fixed:** scoring planet-ships over *all* k penalized ships-in-transit
    (launch looked like a loss) → near-passive (2.5% vs v2.1). Switching to **terminal (k=H)**
    advantage is conservation-correct (transit ships have landed by H; production preserves tempo).
  - **Result:** beats v2.1 **88.8% (1000+) / 91.2% (held-out 5000+)**, 95-97% vs starter, ~4ms/turn,
    self-play clean. Inlined main.py reproduces it (91.7%) and is ruff-clean.
  - **Still 0% vs kuni05** (1240) — Forecast will land above v2.1's 601 but below kuni05; closing
    that gap is the next goal (deeper value: multi-wave lookahead, opponent modeling, regroup).
- **v3.1 "Forecast+Defense" (current main).** Adds **sim-based defensive reinforcement**: owned
  planets the projection shows flipping to an enemy are added to the candidate set, sized to the
  deficit, and the value fn chooses to defend them (stops the mid-game collapse we saw vs kuni05).
  Beats v3 **62-66%** (held-out), 91.7% vs v2.1, 98% vs starter; self-play clean; still 0% vs kuni05.
  Promoted to main + snapshot `agent/versions/v3_1.py`. **NOT resubmitted** — see below.
  - **Submission trade-off (latest-2-tracked):** the comp only keeps your latest 2 submissions
    active. Ours are [Forecast v3, adapted-kuni05 ~1120]. Resubmitting v3.1 would retire kuni05
    (our top LB entry) for a bot that ladders below it. So we promote locally but hold resubmission;
    submit our own line only once it's competitive with kuni05, or deliberately near the deadline.

### CRITICAL — self-play arena does NOT predict the ladder

Ladder scores (μ0=600 start): adapted-kuni05 **1114**, Forecast v3 **561**, v2.1 **556**.
Forecast v3 beat v2.1 **91% offline** but landed **~tied** with it on the ladder — and *below*
the 600 baseline (both are net losers vs the real pool). The offline self-play gate (vs
v2.1/v3/starter) has ~zero predictive value for ladder movement: our agents beat each other but
all cluster ~555-561 against the diverse field, while kuni05 (genuinely strong) sits at 1114.

Implications:
- Promoting/resubmitting our own line (v3, v3.1, ...) is low-yield AND retires kuni05 (latest-2
  rule) — net negative. Keep kuni05 as the live entry; develop our line locally.
- To actually improve our OWN agent on the ladder we must gate against a DIVERSE pool of real
  public agents (spanning the strength range), not self-play — or reach kuni05-class
  sophistication (multi-wave value + opponent modeling + regroup). Self-play lever-grinding is
  proven low-yield (v3->v3.1 offline gains ≈ 0 ladder gain expected).

### Diverse-opponent gate (`arena/suite_gate.py`) — ladder-predictive

Built a fixed suite of public agents spanning the strength range so offline win-rate tracks the
ladder (self-play did not). Usable members (vendored under `agent/versions/suite/`, gitignored,
reconstruct via `arena/_extract_pub.py`): random, starter, **adilshamim** (weak, loses to starter),
**pub_tactical**, **evogen1093** (LB 1093), **multifocus** (mid-strong), **kuni05** (LB 1240).
(`adaptive`, `carbon_top1`, romantamrazov need the unshipped `orbit_lite` → dropped;
debatreyabiswas-1300 = private model.)

**Validated as a ladder proxy** (suite-average vs real ladder): v2.1 54.8% / 556, v3 54.2% / 561,
v3.1 54.2% / (≈), kuni05 89.6% / 1114. The suite reproduces the ladder's verdict (ours all tied,
kuni05 far above) — unlike self-play, which wrongly ranked v3 ≫ v2.1.

**Diagnosis — a hard cliff:** our agents win ~100% vs every weak member (random/starter/adilshamim/
pub_tactical) and **0-4% vs every strong member** (evogen1093, multifocus, kuni05). We beat everyone
below and lose to everyone above → stuck at the boundary (~560). v3 and v3.1 are identical on the
suite (54.2%) despite v3.1 beating v3 62% in self-play — proof that self-play gains don't transfer.
**To climb, we must win games vs the strong tier; the gate now measures that. evogen1093 (1093) is
the most beatable strong agent → the next target.**

### Design study — how the strong tier beats us (evogen1093 + kuni05)

evogen1093 (LB 1093, single-file `OrbitCommander`): opening branch-and-bound DFS over capture
*sequences* (best set+order of neutral grabs over an opening horizon); `plan_target_commitment`
pools ships from MULTIPLE friendly sources until a target is captured/held; an objective loop +
arrival ledger commits several coordinated waves/turn; supply chains mass ships rear→front; forward
sim with both-sides arrival ledger.

**Synthesis — the strong tier (evogen + kuni05) shares 3 things our Forecast lacks** (impact order):
1. **Multi-source coordination ("synchronized strikes")** — pool several planets to co-arrive on one
   target. We send ONE source, minimal force → single-source captures lose/retaken vs strong play.
   Both strong agents do this; it's the likely #1 reason for our 0-4% cliff vs the strong tier.
2. **Opening-sequence planning** — optimal early land-grab (we expand greedily and lose it).
3. **Supply chains** — gradient/route-based rear→front massing (our naive consolidation failed; theirs works).

Our forward sim + per-move value was necessary but not sufficient: the strong tier plans *coordinated
multi-move* play; we plan one move at a time. **Next build: multi-source coordinated commitment**
(gather nearby friendly ships to co-arrive on a target, sized to capture-and-hold), gated on the
SUITE (target: first >0% vs evogen1093). Then opening-sequence planning, then supply chains.

### Multi-source coordination — TRIED → no gain vs strong tier (default OFF)

Implemented multi-source pooling on Forecast (`agent/versions/forecast.py`, `OW_MULTISRC`,
`OW_HOLD_MULT`): per target, pool the nearest viable sources up to `needed*HOLD_MULT` to
capture-and-hold. Suite result: **still 0% vs evogen1093/multifocus/kuni05; suite avg 53.6%
≈ v3's 54.2%** — no movement on the cliff (slightly negative). Refined diagnosis: pooling makes
captures stick (retaking) but the strong tier beats us by **out-EXPANDING** (2× our planets), and
pooling *reduces* how many targets we take → mistargeted. Defaulted OFF.

**Pattern across 4 bolt-on levers** (consolidation ✗, safe_drain ✗, defense=self-play-only,
multi-source ✗): incremental pieces transplanted from the strong tier don't transfer — those agents
win as whole coordinated SYSTEMS (opening-sequence planning + supply + multi-wave + sim together),
not via any single mechanism. The on-target unexplored lever is **opening-sequence planning**
(directly attacks the out-expansion we lose); beyond that, closing the strong-tier gap likely needs
a full coordinated-planner rewrite (kuni05/evogen class), not increments.

### Opening-sequence planner — TRIED → no gain (default OFF). Incremental path exhausted.

Built an aggressive opening expander (`OW_OPENING`): first 25 turns, grab every reachable neutral
with positive production-gain over a 50-turn opening horizon, bypassing the differential value-gate
and in-flight cap. It DID fire more (9 launches in the first 25 turns vs 2) but win-rate **dropped**
(evogen 15.6%→7.5%) and we still held only 1 planet at step 20 — the extra grabs are thin and don't
stick. Defaulted OFF. (A `PROJ_H` horizon sweep also failed: 18→15.6%, 30→3.1%, 45/60→6% vs evogen.)

**Conclusion — the incremental path is exhausted.** Five levers (consolidation, safe_drain, defense,
multi-source, opening-planner), all measured on the ladder-predictive suite, **none close the
strong-tier cliff**: we stay ~54% suite / ~561 ladder, 0-15% vs the strong tier. The strong agents
(evogen 1093, kuni05 1240) win as integrated SYSTEMS; bolting any single mechanism onto our
greedy-plus-sim planner does not transfer. Closing the gap needs a full coordinated-planner rewrite
(opening search + multi-wave + supply + deeper lookahead, co-designed) — a multi-week, high-risk
effort — OR accept the split: **kuni05 (~1114, attributed) as the competitive entry + Forecast v3.1
(~561, our own from-scratch agent that beats every weak public agent and ~15% vs the weakest strong
one).** Best current own-agent config: Forecast v3.1 (all experimental levers default OFF).

## Running

```bash
cd competitions/orbit-wars
python arena/arena.py                          # default suite (current vs baselines), auto procs=cpu-1
python arena/arena.py --games 32 --procs 23    # bigger, pin worker count
python arena/arena.py --a v2.1 --b v1          # head-to-head (names: random/starter/v1/v2/v2.1 or a path)
python arena/validate.py --games 40 --base 5000  # held-out validation on unseen seeds
python arena/sweep_phase.py --games 40         # gated param sweep (parallel)
```

## Submission policy (per CLAUDE.md)

- Submitting to Kaggle is a **remote write requiring explicit human approval**. This
  workspace is offline-only until approved.
- **Gate**: only submit a version that beats the current best agent in the local arena by
  a clear margin over many seeds (mirrors the KCA autonomous-submission strategy).
- Submit command (when approved): `kaggle competitions submit orbit-wars -f agent/main.py -m "..."`.
- Rules must be accepted on the website first (account already joined).
```
