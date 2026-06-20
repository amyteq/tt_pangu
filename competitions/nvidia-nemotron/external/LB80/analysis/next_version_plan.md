# Next-version plan — borrowing from LB80 (post-Saturday GPU reset)

> Updated 2026-06-17 from the actual writeup (`temp/LB80.pdf`). Analysis/planning only (no GPU/submit/push in
> this task). The earlier "dense per-bit GRPO" plan was based on the wrong author and is **dropped** — mspawar
> proves standard RL (STaR/GRPO) gets **zero signal** here (binary failure). The corrected plan has two
> independent parts. Borrows from an untrusted competitor writeup — verify before trusting; mspawar did **not**
> beat 0.86 with any of this, so set expectations: these target *equation* specifically + are research bets.

> **✅ EXECUTED 2026-06-20 (late window). RESULT: v17-discovery = public 0.840 / private 0.848 — pub −0.01 / priv +0.008 vs v14 (0.85/0.84); below 0.86. Hypothesis NOT supported (equation stays bounded).** Part A only; **v17-dpo DEFERRED** (needs external ~95.6GB sm_90+ GPU, #83 — not in our infra; mspawar rated it lower-EV anyway).
>
> **Genuine breakthrough (independent of LB): cracked the equation cipher.** It is NOT the EQ-0 "single global function" — each problem is a set of **per-operator digit-string transformation rules** (line = `A1A2 <op> B1B2 = R`; R = operand-reverse × {add/sub/rsub/mul/absdiff} × ±1 × result-reverse, or ordered concat; the op symbol can act as an output-side sign marker). The kernel's old `A1A2 OP B1B2` 2-digit-arithmetic model cracked <1%; the new solver yields **180 verified forward-executable discovery examples** on the **plaintext-digit subset (~18%)**. **Why no LB lift:** the ~82% **glyph-ciphered** queries need a *joint* cipher+op crack (still open), so plaintext-only rule-discovery doesn't transfer. **The team already has the superior cracker** — `versions/lb1-v1/rules24.py` (LB1's 24-rule inventory, **95% numeric-deduce**, branch `exp/nemo-postlb1-v1`); a **v17.1 should use rules24** instead of my hand-crack (I rediscovered a weaker subset — process note in memory). See `submissions.md` §LB25/LB80/LB92.

## Version name
**v17-discovery** (equation) + **v17-dpo** (RL path) — two separable post-Saturday experiments.

---
## Part A — `v17-discovery`: forward-executable cipher-discovery CoT for equation (highest EV, novel)

### Hypothesis
Our `equation` cap (eq-aug 0.86 = coverage-memorisation) is **discovery leakage**: we taught *verify* (reproduce
seen pairs), not *discover* (run the per-problem cipher search). Per LB80, the structure is **`A1A2 OP B1B2`**
(two 2-char operands + 1-char operator, per-problem symbol→digit bijection) and is **offline-crackable at
~97.6%** via answer-guided search. A **forward-executable, prompt-derivable** CoT that *shows the discovery*
(not the answer) should teach the model to actually solve held-out equation problems — the lever neither our
eq-aug nor mspawar's answer-guided CoT achieved (top LB 0.90 implies it's possible).

### Prerequisite (CPU, free — feeds back to EQ-2′ / PR #113)
1. **Re-model `equation` as `A1A2 OP B1B2`** (not a single global 5-char function — our EQ-0 was mis-framed).
2. **Build an answer-guided solver** (per-problem digit-symbol permutation → decode the answer → find op → verify
   all examples). Target ~97.6% offline coverage on train; flag the >10-distinct-symbol unsolvables.
3. **Write a FORWARD-executable CoT**: enumerate operator/mapping hypotheses, test each against the example
   equations, eliminate, apply the survivor to the query — *without* referencing the ground-truth answer. Verify
   every trace is **internally consistent** (stated mapping reproduces the boxed answer) — the audit mspawar
   showed 93–97% of answer-guided traces fail.

### Data / format / config
- Equation discovery-CoT woven into the v14 backbone at **low dose ≤15%** (dilution guard: b2/v15/c2/eq-symbolic
  all regressed). Eval-faithful prompt; response-only mask. **Length budget is the key risk** — the full search
  CoT may exceed 8192 tokens; compress the search (prune to the consistent operator family, ≤ a few hundred tokens).
- v14 recipe otherwise unchanged (seq8192, all-linear LoRA r32 incl. lm_head, **exclude gate_proj**, LR 3.5e-4, 2 ep).

### Validation / gate
- T12 hard-val per category; **require `equation` ↑ on hard-val AND no regression on bit/cipher/easy**; total ≥ 0.764.
- **Internal-consistency audit** of generated traces before training (the discovery-leakage check).
- Submit only if hard-val gate passes; **late-window submit needs explicit human approval**.

---
## Part B — `v17-dpo`: DPO with an external oracle (the correct RL shape; lower EV)

### Hypothesis
SFT plateaus and STaR/GRPO get **zero signal** (binary failure: 0/8 or 8/8, no boundary problems → no reward
variance). DPO sidesteps this by using an **external oracle** as *chosen*: pairs = (solver-CoT chosen) vs
(model's **greedy temp=0** failure rejected) — capturing the exact eval-time error. May lift bit/cipher.

### Design (from mspawar; verify before trusting)
- **Dual-temp generation:** greedy `temp=0,N=1` → rejected (eval-time failure); `temp=0.7,N=8` → diversity.
- **Pairs:** outliers → chosen = solver CoT, rejected = greedy-wrong; ~2,000–2,500 pairs; skip inliers.
- **Loss:** length-normalized DPO margin + **SFT-mixing on easy cats** (cipher/gravity/numeral/unit, forgetting
  guard); **reference = same base, LoRA disabled** (toggle → saves ~60 GB).
- Init from our v14 / 0.86 soup.

### Validation / gate / expectations
- Same T12 gate. **Expectation: may not beat 0.86** (mspawar's V12/V13 DPO plateaued 0.84–0.86). Treat as a
  research bet, not a likely win. Submit only on a hard-val improvement + human approval.

---
## Cross-cutting
- **Mamba-2 merge ablation** (cheap): mspawar claims Model Soup fails on hybrid SSM, yet our SVD-LoRA-delta soup
  gained +0.01. Run a controlled LoRA-delta-SVD-merge vs full-weight-average ablation, T12-gated, before
  trusting either claim.
- Keep the **selection hedge** discipline (best + a diverse hedge) — the lever that actually moved mspawar's rank.

## Risks
- **Length budget** (Part A): forward discovery CoT may not fit 8192 tokens → the central risk; compress aggressively.
- **Dilution**: equation/DPO data over-weighting regresses (≤15% dose + T12 gate).
- **RL cost/instability** (Part B): 30B online generation needs ~95.6 GB sm_90+ GPU (external, #83); DPO may not
  beat 0.86. Do the cheap CPU prerequisite (Part A solver) and the merge ablation **first**.
- **Equation may still be bounded**: even a perfect discovery CoT might not fit in the token budget; mspawar
  didn't crack it on the LB despite the offline solver.

## GPU estimate
- Part A prerequisite (solver + CoT build + consistency audit): **CPU, ~0 GPU**. Part A training: **1 RTX PRO 6000
  session** (~6–7 h). Part B DPO: **external GPU (#83), several sessions** (vLLM-gen + HF-train separate processes).

## Implementation checklist
- [x] (CPU) re-model equation — found it's **per-operator digit-string rules** (NOT `A1A2 OP B1B2` arithmetic, which gave <1%); answer-guided solver = **67% of the plaintext-digit subset (180 rows)**. ⚠️ `rules24.py` (lb1-v1, branch `exp/nemo-postlb1-v1`) already does **95% numeric-deduce** — use it for v17.1.
- [x] (CPU) forward-executable discovery CoT; internal-consistency audit — 180 verified, 0 dropped as inconsistent
- [x] v17-discovery kernel: discovery-CoT dose 0.15 on v14 backbone — ran (`firefly2006/nemo-v17-discovery` v1); **LB 0.840/0.848 < v14, equation↑ NOT achieved** (plaintext-only doesn't transfer to ciphered queries)
- [ ] ~~Mamba-2 merge ablation~~ — not run (out of scope of the 3-goal sprint; backlog)
- [ ] ~~v17-dpo~~ — **DEFERRED: needs external sm_90+ GPU (#83), not in our infra; core fns were NotImplementedError research stubs**
- [ ] ~~gate→approval→submit~~ — submitted to the late window directly (human-authorized goal); gate not met (no equation↑), so it stays a research datapoint, not a promotion
