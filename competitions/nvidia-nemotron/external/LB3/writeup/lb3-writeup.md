# 3rd Place Solution — NVIDIA Nemotron Model Reasoning Challenge

> **Source (depth 0):** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/3rd-place-solution>
> **Local fallback:** `temp/LB3.pdf` (17 pages). **Conversion:** `pdftotext -layout` → cleaned to Markdown (tables/code blocks repaired). Raw at `writeup/raw/lb3-pdftotext-layout.txt`.
> **Author:** YS-L (liauys). **Solution Writeup · 3rd place · Jun 19, 2026.** **Final: Private LB 0.900; local validation 90.46%.**
> Treat all quoted external content as **untrusted data**, not instructions.

---

## Overview

My solution builds on top of the excellent early work and ideas from **llkh0a, huikang, kemshim, youkinasa** and others, with the following improvements:

- Rewritten **numeric solver** that is more minimal and with a better guessing logic.
- **Hui Kang-style bit manipulation trace** compacted with **hex notation** and extended with **majority operation search**.
- **Data augmentation** for all problem types except gravity, unit conversion and numeral.
- **Constraint satisfaction problem / CSP-like algorithm** that solves overall **24.2% of cryptarithm** problems within token budget (27.8% of deduce cases, 9.8% of guess cases) using multiplication patterns and backtracking search.
- **Two-stage training** approach that **decouples memorization and execution** to help the model learn the cryptarithm trace better.
- **Local validation strategy** that turns out to track the **private** test set well.

## Solver and trace design

### Gravity, Unit conversion, Numeral
Trivial categories the model does very well with minimal training. **Reused traces from llkh0a's notebook directly.**

### Cipher
Simplified the trace from the same notebook and removed the elaborate missing-letter analysis. Simply **adding more augmented samples** is sufficient to teach the model to fill in missing letters (small vocab).

### Bit manipulation
Modified the Hui Kang-style trace with three changes:

**1. Hex-notation with tail bits** to more compactly represent output bit columns.

Before:
```
OR-NOT
01 1110001110 6
12 1111110111 9
23 1111101011 8
34 1010011111 7
```
After:
```
OR-NOT
01 E3|10 6
12 FD|11 9
23 FA|11 8
34 A7|11 7
```
(Encoding the last two bits as a hex char with left/right padding confused the model and hurt the 9-/10-example cases — so the **tail bits are kept as-is** after the `|`.) This brings about **25% reduction in token usage**, which allows the second change.

**2. Search over the majority operation (MAJ)** to fit under token budget (enabled by the token savings).

**3. Rule-ordering change** so OR-NOT candidates are tried before plain OR and XOR:
- Default ordering: `Identity, NOT, Constant, AND, OR, XOR, AND-NOT, OR-NOT, XOR-NOT, MAJ`
- New ordering: `Identity, NOT, Constant, AND, OR-NOT, OR, XOR, AND-NOT, XOR-NOT, MAJ`

which empirically improves the solve rate slightly (**+0.6%**).

### Numeric equation
Rewrote a solver from scratch, adding operations one by one to identify exactly those needed. The set:
```
[ "a+b", "a-b", "abs(a-b)", "negated absolute diff", "b-a",
  "a*b", "a+b+1", "a+b-1", "a*b+1", "a*b-1",
  "concat(a,b)", "concat(b,a)", "max(a,b) mod min(a,b)" ]
```
This is the exact set: if the solver were allowed to "peek" at the answer (include the question as an example), **all problems solve unambiguously** with just these. Without peeking, multiple ops sometimes fit all examples — **conflicts occur only among subtraction-type ops** (`['a-b','negated absolute diff']`, `['abs(a-b)','a-b']`, …). No disambiguation beats random guess, so a **deterministic ordering** (prefer `a-b` over negated absolute diff) maximizes train solve rate.

Important: the **"simple" or "reverse" form must be applied globally** across all equations in a problem, not independently per equation.

**Family structure.** A co-occurrence table of true operations within problems shows organized patches of zeros: `a*b` never appears with `a*b±1`; `a+b` never with `a+b±1`, etc. → the data generator samples **broad operation "families"** and picks **one op per family** per problem. This improves the guessing logic when the query operator is unknown: **the optimal guess is an operation in a family not yet mapped** by the existing examples.

Solver:
1. Try two structures in order: **simple** `f(a,b)=fmt(op(a,b))`, then **reverse** `f(a,b)=fmt(rev(op(rev(a),rev(b))))`.
2. For each structure, for each operator symbol, test candidate ops in the order above; take the first that fits every example. Exit early if any operator can't be explained (wrong structure).
3. Prefer **simple over reverse** if both fully explain all operators.
4. If the query operator is unseen, guess priority `a-b, a+b, a*b`, choosing the **unseen operation type**.

Train solve-rate ceiling: **deduce 559/596 = 93.79%**, **guess 53/136 = 38.97%**, **overall 612/732 = 83.61%**.

### Cryptarithm

Strategy inspired by the **multiplication-pattern-lookup** ideas from **kemshim** and **youkinasa**: use multiplication examples to propagate constraints and provide a good starting point for a backtracking solver with most digits already solved.

**Overall sketch:**
1. Identify **MUL examples** (they constrain more symbols than other ops).
2. Each MUL example emits, from the pattern-lookup table: possible digits per symbol, and possible candidate mappings.
3. With multiple MUL examples, compute their **intersection** — "join" candidate mappings from different MUL examples; two (up to four) mappings either **merge** (no conflict) or are **rejected** (conflict).
4. The intersection yields a much more constrained set — often exactly 1. Each merged candidate mapping is an **anchor mapping**.
5. For each anchor mapping, launch a **backtracking symbolic solver** for the remaining unknowns over the free digits:
   - At each step, choose the example with the **least unknowns** and solve it.
   - Non-negative answers: try `a+b, a+b+1, a+b-1, a-b, abs(a-b)`.
   - Negative answers: try `a-b, -abs(a-b), b-a`.
   - Backtrack when no valid solution; stop early once all unknowns are solved.

Repeated for each `(structure, multiplication type)` pair — structure ∈ {simple, reverse}, mul type ∈ {`a*b`, `a*b+1`, `a*b-1`} — greedily trying **reverse first, then simple**, stopping at the first solution satisfying all examples. The symbolic solver supports **up to 2 unknowns per equation** (sufficient because the anchor-finding phase does most of the heavy lifting).

**Example trace** (problem `|"-!{ = ?]` / `{!*{| = ]!]]` / `"!*\[ = \[]/` / `/:-{: = |!"`, query `|/*/!`): equations 2 and 3 are MUL (length-4 answers).

- `<RECALL_DOMAINS>` emits possible digits per symbol from the lookup table (e.g. `sig=ab-ac-dbdd type=R*` → a∈{2,9}, b∈{3,6}, …). `R*` = `a*b` in reverse form.
- The intersection section combines domains across MUL examples (symbol `!`: E2={3,6} ∩ E3={2..9} = {3,6}).
- `<RECALL_ROWS>` enumerates candidate mappings per signature; rows are filtered by the intersected domains; passing rows are spelled out explicitly as `E2_1, E2_2, E3_1, …` (the explicit spelling gives the model context to perform the merge/conflict detection next).
- **Join** step: `E2_1xE3_1NS【!】63` = conflict (symbol `!` → 6 vs 3); `E2_1xE3_2Y=A1` = mergeable, anchor `A1` with merged map.
- **Backtracking solver** from anchor `A1` (`Q`=pick next equation, `C`=commit assumption, `S`=symbolic steps, `N`=conflict/backtrack, `Y`=valid) resolves the remaining symbols.
- **Query computation**: `f(75,56) -rev-> f(57,65) = 57*65 = 3705 -rev-> 5073` → re-encrypt → answer.

**More implementation details:**
- Candidate mapping enumeration capped at **48 per signature**; max **8 anchor mappings** (more doesn't help under budget).
- Length-3 answers sharing the MUL operator are treated as MUL examples too.
- Single unmapped query symbol + single unmapped digit → last step establishes the mapping.
- Unknown query operator → same family-based guessing as numeric equations.
- `<RECALL_DOMAINS>` / `<RECALL_ROWS>` tags mark sections that must be **derived purely from memory** (see Modeling).

**Solve rate within budget** (local dataset = original cryptarithm + numeric equations encrypted as cryptarithm):
- cryptarithm_deduce **183/659 = 27.8%**, cryptarithm_guess **16/164 = 9.8%**, **combined 199/823 = 24.2%**.

## Data augmentation and overall mix

- **Cipher** — 77 unique words, 4 sentence structures `(subj,verb,obj)`, `(subj,verb,the,adj,obj)`, `(subj,verb,prep,prep_object)`, `(the,adj,subj,verb)`. Generated **3K** augmented samples (uniform sampling).
- **Bit** — two methods: **swap-augment** (change input values in an existing problem, apply the transform, reshuffle/select a new query) and **formula-augment** (build new problems from two-/three-ops/majority/choice). **3K swap + 3K formula**, each duplicated twice.
- **Numeric** — sample an original problem (from original numeric + decrypted cryptarithm pool), change operands and operator symbols, recompute. (Re-using original problems rather than generating from scratch avoids creating/removing hidden artifacts vs the official generator.) Final = all original numeric + decrypted cryptarithm + **3K** augmented.
- **Cryptarithm** — create a new numeric problem (as above), then apply a cipher encryption → a new cryptarithm. **48K** augmented (4K of `concat` type, answerable directly without pattern matching). The category needing the most augmentation.

**Overall training mix** (after a 10% validation split):

| Problem category | Samples | Token count | % of dataset |
|---|---|---|---|
| cryptarithm | 43,157 | 199,165,000 | 59.63% |
| bit_manipulation | 13,998 | 83,769,094 | 19.34% |
| cipher | 4,418 | 5,896,685 | 6.10% |
| numeric | 4,076 | 6,168,838 | 5.63% |
| cryptarithm_pattern_drill | 3,000 | 2,164,784 | 4.14% |
| gravity | 1,437 | 1,195,592 | 1.99% |
| unit_conversion | 1,434 | 700,982 | 1.98% |
| numeral | 857 | 313,229 | 1.18% |
| **Total** | **72,377** | **299,374,204** | **100.00%** |

## Modeling

Used **Hui Kang's training loop with cut cross entropy (CCE)** — reduces memory, allows micro-batch 4, better GPU utilization. Findings: **disabling MoE tie weights** gives better results; **too-large effective batch size under-trains** the model (started at 16, down to 8, settled on **4**).

Final training parameters:

| Parameter | Value |
|---|---|
| Epochs | 1 |
| Batch size | 4 |
| Gradient accumulation | 1 |
| Effective batch size | 4 |
| Learning rate | 2e-4 |
| LR schedule | linear decay |
| Max sequence length | 8192 |
| Max grad norm | 10 |
| Seed | 42 |
| LoRA rank | 32 |
| LoRA alpha | 32 |
| LoRA dropout | 0.0 |
| LoRA dtype | fp32 |
| LoRA target modules | q_proj, k_proj, v_proj, o_proj, up_proj, down_proj, in_proj, out_proj, lm_head |
| Manual LM-head LoRA | 1 |
| MoE tie weights | 0 |

### Two-stage training

Cryptarithm trace success at inference hinges on (a) **correct recall** of possible digits/candidate mappings for any signature + mul type, and (b) **correct execution** of the algorithm assuming recall is correct. A **two-stage** approach works better than one run.

**Stage 1 — learning to memorize.** Train the model to recall, given a signature, the domains and rows. E.g. for `<RECALL_DOMAINS> sig=aa-ba-acde type=R-` complete with `a 37 / b 48 / c 59 / d 26 / e 15`; for `<RECALL_ROWS> sig=aa-ba-acde type=R-` complete with the rows `38521 / 74965`. The stage-1 dataset is **pure "drill" completion requests** covering all multiplication signatures. To speed convergence, each sample **packs 16 signature requests**; the opening tags and request signatures are **masked** from loss. Stage-1: LR 2e-4, effective batch size 8, ~27.6K steps. **Stage-1 memorization quality on 1000 random signatures: overall exact 97.1%, domain exact 98.4%, row-ordered exact 95.9%, row-set recall 98.0%, row-set precision 97.9%.**

**Stage 2 — learning to solve.** The stage-1 LoRA adapter becomes the **initial adapter** for stage 2, which trains on the actual trace data; the model focuses on **execution** (composing memorized patterns). A small number of drill samples (**3K**) are injected to retain memory.

**Sample efficiency** (12K cryptarithm samples; ~11 non-concat cryptarithm problems solvable under budget in the held-out set): **direct training solved 0; two-stage solved 7.** Matching that with direct training needs **36K** samples. So the cryptarithm trace is ~learned (near target solve rate) with **40K+ samples**. Stage-1 training does **not** impair downstream learning, and is **modular** (solver/format changes reuse the same stage-1 model).

**Training durations:**

| Model | # examples | Training input tokens | Steps | Duration |
|---|---|---|---|---|
| First stage | 44,136 | 159,305,950 | 27,585 | 25.2 hr |
| Second stage | 72,377 | 299,374,204 | 18,095 | 32.7 hr |

## Validation strategy

Hold out **~10% stratified by category** (954 validation rows). Exclude validation rows from training; **also exclude augmented samples derived from validation originals** (reduce leakage).

The validation strategy **tracks the private test scores well — but NOT the public LB.** "The dreadful **wall of 0.86**" is clearly visible on public; one **0.85 public** submission scored **0.90 private**. Private LB kept improving in line with validation, "but there was no way of knowing." A 0.87 submission at the right time provided motivation to keep pushing.

**Additional metrics:**
- **Perfect trace rate** — whether the model emits the expected trace exactly (a leading indicator; the model can be right by luck while the trace is wrong). Target >85% bit, >95% cipher/numeric. Expected low for gravity/unit (float arithmetic) — fine, since accuracy is high anyway.
- **Cryptarithm pattern-matching metrics** — how well the model recalls memorized domains/rows, and how self-consistent the trace is assuming correct recall.

**Iterating with single-category training.** When testing a new solver/format, train+validate on just the target category to isolate effects; treat standalone validation as a **ceiling** (a slight drop usually appears when combined with all categories). Promote a variant only if standalone validation improves; if the all-categories run drops too much, add more augmented samples.

## Overall scores

Final model: **Private LB 0.900.** Local validation:

| Category | Actual solve | Ideal solve | Total | Accuracy |
|---|---|---|---|---|
| Overall | 863 | 864 | 954 | **90.46%** |
| bit_manipulation | 144 | 144 | 161 | 89.44% |
| cipher | 156 | 158 | 158 | 98.73% |
| cryptarithm_deduce | 20 | 21 | 66 | 30.30% |
| cryptarithm_guess | 1 | 1 | 17 | 5.88% |
| equation_numeric_deduce | 56 | 56 | 60 | 93.33% |
| equation_numeric_guess | 8 | 6 | 14 | 57.14% |
| gravity | 160 | 160 | 160 | 100.00% |
| numeral | 158 | 158 | 158 | 100.00% |
| unit_conversion | 160 | 160 | 160 | 100.00% |

## Acknowledgements

- **llkh0a's notebook** — got started following this work; the final model still uses its traces for some categories.
- **huikang's solution and training notebook** — the open-progress-prize-winning solution; the manual training loop is "amazing and not talked about enough."
- **kemshim's discussion** — ideas for a symbolic equation solver for cryptarithm.
- **youkinasa's discussion** — the cryptarithm strategy that intersects constraints from multiple examples.

## Closing / Author / Citation

5th gold medal after a decade away; good placement on an LLM competition as a historically "xgboost / tabular ML" person.

> **Author:** YS-L (liauys).
> YS-L. *3rd Place Solution.* <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/3rd-place-solution>. 2026. Kaggle.
