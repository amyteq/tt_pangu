# Equation frontier — post-competition R&D plan

> **⚡ EQ-0 RESULT (2026-06-16) REFRAMES THIS PLAN — read §8 first.** The real `equation` transform is a
> **single GLOBAL deterministic function** (5-char→1–4-char over a 36-symbol alphabet; 6216 inputs, only 35
> collisions), **not** per-prompt secret rules. Per-prompt solving covers ~0% (61.6% of prompts have an
> unseen query symbol — why GPT-5.4 failed on the tail). But **offline we hold 7748 consistent input→output
> pairs**, so the rule is **reverse-engineerable → ~100% ceiling if cracked**. The lever is **crack one global
> rule** (EQ-2), then generate unlimited verified CoT — not a per-prompt solver. Sections below predate EQ-0;
> §8 supersedes the per-prompt framing.

> The `equation` category was the single **unsolved** category: ≤2/16 (T12 min-logprob hard-val) and
> 5/23 (eval/hard_val_ids.json) for *every* adapter incl. the 0.86 soup, and `surgery` couldn't move it.
> Even a dedicated external-teacher CoT run (andy279, 800 equation traces) regressed overall (0.81 —
> dilution). This note is the durable plan to crack it on a future **RTX Pro 6000** GPU session.
> Status: research-backed plan; nothing run yet. Companion task entries in `tasks.md` (§Equation frontier).

## 1. What the task actually is (precise)
A few-shot **transformation-rule induction** problem (≈ ARC-AGI for symbol/number equations):
- **Symbolic/transformation** (`make_cryptarithm_*`, `make_symbol_puzzle`): the prompt gives examples
  `A op B = result` where `op ∈ {+,-,*,/}`; each operator applies a *secret per-operator transformation*
  mapping the two operand strings to a result string (positional permutation, char substitution, reversal,
  interleave, index arithmetic, …). Sometimes an example uses **unseen symbols** → the rule must be
  inferred *structurally*, not memorised. Task: induce each operator's rule from the examples, apply to a query.
- **Numeric deduce/guess** (`make_equation_numeric_*`): induce `f(x)` (linear/quadratic/floor/arithmetic/
  geometric/sequence) from `(x → f(x))` pairs and apply to a query.

**Hard eval constraint:** the submission is a static rank≤32 LoRA; at grading it does **greedy CoT decode
(temp=0, ≤7680 tokens) with NO tool/code execution**. So the rule induction must happen *in the chain of
thought*. (We can use anything — solvers, code, teacher models — at TRAINING time only.)

## 2. Why we missed it (root cause — precise codebase gaps)
- **Tiny rule set.** `lib/nemo_synth_gen.py` `_RULE_REGISTRY` = **8** rules; `lib/nemo_solver.py` `_REWRITES`
  = **9** (`concat_ab/ba`, `rev_*`, `interleave`, `swap_inner`, `left/right_dup`, `rev_concat`). The full
  positional-map space for 2-char operands is **~256** — we covered ~3%. The model learned *those rules*, not
  the **meta-skill of inducing an arbitrary rule** → ~0.4% coverage of real `equation` prompts.
- **Parser drops variable-length operands.** `nemo_solver.py` `_parse_eq_line` hard-codes `len(lhs) != 5`
  (i.e. assumes exactly `A op B` with 2-char operands) → silently skips any 1-/3-char-operand prompt.
- **No numeric solver in the Option-C pipeline** — `SOLVERS["equation"]` has no `f(x)` solver, so real numeric
  equation prompts produced zero verified CoT.
- **Answer-first CoT.** The generator CoT jumps to "the rule is X → apply" without showing candidate
  enumeration/rejection → teaches the answer, not the induction procedure (the OOD-generalization lever, §4).
- High-dose category augmentation **diluted** the clean replay recipe (B8 / single-cat ≠ total): andy279
  (≈17% dose incl. 800 equation) dropped 0.85→0.81. So an equation specialist must be **low-dose and/or
  souped**, not blended at high dose into the main adapter.
- Local hard-val is a **noisy** LB predictor (surgery +1/78 → 0.00 LB delta) — gate on it, but don't trust small deltas.

## 3. Approaches
All are buildable offline; the output is **greedy-CoT-decodable training traces** that teach induce→verify→apply.

**A. Exhaustive positional-map solver + compositional generator (teach the meta-skill).**
Replace the 8/9 fixed rules with the **full positional enumeration**: every output position drawn from
{A0,A1,B0,B1}(+constants) → ~256–625 maps for 2-char operands; generalise to variable-length operands +
2–3-step compositions + per-char bijections. **SOAR-style relabeling**: candidate maps the solver tries that
are consistent with a *subset* of examples become *new* synthetic puzzles (with that map as ground truth) →
free, diverse training data. Validate generalisation on a **held-out rule distribution** (rules absent from training).

**B. Offline solver over REAL train.csv prompts → verified CoT (audit "option G", confirmed by the winners).**
Run the §A solver on real prompts; keep only maps reproducing ALL examples **and** the held-out query answer
(ground truth) → distil into CoT. Concrete fixes first: (i) drop the `len(lhs)!=5` hard-code in `nemo_solver.py`
(support 1-/3-char operands); (ii) add the 256-map enumeration to `_REWRITES`/`_RULE_REGISTRY`. Verified-real-prompt CoT can't poison.

**C. Numeric sub-solver (brute force over the 5 classes) — fills the Option-C gap.**
Add `solve_equation_numeric` to `SOLVERS["equation"]`: try linear → quadratic → arithmetic-diff → geometric-ratio
→ floor-div(k); keep the class reproducing all pairs; distil derivation into CoT. (PySR/LaSR only if real prompts exceed the 5 classes.)

**D. Enumerate→verify→apply CoT format (the OOD-generalization lever).**
Replace answer-first CoT with the structure (from §4): list a *closed, named* candidate set → test each against
**every** example (show predicted vs actual, ✓/✗) → eliminate inconsistent → apply the survivor → `\boxed{}`. Example skeleton:
```
Candidates: [R1 concat_ab, R2 swap_inner, R3 interleave, ...]
R1 on ex1: A='XY',B='ZW' → 'XYZW' vs actual 'XYZW' ✓ ; ex2: ... ✓  → consistent
R2 on ex1: → 'YXZW' vs 'XYZW' ✗  → eliminated
... only R1 consistent → apply to query 'AB','CD' → \boxed{ABCD}
```
Ablate this vs answer-first on the held-out hard-val.

**E. Soup integration + dose control (avoid dilution).**
Train an **equation specialist** LoRA (v14 backbone + the A/B/C data), then **soup** it with v14 (and the
0.86 members) at a tuned weight; gate on T12 hard-val that it lifts `equation` *without* dropping bit/cipher.
Do NOT high-dose-blend into the main adapter (B8).

**F. RLVR / GRPO with a verifiable reward (connects to the existing GRPO task in `tasks.md`).**
Reward = does the model's induced rule reproduce all examples + the correct query answer? This is the
literature's strongest path for rule/puzzle reasoning (Logic-RL family). Heavy (online rollouts); run after A–C give a stable SFT base + the local metric.

## 4. Research-backed techniques (external; cited)
> Competition-specific post-comp writeups were **not yet published** at close — revisit the discussion/GitHub/HF
> for winners' equation handling. The community signal we DO have (below) already points the same way as the lit.

**Competition signal (community, medium trust) — the winning architecture is "brute-force solver → teacher CoT".**
- tonghuikang (Progress-Prize winner) [repo](https://github.com/tonghuikang/nemotron) tracks *rule-found / hypothesis-formed / rule-unknown* per puzzle → an offline solver runs per puzzle, teacher CoT only where the solver succeeds. Mirrors our Option C.
- andy279 [raw-traces](https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge-raw-traces): "deterministic brute-force solvers first discover the hidden rule, then teacher models generate reasoning with the discovered rule prepended." → **the lever is a richer solver, not more LLM.**
- ⚠ **Coverage ceiling:** andy279 reports **399 transformation puzzles that no teacher (incl. GPT-5.4 high-effort) could solve** — a structural hard tail (rules outside any finite positional DSL). Expect a ceiling, not 100%.

**ARC-AGI induction (this task ≈ ARC).**
- **TTT (test-time training) — the dominant ARC-AGI lever — is FORBIDDEN here** (static LoRA, greedy single pass). ARC Prize 2024 report: no static-transduction solution >11%. So our setting is the hardest case for few-shot induction; manage expectations. [ARC Prize 2024](https://arxiv.org/pdf/2412.04604), [2025](https://arxiv.org/html/2601.10904v1)
- **SOAR** (ICML 2025) — alternate LLM program-search with *hindsight relabeling*: failed search programs become correct solutions for synthetic tasks → free diverse training data; distil search traces. [arXiv 2507.14172](https://arxiv.org/abs/2507.14172). **Directly applicable** (Approach A's relabel step).
- Hypothesis-enumerate→verify→apply is the through-line (CodeARC fine-tuning on synthesis traces: +31% rel; ABPR's hypothesis-test-debug; Meta-CoT linearized search traces). [CodeARC 2503.23145](https://arxiv.org/html/2503.23145v2), [Meta-CoT 2501.04682](https://arxiv.org/abs/2501.04682)

**Inductive program synthesis for strings.**
- **Exhaustive positional enumeration is the right offline solver here** (not generic FlashFill): for 2-char operands → 4-char results, every output position draws from {A0,A1,B0,B1}(+constants) → only **~256–625 candidate maps**, enumerable in microseconds/puzzle. Covers every permutation/interleave/swap/reverse/concat variant our 9-rule registry misses. [FlashFill++ POPL'23](https://www.microsoft.com/en-us/research/wp-content/uploads/2022/12/flashfillpp-popl-23-camera-ready.pdf), [DSL-synthesis OOPSLA'25](https://arxiv.org/pdf/2508.16063)
- Content-dependent rules (char-class/value, not just position) fall outside the positional DSL → need lookup-table/char-class extensions (part of the 399 hard tail).

**Symbolic regression (numeric sub-type).** PySR / LaSR (NeurIPS'24, LLM-guided) fit `f(x)` from few points — but **overkill**: our numeric family is a known 5-class set (linear/quadratic/floor/arith/geom) → a brute-force parameter search over those classes suffices and is trivially buildable. [LaSR 2409.09359](https://arxiv.org/abs/2409.09359)

**Teaching induction via CoT distillation (the format lever).**
- **CoT granularity drives OOD generalization** — complete, step-by-step chains beat answer-first; QA-style fails OOD even with 10k+ examples ([Beyond In-Distribution Success, 2502.18273](https://arxiv.org/html/2502.18273)). Our current generator CoT is **answer-first** ("the rule is X → apply") — it teaches the answer, not *how to find it*. **Replace with enumerate→verify-each-against-all→reject→apply** (template in §3-D). Closed, named candidate set to avoid rule hallucination (ILP-LLM, [AAAI'25](https://arxiv.org/html/2408.16779v1)).
- STaR/self-verification underpins the verify step ([STaR](https://arxiv.org/abs/2203.14465); [S2R 2502.12853](https://arxiv.org/pdf/2502.12853)).

**RLVR / GRPO (ties to the existing GRPO task).** Verifiable reward = induced rule reproduces all examples + the query; heavy online rollouts; gate behind EQ-1..3.

## 5. Prioritised tasks (EQ-0 needs no GPU; EQ-1+ need an RTX Pro 6000)
0. **EQ-0 (no GPU, do first): quantify the DSL gap + fix the solver.** Download the public andy279
   transformation set (~10,741 ex), run a 256-map positional solver over it → measure coverage and
   characterise the unsolvable tail (~399 hard puzzles). Fix `lib/nemo_solver.py`: drop the `len(lhs)!=5`
   hard-code, add the 256-map enumeration to `_REWRITES`/`_RULE_REGISTRY`, add `solve_equation_numeric`
   (5-class brute force). **Deliverable: a coverage number that says whether this can move `equation` at all** — gates the GPU spend.
1. **EQ-1 (GPU)** generator + induce→verify→apply CoT (Approaches A + D): compositional rule-DSL + SOAR
   relabeling + the enumerate-verify CoT format; validate on a **held-out rule distribution**.
2. **EQ-2 (GPU)** verified real-prompt CoT (Approaches B + C): run the fixed solver on real prompts (+ numeric
   sub-solver), distil verified traces (optionally reuse the public andy279 hard-cat traces if rules permit).
3. **EQ-3 (GPU)** equation-specialist LoRA → **soup with v14** (Approach E), T12-gate (lift `equation`, hold
   bit/cipher; low dose); run the §D format ablation here.
4. **EQ-4 (GPU, stretch)** RLVR/GRPO with the rule-reproduction verifiable reward on the equation set (Approach F) — after EQ-1..3.

## 6. Success criteria & guardrails
- **Metric:** `equation` accuracy on `eval/hard_val_ids.json` (official extract+verify) — target a clear lift over the soup's 5/23, AND no regression in bit/cipher (T12 gate).
- **Compliance:** keep it a real rank≤32 LoRA (no repack); external-teacher CoT only if rules permit (verify) — Approaches A–C can be fully own-work (our own solver/generator), preferred.
- **Dilution guard:** specialist + soup, low dose; LB keeps the max, so an equation soup can't lower the banked 0.86.
- Evaluate locally first (no quota burn); only submit candidates that beat the soup on hard-val.

## 8. EQ-0 results (2026-06-16) — measured on real train.csv, no GPU
Ran on the **1,555 real `equation` prompts** (train.csv, downloaded locally). Scripts in the worktree analysis (`eq0_analyze.py`, `eq0_solver.py`, `eq0_arith.py`).

**Structure (measured):**
- Input (LHS) is **always 5 chars**; output (RHS) is **1–4 chars** (len 1: 311, 2: 1732, 3: 2115, 4: 2101); **never length-preserving** (0% same-len). Output uses the **same 36-symbol alphabet** as input (incl. symbols absent from the input → substitution, not pure positional selection).
- **NOT operator-based:** only 28/1555 prompts share a constant middle char. The old `A op B` generator/solver modeled the wrong structure → explains the ~0.4% real coverage.
- **It is a GLOBAL near-function:** across all prompts' examples, 6216 distinct LHS → only **35** map to >1 RHS (~0.6%, likely ambiguous/noise); 1554 distinct queries, only 1 with >1 answer. The per-prompt "examples" are just samples of one shared function; the query is another input to it.

**Solver coverage (per-prompt, offline):**
- per-char homomorphism (char→0–2-char string, concat): **0/1555**.
- positional permutation: **6/1555 (0.4%)**.
- **61.6%** of prompts have a query symbol **never shown in their 4 examples** → per-prompt induction is impossible for the majority (matches andy279's "399 unsolvable even by GPT-5.4"). This is a *per-prompt* wall, not a global one.

**The opening:** globally we hold **7748 unique input→output pairs** of one deterministic function — massive supervision. Reverse-engineering it offline → **unlimited verified CoT → ~100% test coverage** (vs the 0.4% the wrong-structure solver got). Simple base-36 value arithmetic is **ruled out** (`in//B^k`, `in%B^k` hit <1%); surface forms mix numeric-looking (`34/44 → 1`) and symbol-cipher (`` `\!*[{ → '"[` ``) cases, so the rule is a non-trivial multi-step transform (candidates: per-position cipher + deletion with a secret digit/symbol permutation; expression-evaluation; lookup over a structured encoding).

**Reframed tasks (supersede §5 for `equation`):**
- **EQ-2′ (highest EV): reverse-engineer the global rule** from the 7748 pairs. Tractable (finite deterministic function, abundant data) but an open decryption puzzle; needs focused iteration. If cracked → generate exhaustive verified CoT for the whole input space.
- **EQ-1′: rebuild the generator to the REAL structure** (5→1–4-char global transform), once the rule (or its family) is known — so the model learns the actual function, not the old `A op B` fiction.
- **Fallback if the rule resists cracking:** SFT directly on the 7748 input→output pairs (memorize + interpolate) — weaker (hidden test = unseen inputs) but a floor.
- **Why it's worth GPU:** `equation` is ~1,555/9,500 ≈ 16% of train; lifting it from ~22% (soup's 5/23 hard-val) toward ~100% could move the overall score by several points — the clearest path above the 0.85 ceiling.

### 8.1 Reverse-engineering log (2026-06-16) — structure cracked, exact rule resists
Probed the 7,748 global pairs (scripts in /tmp: `eq0_{analyze,solver,arith,crack,probe2,digits,modscan}.py`). Ruled OUT, in order:
- per-char homomorphism (0%), positional permutation (0.4%), single-input-position → output[j] (NONE consistent for any L,j).
- order-independence: **order-DEPENDENT** (619/627 anagram groups give different outputs) → not a sum/checksum.
- single-symbol change **cascades through the whole output incl. its length** → carry-propagation signature → **value-based modular arithmetic under a secret symbol cipher**.
- **no anchors:** 0/7748 all-digit pairs, so the 36 glyphs carry no free numeric values (full secret permutation σ).
- global `out = in mod M` / `in // M` under sorted OR ascii orderings: **no fit** (best ≈ noise).

**Conclusion:** the transform is a *single global* function = (secret 36-symbol→value bijection σ) ∘ (value arithmetic with carries, likely multiplicative/affine, possibly two-operand × given the variable output length) ∘ (encode back via σ). Cracking it = a **joint solve of σ + the operation** (a SAT/ILP/constraint project) — tractable in principle (deterministic, 7748 constraints) but a real effort with uncertain payoff (it may be a deliberately strong cipher — it defeated GPT-5.4 per-prompt).

**Fork for the next step:**
- (a) **Heavy cryptanalysis** — joint σ+operation constraint solve (e.g., hypothesise two-operand `A×B`/`A+B`, solve σ by propagation; or SAT). High effort, high payoff if it cracks (→ unlimited verified CoT → ~100%).
- (b) **Model-training pivot (recommended GPU path):** SFT the 30B equation-specialist directly on the global pairs in prompt→answer (+derivation) format; the model may learn the global function better than we can hand-crack it. Soup with v14 (T12-gated, low dose); validate on the **late-submission** quota (100/day). Risk: 7,748 pairs ≈ 0.01% of the 36⁵ input space → may learn only part of a complex function.
- (c) **Fallback:** accept `equation` as a structural hard tail (matches andy279's 399-unsolvable); bank the lessons.

### 8.2 Crack round 2 (2026-06-16, `nemo5` takeover) — class eliminations + division-of-operands lead
Re-derived the 7,695 clean global pairs first-hand (scripts now committed under `analysis/equation/`:
`struct.py`, `probe2.py`, `crack_mod.py`, `factor_g.py` — durable, not `/tmp`). New, sharper results:

- **Carry depth measured:** the last output glyph is **62%** determined by the **last 3** input glyphs
  (vs 22% by last 1, 27% by last 2) → carry propagates ~3 base-36 digits. Last- and first-char identity is
  **16%** (≈5× the 1/33≈3% baseline, so enriched but *not* dominant); digit glyphs `5-9` have the lowest
  identity (~9–12%). Output-as-suffix/prefix of input: **0.6%** (essentially never).
- **Cokernel attack on the residue-preserving class `out ≡ in (mod M)`:** if it held under a base-36 value
  map σ, then `Σ_g σ(g)·c_pair[g] ≡ 0 (mod M)` ⇒ M divides every 36×36 minor of the glyph-weight matrix.
  gcd of 12 random minors = **6³⁶ = 36¹⁸** — a purely *structural* divisor (the count vectors live in a
  6-divisible sublattice), giving only degenerate moduli. `out ≡ in (mod 36)` is *directly falsified*
  (would force 100% last-char identity; observed 16%). ⇒ **the residue-preserving / `in mod M` / `in // D`
  (constant M,D) classes are DEAD** (also confirmed independently by the length argument below).
- **Length-distribution eliminations (no compute):** outputs are `{len4: 2600, len3: 2572, len2: 2134,
  len1: 389}` from *uniformly* 5-digit inputs. A single-char output (5%) needs value <36; a 4-char output
  (34%) needs value ~36⁴. **No constant-modulus `in mod M`, constant-divisor `floor(in/D)`, or fixed-split
  `A±B` can produce both rates** (mod/div with one constant give a narrow length band; `A±B` of ≤3-digit
  parts can't reach 4 digits). All eliminated.
- **The live lead — division/ratio of two embedded operands.** A near-**log-uniform** spread across output
  lengths 1–4 is the signature of a **ratio**: `out = floor(A / B)` or `A mod B` where A,B are positional
  sub-fields of the 5 chars (e.g. A=`in[:4]`, B=`in[4]` as a 0–35 divisor gives the full 1–4 length range:
  B≈35,A small → 1 digit; B=1 → 4 digits). Order-dependent and carry-heavy, both consistent. This refines
  §8.1's "multiplicative/affine" guess to a **division-of-operands** family.
- **Division-of-operands family TESTED → also DEAD** (`analysis/equation/crack_div.py`). For every split
  `A=in[:k]` and op ∈ {`floor(A/B)`, `A mod B`, `floor(B/A)`, `B mod A`}, across 5 σ seeds (incl. the
  untried *digits→0–9* seed) the exact-match rate is ≤ **58/7695 (0.75%, at chance)**; the soft
  interval-penalty hill-climb (4000 swaps) stays flat (final exact 0–9). So the transform is **not** a
  simple two-operand divide/mod with a positional split either.
- **Net after round 2:** eliminated — homomorphism, positional permutation, residue `in mod M`, `floor(in/D)`,
  fixed-split `A±B`, and now `A÷B`/`A mod B`. The transform is a *single global* 5→1-4-glyph function that is
  order-dependent, carries ~3 base-36 digits deep, and has log-uniform output magnitude, but defeats every
  simple closed-form arithmetic tried. **Working conclusion: a deliberately strong cipher** (consistent with
  it defeating GPT-5.4 per-prompt and andy279's 399-unsolvable tail). Remaining crack paths are heavy:
  joint σ+op **SAT/ILP**, multiplicative/modular-exponentiation forms, or an iterated/CA-style cipher — all
  high-effort, low-probability-per-unit-effort. **Recommendation:** treat path (a) hand-crack as a
  diminishing-returns research bet to greenlight explicitly; rely on **EQ-3 (model pivot, running)** as the
  pragmatic empirical test of whether SFT on the 7,748 pairs interpolates the function at all. Do **not**
  spend more GPU on extra specialist variants — they share the same 7,748-pair information ceiling until the
  rule cracks (then full-coverage verified CoT becomes the real win).

### 8.3 Crack round 3 (2026-06-16, `nemo5`) — multiplicative families eliminated → strong-cipher verdict
Per the human "go deep" decision, extended the attack to the families §8.2 hadn't reached:

- **Multiplicative-hash `out = K·in mod M` (cokernel K-sweep, `analysis/equation/crack_mult.py`).** For each
  multiplier K∈1..60, built the K-weighted glyph-difference matrix `K·cin[g]−cout[g]` and took the gcd of its
  36×36 minors. *Every* flagged K's non-{2,3} part is **exactly a power of K's own prime factors** (K=35→35⁵,
  K=37→37⁶, K=49→7¹⁴, K=44→11⁹, …) — a determinant artifact of the `K·a−b` entries, **not** a hidden modulus.
  No K reveals an M independent of K ⇒ the multiplicative-hash family is **refuted for all K∈1..60**.
- **Multiplication / polynomial of operands (`crack_mult2.py`).** Seed-rate scan over `A·B` (all splits),
  `(A·B) mod 36⁴`, the 5-digit product, and sum-of-squares, across 5 σ seeds: best **6/7695** (pure chance).
- **Verdict.** The full simple-algebraic space over base-36 is now eliminated: homomorphism, positional
  permutation, residue `in mod M`, `floor(in/D)`, `A±B`, `A÷B`, `A mod B`, `A·B`, products, `K·in mod M`
  (K≤60). The transform is a **deliberately strong cipher / PRF** — order-dependent, carries ~3 base-36
  digits deep, log-uniform output magnitude — **not recoverable from 7,748 samples by closed-form algebra**
  (consistent with it defeating GPT-5.4 per-prompt and the andy279 399-unsolvable tail). Remaining theoretical
  paths (bit-level SAT against an unknown cipher structure, or recovering the generator's RNG seed) need more
  information about the construction than the samples provide; **EV of further hand-cracking is now low**.
- **Decision:** crack workstream parked at "strong cipher, algebraic space exhausted". The live bet is the
  **EQ-3 specialist grid** — `eq-spec` / `eq-aug` / `eq-hidose` / `eq-aug-hidose` (a 2×2 coverage×dose grid
  across both accounts, all training on the RTX Pro 6000), measured on the late-submission window (100/day).
  If even the best grid point can't lift `equation` on the official metric, it is a confirmed structural hard tail.

### 8.4 EQ-3 empirical result (2026-06-16) — coverage helps, dose hurts; eq-aug = best private 0.86
Trained the full **2×2 (coverage × dose)** grid (real equation prompts woven into the v14 replay backbone) and
measured each on the **official LB** (the authoritative metric):

| kernel | coverage | dose | **LB pub / priv** |
|---|---|---|---|
| **nemo-eq-aug** | **rotated 7,814 real pairs** | **×1** | **0.86 / 0.86** ← best private of the whole campaign |
| nemo-eq-spec | query-only 1,555 | ×1 | 0.85 / 0.85 |
| nemo-eq-hidose | query-only 1,555 | ×3 | 0.84 / 0.84 |
| nemo-eq-aug-hidose | rotated 7,814 real pairs | ×2 | 0.85 / 0.82 |

anchors: v14 0.85/0.84 · soup 0.86/0.85 · identity ~0.47.

- **Coverage is the lever.** `eq-aug` rotates *each in-context example into a query target* → ~5× more genuine
  cipher input→output pairs than query-only (`eq-spec`). That lifts it to **0.86 / 0.86** — ties the soup's
  public 0.86 and **beats** its private 0.85, the best own-work private of the campaign. Mechanism: memorising
  the real pairs captures the **seen-input fraction** of hidden equation queries (EQ-0: ~38% of hidden queries
  have all-seen symbols). A modest but real `equation` gain (+0.01 aggregate; equation ≈ 1/9 of categories).
- **Dose hurts.** Over-weighting the equation data regresses: query-only ×3 (`eq-hidose` 0.84) and coverage ×2
  (`eq-aug-hidose` **priv 0.82**, −0.04 — private drops more than public = overfit signature). **Sweet spot =
  a single epoch over the full real-pair coverage.**
- **⚠️ Methodological lesson — the T12 min-logprob hard-val mispredicts atypical adapters.** `eq-spec` scored
  **0.167** on hard-val but **0.85** on the real LB (gap 0.68, vs ~0.07–0.10 for the hard-tail-robust soup/v14).
  The hard-val over-samples the hardest problems; `eq-spec` answer-shortcuts *under uncertainty* (preflight:
  emitted `\boxed{00010110}` with zero CoT on the single hardest bit problem) but reasons fine on the bulk.
  **→ Trust the LB aggregate; treat hard-val as a hard-tail hint, not a verdict.** (An initial "collapse /
  frontier-closed" read off the 0.167 was premature and was corrected once the LB landed.)
- **Reusable insight:** for a **global-function / lookup-style** hidden category, train on *all available real
  input→output pairs* (rotate every shown example into a supervised target), at **low dose / single epoch**.
  This beats query-only SFT and beats higher-dose.
- **eq-aug does NOT soup (tested).** `soup_v2 = SVD(0.86-soup ×0.6 + eq-aug ×0.4)` → **0.85 / 0.85**, below both
  parents. The model-soup lever requires **hard-tail-robust** members (original v14+c1+b1 all ≥0.76 hard-val);
  blending the hard-tail-*weak* eq-aug (0.194) imports its shortcutting and averages out its equation coverage.
  **The coverage gain survives only standalone, not in a merge** → eq-aug 0.86/0.86 is the ceiling.

**Status: `equation` is *partially* addressable, not solved.** Coverage-memorisation (eq-aug) captures the
seen-input fraction for a real **+0.01 → 0.86 / 0.86** (new best own-work private), but the unseen-input
majority remains uninferable (EQ-2′ strong cipher: no closed-form rule, no derivable CoT). The frontier is thus
**bounded**, not open: this coverage lever is the practical ceiling; nothing reaches the cipher's unseen tail.
