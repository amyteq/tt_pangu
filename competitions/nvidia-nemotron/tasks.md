# Tasks — nemo

> Derived from issue #86 Table 2 (T1–T13). Full English tracking in `tracking.md`.

## Now
- Hold the **0.86** (`nemo-merge-soup`) entry through the **2026-06-15 23:59 UTC** deadline
  (quota 5/5 used today → locked). Manual: ensure the 0.86 soup is *selected* for private scoring.

## Next — top 4 post-competition tasks (picked from T5/v11, T6, T9, T12, GRPO/RL)
> The deadline is reached with 0/5 quota left, so these are post-competition; they are ordered by
> value-as-reusable-capability and by what unblocks the rest. Rationale + literature in `research.md`.
1. **T12 — local official metric + hard-val set** (✅ built this PR: `lib/official_metric.py` +
   `eval/hard_val_ids.json` + test). *Highest leverage:* it is the prerequisite to evaluate every other
   experiment without burning the 5/day quota; the audit's #1 missing infra.
2. **v11 / T5 — rejection-sampling (STaR/ReST-style) self-distillation.** Sample CoT (from v14, on-policy)
   → keep only ground-truth-correct → SFT. The untried distillation lever; needs a sample-kernel +
   train-kernel (multi-session, ~2–3 GPU runs — that is why it was deferred). Design in `research.md`.
3. **GRPO / RLVR (verifiable-reward RL).** The literature's strongest path for rule/puzzle reasoning
   (Logic-RL, LogicPuzzleRL, Tina). Heavy (online rollouts); run **after** v11 + a stable metric. Design
   in `research.md`.
4. **T9 — elevate `kca-<slug>.yaml` + on-the-fly metadata + flat layout + scheduling into KCA core**
   (#85). ~70% done (PR #106); promote `yaml_meta.py` into the `kca` CLI + multi-account user-pool.

> **Dropped: T6 (Unsloth seq8192)** — superseded; v14 already does seq8192 + the full recipe, so the
> marginal value is ~0.

## Equation frontier (post-comp R&D — needs RTX Pro 6000)
> The only **unsolved** category (≤2/16 hard-val for every adapter incl. the 0.86 soup; surgery couldn't
> move it; high-dose teacher CoT diluted to 0.81). Full plan + rationale + research in
> [`equation-frontier.md`](./equation-frontier.md). It is few-shot **transformation-rule induction**
> (≈ ARC-AGI), inducible only in greedy CoT at eval (no tools). Winners used **brute-force solver → teacher
> CoT** (our Option C, richer solver); TTT is forbidden by our static-LoRA constraint; expect a coverage ceiling.
- **EQ-0 ✅ DONE (2026-06-16) — REFRAMED the plan** (see `equation-frontier.md` §8): the real transform is a
  single **GLOBAL deterministic function** (5-char→1–4-char, 36-sym alphabet; 6216 inputs, 35 collisions), NOT
  per-prompt rules. Per-prompt solvers cover ~0% (homomorphism 0%, positional 0.4%; 61.6% have unseen query
  symbols). But offline we hold **7748 input→output pairs** → reverse-engineerable, **~100% ceiling if cracked**.
- **EQ-2′ ⏸ PARKED (2026-06-16, `nemo5`) — strong-cipher verdict** (see `equation-frontier.md` §8.2–8.3).
  3 crack rounds eliminated the *entire simple-algebraic space* over base-36: homomorphism, positional perm,
  residue `in mod M` (cokernel: gcd-of-minors = 6³⁶ structural), `floor(in/D)`, `A±B`, `A÷B`, `A mod B`, `A·B`,
  products, and `K·in mod M` for K≤60 (K-sweep cokernel). Order-dependent, carries ~3 base-36 digits deep,
  log-uniform output magnitude — a deliberately strong cipher/PRF, **not recoverable from 7,748 samples by
  closed-form algebra**. EV of further hand-cracking now low; durable scripts under `analysis/equation/`.
- **EQ-3 ✅ DONE (2026-06-16) — specialist grid scored, both accounts.** Pivoted to the empirical bet: a
  2×2 coverage×dose grid SFT'd on the real equation prompts woven into the v14 replay backbone, all on the RTX
  Pro 6000 — `nemo-eq-spec` (harry: 1,555 answers, ~16%), `nemo-eq-aug` (harry: 7,814 rotated targets),
  `nemo-eq-hidose` (may: 1,555×3), `nemo-eq-aug-hidose` (may: 7,814×2). Measure on the late-submission window
  (100/day); build soup-with-v14 candidates from any that lift `equation` without dropping bit/cipher (T12 gate).
  - **✅ Result (2026-06-16) — full 2×2 grid scored on LB: COVERAGE helps, DOSE hurts.**
    `eq-aug` (rotated **7,814 real input→output pairs**, ×1) → **0.86 / 0.86** — ties soup public, **beats** soup
    private (0.85) ⇒ **best own-work private of the campaign.** vs `eq-spec` (query-only 1,555, ×1) 0.85/0.85,
    `eq-hidose` (×3) 0.84/0.84, `eq-aug-hidose` (×2) 0.85/**0.82** (overfit). Coverage = rotate every in-context
    example into a query target (~5× more real cipher pairs) → captures the seen-input fraction of hidden
    queries (EQ-0 ~38%). **Reusable insight:** for a global-function/lookup category, SFT on *all real
    input→output pairs at single epoch* — beats query-only and beats higher-dose. **⚠️ Metric caveat:** T12
    hard-val ranked eq-spec **0.167** vs real LB 0.85 (over-samples hardest problems; eq-spec shortcuts under
    uncertainty) → **trust the LB; hard-val is a hard-tail hint only.** (Initial "collapse" read off 0.167 was
    premature — corrected when the LB landed.) **Soup tested & FAILED:** `soup_v2 = SVD(0.86-soup ×0.6 +
    eq-aug ×0.4)` → **0.85/0.85**, below both parents — eq-aug is hard-tail-weak (0.194 hard-val) so the merge
    imports its shortcutting + averages out the equation coverage. **eq-aug 0.86/0.86 standalone is the ceiling;
    EQ-3 COMPLETE.**
- **EQ-1′** rebuild the generator to the REAL structure — BLOCKED on EQ-2′ (needs the cracked rule; parked).
- **EQ-1 / EQ-2** per-prompt induction CoT / DSL solver — INVALIDATED for `equation` by EQ-0 (61.6% unseen-query
  symbols ⇒ per-prompt solving impossible); superseded by the global-function framing.
- **EQ-4** (stretch) RLVR/GRPO with a rule-reproduction verifiable reward — needs the cracked rule (EQ-2′ parked)
  or a model that can verify equation (none does on unseen inputs); deferred.
- **Frontier status (2026-06-16) — BOUNDED, not open.** cryptanalysis side **closed** (EQ-2′ strong cipher).
  Empirical SFT side: `equation` is **partially addressable** — coverage-memorisation (eq-aug) captures the
  seen-input fraction for a real +0.01 → **0.86 / 0.86** (new best own-work private), but the unseen-input
  majority stays uninferable. eq-aug coverage is the practical ceiling; nothing reaches the cipher's unseen tail.

## Validated this competition
- **Model-soup of comparable+complementary adapters** beats each member (v14+c1+b1 soup → 0.86). The
  reusable lever for the next competition: train N diverse same-base fine-tunes, then soup+SVD-rank-cap.

## Blocked
- None hard-blocking; constrained by deadline (06-15) and 5/day quota.

## Done
- T1 ctx4k (0.67), T2 ctx2k (0.42, negative-sample lesson), T4 v10 rule-CoT (0.59),
  T7 SVD merge (0.82, strong+weak route closed), T8 time-budget guard, T10 v14 replay (0.85),
  T11 v15 cryptarithm synth (0.84), T13 fix held-out eval truncation (512→7680 + time cap).
- Final sprint: b1 0.85, b2 0.84, c1 0.85 (verified solver-CoT), c2 0.83, **soup v14+c1+b1 = 0.86 (best)**.
- T12 local metric + hard-val: built this PR.
- All D1–D9 discussions confirmed (2026-06-12).

## Proposed GitHub issues
> Not created in this task; titles + acceptance below.
- "nemo: post-deadline archival — finalize submissions.md LB/CV + private-LB + final postmortem"
  (acceptance: submissions.md complete; private LB recorded if released; status → archived).
- "nemo: port official metric + min-logprob hard-val set (T12) for reuse" (acceptance: `eval/official_metric.py`
  + `eval/hard_val_ids.json` exist with a local unit test).
