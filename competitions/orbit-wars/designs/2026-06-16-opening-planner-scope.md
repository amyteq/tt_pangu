# Scope — integrated opening-sequence planner (T20 follow-on)

> orbit5, 2026-06-16. Grounded in `orbit_wars.py`, `agent/versions/v4.py`,
> `agent/versions/suite/evogen1093.py`, `forecast_sim.py`, and a 3-agent study
> (evogen reverse-engineering + v4 integration + adversarial red-team).
> **Bottom line: build the 3 measurement probes FIRST, not the planner.** The probes
> are the cheapest way to get the first hard evidence in 12 levers about whether the
> opening is a real, non-greedy, win-predictive lever. Strong base rate of failure.
>
> ## ⛔ PHASE 0 RESULTS (2026-06-16) → DO NOT BUILD the set+order planner
> Ran the three probes (`arena/opening_probes.py`, 40 games vs evogen + 20 vs starter,
> 80 opening states, reusing v4's `_solve_intercept`/`_path_blocked` + `forecast_sim`):
> | probe | result | verdict |
> |---|---|---|
> | **P1 super-additivity** | median Δ(CP-search vs CP-greedy) = **+0.0%**, frac>5% = 0%; **P1b** Δ(CP-search vs v4 conservation-greedy) = **+0.0%** | **KILL** |
> | P2 objective-divergence | first-3 agreement (CP vs `_term`) = **73%** (<80%) | PASS (marginal) |
> | P3 conversion | control@80 → win: r=**+0.57** (all 60) / +0.36 (evogen, 3/40 wins) | PASS |
>
> **The decisive probe P1 KILLs it.** A set+order search captures **zero** extra
> controlled-production over greedy — *and zero over v4's actual conservation-greedy* —
> in every opening state: our greedy already grabs the affordable opening optimum, so
> **order/selection is moot** (you control the planets you can afford regardless of
> sequence). This empirically confirms the red-team prior (a planner re-derives greedy).
> P2/P3 "pass" but are hollow given P1: the 27% different picks (P2) yield no extra
> control (P1), and although the opening predicts the win (P3), we are **not leaving
> opening control on the table** for a planner to seize — we *lose the control race*
> because we reach worse board states (the integrated cliff), not because we plan the
> opening badly. Per this scope's gate ("build only if all three pass") → **STOP**.
>
> **Only remaining crack (untested by these probes):** evogen's *timed wait-to-mass*
> (accumulate at one source to take a target unaffordable NOW). The probes required
> affordability-now, so they did not test timing. But it is a narrow, single-mechanism
> lever adjacent to the refuted EM/OVERKILL sizing family — NOT the multi-week
> integrated planner — and carries the same over-commit risk. Not recommended without
> its own measure-first probe. Net: the integrated opening-planner build is **shelved**;
> Phase 0 did its job — prevented the 13th refuted lever (a multi-week build) for ~1h of
> measurement. v4 (~700) stays on the ladder; kuni05 (1079.7) + coarr remain the anchors.

## 1. Problem & the ONE genuine escape axis
- The cliff: ~100% vs weak, **0–20% vs strong** (evogen 1093 / multifocus / kuni05 1240); v4 ladders ~700.
- Episode 80118852 (our kuni05): opening is **多而小** — early ≤step80 median launch ~20 ships, we trail in planet count (5 vs 7 @ step40), mass only late.
- **12 single-mechanism levers refuted** (OW_OVERKILL, OW_MULTISRC, OW_COARRIVAL, OW_OPENING, v4a/f/c/i, T20 OW_EM). 
- 🔑 **Red-team prior (`v4.py:130-138`, 2026-06-12):** set/beam planning over the **conservation-correct terminal value** provably **re-derives the greedy menu** — under conservation, concentration/coordination/ordering have **zero marginal value** (the `value<=0` gate kills them); a beam's couplings map 1:1 onto the refuted levers.
- **The one untested axis:** evogen's opening does **not** use the conservation-terminal value. It optimizes an **own-side additive horizon-production accumulation** (`opening_score`, evogen1093.py:661-673) under which **earlier/compounded captures have strictly positive marginal value**. A planner on *that* objective is the single element of the proposal not auto-refuted by the prior. Everything else (set/order, multi-source, capture-and-hold sizing) is a recombination of refuted couplings.

## 2. Reference — what evogen actually does (cited)
- **Branch-and-bound DFS over capture SEQUENCES** (evogen1093.py:738-763), run **only the first 3 env steps** (`OPENING_TURNS=3`, :68, :811-812); per-turn greedy after.
- **Objective `opening_score`** (:661-673): Σ over planets I'll own of `stationed + prod·(H−turn)` + in-flight landing garrisons. Monotone-additive, **no enemy/conservation term** → ordering compounds.
- **Captured-planet feedback** (:622-630, :751-761): a grab becomes a new source AND its production finances the next grab; target B's capture-turn/source/gain are recomputed *after* A is owned.
- **Timed single-source mass** (:573-575, :598-611): waits, `launched = stationed + prod·wait`, launches only when one source alone beats the garrison at landing — directly fixes "thin grabs that don't stick."
- **Optimistic-bound pruning** (:728-736, :743-744) over a small pre-sorted positive-gain candidate set → tiny tree, sub-budget.
- **Transferable delta vs our `OW_OPENING` (v4.py:639-696):** SET+ORDER joint valuation + timed-mass + the **hold-rewarding additive objective**. (Note: evogen's *opening* is single-source — multi-source pooling is its *mid-game* `plan_target_commitment` :349-479 — so multi-source is **not** the opening delta.)

## 3. The crux — why our value fn can't express this
`_term` (v4.py:553-558) reads only `k=H` of one planet's owner/ships: `+mine / −enemy / 0 neutral`; candidate `value` (783-785) sums it over the two touched planets minus the do-nothing baseline; `value<=0` gate (798). It is **blind** to: (a) **opponent-denial** (frozen do-nothing opponent — taking a contested neutral first has no representation); (b) **board-position/region control** (per-planet additive, no joint board term — the 5-vs-7 planet deficit is unscored); (c) **tempo** (single fixed `H=26`; a grab now vs in 15 turns look identical; `signed_adv`'s γ=0.97 discount, fsim.py:183-195, is **unused** in the gate). ⇒ a planner optimizing `_term` is provably greedy. The opening planner needs its **own** objective reading the **whole owner-trajectory** (control over time) summed jointly across my planets.

## 4. Proposed design — IF (and only if) §5 probes pass
- **Injection:** replace the `OPENING` block (v4.py:639-696, `if OPLAN and step < OPEN_WIN: ... return plan_moves`), preempting the greedy menu for the opening window only; fall through to greedy + hub-and-hammer after. Gated **`OW_OPLAN` default-OFF, byte-identical when off.** Emit `[src,angle,int(ships)]`; respect `_avail`/`launch_budget`/`reserve` computed above (484-524).
- **Objective (the novel element):** controlled-production trajectory over `Ho≈50–80`: at each `k` count planets the projection shows me **owning**, sum their `prod`, integrate with a **tempo discount** (reuse `signed_adv`'s γ form, applied to controlled-production not net-ship-at-H). Plus a **STICK** term (a capture that `replay_planet` shows flipping back before `Ho` contributes ~0 — credits hold without the refuted `EM_HOLD` knob) and an **opponent-denial** term (contested neutrals — reachable by a nearby enemy source within `Ho` via `_exposure` :884-899 — worth more taken first). **Owner-agnostic** (count MY planets, all others "not-mine") → 4p-safe.
- **Search:** thin **frozen-opponent beam, width ~3–4, depth ~3 grabs**, opening-only. Score a plan by **event-append + `replay_planet`**: assign each planned launch an arrival turn via `_solve_intercept`, append `(eta,player,ships)` to each touched planet's `base_arr`, `replay_planet` every touched planet, read the full owner list. ~5–7 µs/replay → ~50 µs/plan → **~1000 plans in 50 ms** (budget ~996 ms headroom; v4 typical 1–4 ms/turn). Opponent-aware term added **only after** a frozen version shows signal (avoid the v4f trap).
- **Sizing:** capture-for-hold via **`_flip_need`** (exact min ships to own at K, v4.py:808-847), **not** `EM_HOLD·defender`. Hard constraint: **commit ≤ greedy total opening ships** — win by ordering/targeting, not by sending more (else it is EM, monotonic-negative).
- **Reuse (no new sim):** `_solve_intercept`, `_path_blocked`, `project`/`replay_planet`, `signed_adv`, `_safe_surplus`, `_flip_need`, `reserve`/`launch_budget`, `_exposure`. Honor per-player state (`_V4S`, :218) to avoid the mirror-seat bug.

## 5. ⛔ Measure-first gate — 3 offline probes BEFORE any agent change
Per the project's measure-first discipline (correctly PARKed T16). All offline, reuse `forecast_sim.project/replay` + `OW_LOG`/episode pipeline, **zero agent change, zero ladder cost, ~1–2 days**.
| Probe | Question | KILL if |
|---|---|---|
| **P1 Super-additivity** | best SET+ORDER controlled-production vs Σ greedy independent picks, on logged opening states | joint − greedy ≈ 0 (<5%) → red-team prior confirmed; planner = greedy |
| **P2 Objective-divergence** | does controlled-production-at-`Ho` pick different first 1–3 targets than the conservation greedy? | rankings agree >80% → objective colinear; planner = OW_OPENING-with-a-sort |
| **P3 Conversion** | does step-80 board-control predict the terminal win over ~80 logged games (vs evogen+starter)? | \|r\|<0.2 / AUC<0.6 → opening isn't the cliff lever |
**Only if all 3 pass** is the thin planner (§4) justified.

## 6. Validation — IF built
- **Gate:** vs evogen ≥150 paired seeds (300 games, ±3.5pt), **+7pt bake bar** (the bar that baked t14, caught a regression). 
- **No-regress:** starter ≥85% AND **not** a one-sided weak-tier bump (the v4f/EM over-defensive tell). **4p:** `eval_4p` avg_rank/1st-rate/elim-by-t50 no worse than baseline (~1.78). **Cliff ref:** multifocus/kuni05 tracker (expect no gradient).
- **Opening-isolation:** clamp-to-opening arm vs a sham all-game arm (if all-game is no worse, the "opening" framing isn't what's acting); `OW_LOG` count of divergent opening decisions/game (prove it FIRES — the v4a lesson).
- **Kill at any:** over-defensive tell · monotonic-negative param sweep (do NOT parameter-search — refuted anti-pattern) · <+7pt at 150 seeds → record as the **13th refuted lever**, default-OFF.

## 7. Risks (why it is likely the 13th refuted lever)
1. The action space (set/order/multi-source/hold) is refuted couplings; only the objective is novel — narrow and entirely load-bearing on P1/P2.
2. Controlled-production-at-H is **nearly colinear** with OW_OPENING's `prod·(H−eta)−cost` (v4.py:679-681) — the set wrapper may be all that differs, and that wrapper is the refuted beam.
3. Capture-for-hold is the **EM mechanism**, monotonic-negative (over-commit); a *set* of hold-sized grabs commits MORE ships earlier — the wrong direction.
4. **Cliff diagnosis** (overkill-revival postmortem, EPISODES.md #1): v4 floors ~1–2% vs kuni05 because we can't reach the board states where it matters — the bottleneck may be mid-game, not the opening. The ep-80118852 evidence is a **4p win vs collapsing rivals**, weak for the 1v1 cliff cause.
5. Opponent-awareness is **v4f's exact failure surface** (−9pt over-defensive) — add it only after a frozen version shows signal.
6. **Measurement power:** evogen has discriminating power but the real cliff (kuni05) has none — the validation that matters most is the weakest.

## 8. Effort, phasing, deadline
- **Phase 0 — probes (§5):** ~1–2 days, offline. Decision gate: all 3 pass → Phase 1; any fail → STOP, record measured-then-parked (like T16/T8/relay). **Fits before the 2026-06-23 deadline.**
- **Phase 1 — thin frozen planner (§4):** ~2–3 days build + 150-seed gate. Default-OFF.
- **Phase 2 — only if Phase 1 clears +7pt:** opponent-denial term, 4p tuning, ladder submission. ~3–4 days.
- **Total ~1–1.5 weeks IF the probes pass** (does NOT fit before 2026-06-23); ~1–2 days if they kill it (the likely outcome). Pre-deadline, **only Phase 0 is feasible** — the full planner is a post-deadline / final-eval-window effort.

## 9. Recommendation
> **UPDATE 2026-06-16: Phase 0 executed → DO NOT BUILD (see the Phase 0 Results box up top).**
> P1 KILLed it (set+order search = greedy, +0.0% controlled-production). The integrated
> opening planner is shelved; the only residual crack is evogen's timed wait-to-mass,
> which would need its own measure-first probe and is not recommended (narrow, over-commit
> risk, adjacent to refuted EM/OVERKILL). Original recommendation retained below for record.

**`build_minimal_first`** — build the 3 probes (Phase 0), not the planner. They empirically test the red-team prior (super-additivity, objective-divergence, conversion) instead of re-asserting or re-defying it, at ~1–2 days and zero ladder cost. If any fails (the strong base rate), we avoid the 13th refuted lever for the cost of measurement. If all pass, that is the first hard evidence in 12 levers that the opening is a real exploitable non-greedy lever — and the thin frozen planner is then justified at the +7pt bar. Keep v4 (~700) on the ladder and kuni05 (1079.7) + coarr as anchors throughout.
