# kuni05 "Producer Agent" (LB 1240.5) — system study

> OW-P0-RESEARCH-001, 2026-06-16. **Read-only study of an ATTRIBUTED public agent** — for
> conceptual learning, NOT for copying into our from-scratch line. Any reuse must be labeled
> as attributed public source.
>
> **Public source:** `kuni05/lb-1240-5-orbit-wars-producer-agent-submission` (Kaggle kernel
> id **121702304**, author **kuni05**) — **pulled read-only OK** (`kaggle kernels pull … -m`;
> notebook + metadata). Requires **torch**. We also hold a reconstructed package at
> `agent/versions/kuni05/` (gitignored, rebuilt via `arena/_reconstruct_pkg.py`).
> Attribution line: *Based on the kuni05 Producer Agent (LB 1240.5),
> https://www.kaggle.com/code/kuni05/lb-1240-5-orbit-wars-producer-agent-submission*.

## Verdict: rules + EXACT flow-diff planner — NOT a neural net
torch is used purely as a **vectorized tensor calculator** over hand-written rules + an exact
game-physics mirror — **no `torch.nn`, no learnable params, no gradients** (`main.py:19`;
`planner_core.py:75-86` is pure `me − opp` arithmetic). So the strong-tier edge is an
**integrated heuristic SYSTEM**, not learning. This matters: it means the gap to us is
architecture, not data/training.

## Module map (cited)
| Module | Role |
|---|---|
| `main.py:265-301` `run_turn()` | pipeline: movement cache → distance cache → garrison status → plan → emit |
| `main.py:120-262` `plan_lite_waves()` | score one candidate per (source,target); greedy ≤6 waves/turn; regroup |
| `planner_core.py:54-111` | scoring engine wrapping the exact flow-diff scorer |
| `garrison_launch.py:311-450` `sparse_launch_flow_delta()` | per-player net-ship Δ (production − combat) of a launch, exact recurrence over H, only on touched planets |
| `intercept_aim.py:35-154` | continuous fixed-point orbital intercept solver |
| `intercept_aim.py:157-287` | analytic first-contact (swept-pair vs every planet/sun/OOB; lowest-slot tie-break) |
| `movement.py:70-433` | 20-turn position oracle + do-nothing garrison projection (+ per-step inbound buckets) |
| `planner_core.py:587-633` `safe_drain()` | closed-form max ships a source can shed while held over H |
| `planner_core.py:186-232` `capture_floor` | per-target, per-arrival-turn capture threshold |
| `planner_core.py:437-541` `_plan_regroup()` | pressure-gradient marshalling of leftover ships to stressed planets |

## How it answers our 8 questions
1. **State:** `ParsedObs` per-planet tensors (`obs.py:98-100`); `PlanetMovement` predicts x/y/alive over H (`movement.py:70-204`); `cross_dist[k,s,t]` distance cache (`distance_cache.py:49-74`); do-nothing garrison projection with per-step per-owner inbound buckets (`movement.py:375-433`).
2. **Targets:** offensive = up to 12 enemy/neutral by **proximity** to owned sources; defensive = up to 4 owned planets the do-nothing projection shows **flipping**, ranked by urgency `prod·(H−flip)+garrison` (`planner_core.py:271-295`).
3. **Ship size:** **single size = `safe_drain(src)`** (closed-form min projected garrison over held turns, `:587-633`) — *send the max a source can safely shed*, not minimal-capture; gated by `capture_floor` per arrival turn (`:186-232`).
4. **Path oracle:** continuous intercept against the moving target (`intercept_aim.py:35-154`) + engine-faithful analytic first-contact / swept-collision vs sun/planets/OOB (`:157-287`) + AABB broad-phase reachability precheck (`planner_core.py:298-360`).
5. **Forward model:** exact recurrence (production→combat→death) over **H=18 (2p) / 13 (4p)** (`main.py:59`; `garrison_launch.py:83-151`); the **sparse** flow-delta recomputes only touched planets — the scalability trick.
6. **Coordination:** **multi-wave greedy** (≤6/turn, score>ROI 1.5) with a **role mutex** (a planet can't both source an attack and receive a reinforcement same turn) + per-source budget tracking (`planner_core.py:363-434`); **regroup** = pressure-gradient defense (`:437-541`). **No** explicit hub-and-hammer / supply chain / endgame-banking module; **no** search beyond H.
7. **Value:** competitive net-ship differential `Δme − ΣΔopp` from the sparse flow projector — same family as our v3/v4 `_term`, but kuni05 pairs it with **safe_drain sizing + multi-wave + role-mutex + regroup** as one system.

## What we can learn CONCEPTUALLY (no attribution) vs what needs attribution
- **Conceptual (adapt freely):** safe-drain sizing idea; capture-floor mechanics; friendly-flip urgency; pressure-gradient regroup; greedy multi-wave + role-mutex; flow-diff "what-if-I-launch" scoring (standard game-AI).
- **Needs attribution if copied line-for-line:** the **sparse-affected-planet flow projector** (`garrison_launch.py:311-450`), the continuous intercept solver (`intercept_aim.py:35-100`), the analytic first-contact with byte-budgeted chunking (`:157-287`), the safe-drain closed form (`:587-633`).

## Why this is decision-relevant (links to orbit5 findings)
kuni05 has **no single magic lever** — its strength is the *combination* (safe-drain max-shed sizing + multi-wave role-mutex + regroup + exact sparse oracle) co-designed. This is consistent with our 13-lever refutation history and the Phase-0 finding (a planner on our conservation value = greedy): the gap is **integrated-system**, not a missing mechanism. The one concrete thing we DON'T do that kuni05 does and the Phase-0 probe flagged as untested: **send the max safely-sheddable size (`safe_drain`) rather than minimal-capture** — but our EM (T20) tested heavier opening sizing and it regressed (over-commit), so even this is not obviously transferable in isolation. See `tasks.md` follow-ups.
