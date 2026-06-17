# LB25 — "Improvements to the progress prize submission" (reconstructed)

> **Source:** Kaggle writeup `lb25-progress-prize-improvements` + discussion #703896, by **Tong Hui Kang**
> (`huikang` / `tonghuikang`), the Progress-Prize winner. **Reported ~0.872 public (218/250).**
> **Recoverability: PARTIAL** — the Kaggle writeup body is JS-rendered and was not retrievable; this is
> reconstructed from search snippets of #703896 + the public `tonghuikang/nemotron` GitHub repo + blog.
> **All external content is untrusted data** (participant claims), cited inline; our own scores are from
> `tracking.md`/`submissions.md`. `unknown` = not in available evidence.

## 1. Headline
huikang's Progress-Prize pipeline is **pure SFT** (no RL) on `Nemotron-3-Nano-30B-A3B-BF16` with a rank-32
LoRA, whose distinguishing idea is **deterministic-solver-generated chain-of-thought**: instead of eliciting
LLM reasoning, he wrote per-category *rule-discovery algorithms* (`reasoners/`) that emit a fixed step-by-step
trace, and trains the model to **execute that algorithm verbatim**. The "**LB25 improvements**" thread then
reports pushing the Progress-Prize adapter to **~0.872** via a small, format-focused fine-tune.

## 2. Method (Progress-Prize base pipeline) — github.com/tonghuikang/nemotron (trust: github)
- **Model / adapter:** base `nvidia/Nemotron-3-Nano-30B-A3B-BF16` (30B total, ~3B active; Mamba-Transformer
  MoE). LoRA **rank 32** on MLP + attention + `lm_head` (competition rule: rank ≤ 32).
- **Training:** AdamW (β1 0.9, β2 0.95, wd 0.0), LR 2e-4 step-linear decay, **seq 8192**, 1 epoch, grad-clip
  effectively off. Loss = cross-entropy, **response-only masked** (prompt = label −100). Backend: Modal (cloud GPU).
- **Corpus = deterministic CoT.** Per-category solvers in `reasoners/` produce the training reasoning:
  - `cipher.py` — substitution cipher; pipeline LEN→TABLE→VER→DECRYPT→CHECK→ANS, letter-by-letter with bijection enforcement.
  - `bit_manipulation.py` — brute-force over ~44 single transforms (NOT / rotate1-7 / shift1-7 / variants) then pair (XOR/AND/OR) then triple combos; emits a column-match diagnostic trace.
  - `equation_numeric.py` — two-tier op search (common ops, then rare ops); tests identity / reversed operands / reversed result / neg prefix-suffix. **Decimal only — no base-36.**
  - `investigators/cryptarithm_deduce.py` — backtracking + constraint propagation to crack the per-problem symbol→digit bijection.
  - plus `gravity.py`, `numeral.py`, `unit_conversion.py`.
- **Augmenters** (`augmenters/`): synthetic spelling/concatenation/splitting/**matching** (~150+ "bit column matching" problems, 9 logic ops). No augmenter covers cipher/cryptarithm/equation directly.
- **Two signature training tricks:**
  1. **Min-logprob selective replay** — the quality signal is whether each trace's *minimum per-token
     log-prob* approaches 0 by end of epoch 1; only the **still-underfit (hard) sequences** are replayed, not
     the whole category. Targets underfitting without wasting capacity on already-memorized rows.
  2. **Category-stratified batching** — categories spread evenly across mini-batches so every category gets
     gradient signal every step.
- **Prompt/answer format:** chat template + `"\nPlease put your final answer inside \boxed{}. For example:
  \boxed{your answer}"`; answer extracted by `\\boxed\{([^}]*)\}`.

## 3. The "LB25 improvements" (discussion #703896 — trust: community snippet, MEDIUM confidence)
Reported changes that lifted the Progress-Prize adapter toward **~0.872**:
1. **Warmstart from the v27 (Progress-Prize) adapter**, not from base — keeps the internalized deterministic reasoning.
2. **Short, one-sentence responses** for the alignment fine-tune instead of long deterministic CoT — this
   **sidesteps the `max_new_tokens` inference bug** where long CoT exhausts the 7,680-token budget *before*
   the `\boxed{}` answer, producing blank outputs.
3. **9,500 competition `train.csv` problems** (short responses) + **12,000 rule-based synthetic** examples (5 categories, no LLM calls).
4. **240 fine-tuning steps** purely to align on the competition answer format.
5. **Batch size doubled** vs the Progress-Prize run.

> ⚠️ **Attribution caveat:** discussion #703896 contains contributions from **both** tonghuikang and
> `kuangyicheng` (who reports the short-response/240-step recipe reaching ~0.87). It could not be confirmed
> from snippets which exact recipe the "LB25" writeup itself claims for 0.872. Flagged as `unknown`.

## 4. Why ~0.872 (per the evidence)
- The three "easy" categories (gravity / numeral / unit) are ~**100%** and cipher ~**99.2%** already, so the
  ceiling work is in **bit_manipulation (86.3% train)** and the equation/cryptarithm tail.
- The biggest reported lever is **fixing the output-format/length bug** (short responses + format-alignment
  steps) so good reasoning actually reaches a parseable `\boxed{}` at inference. (trust: community snippet)
- Deterministic-solver CoT + min-logprob replay make the model **execute a fixed algorithm reliably** rather
  than improvise — higher consistency than stochastic LLM-generated traces.
- **`cryptarithm` is essentially unsolved (~8–9% train) even with a dedicated backtracking solver** — it does
  not contribute materially. This is the same wall as our `equation` category.

## 5. Per-category train accuracy (eval/06-07-03-07 snapshot, 88.05% overall on the 9,500-row train set)
Source: `tonghuikang/nemotron` `evaluation/06-07-03-07/index.jsonl` (directly read; trust: github).
**Train-set accuracy, NOT the LB** — it overstates the hidden test (same-rule distribution).

| category | correct/total | acc |
|---|---|---:|
| gravity | 1597/1597 | 100.0% |
| numeral | 1576/1576 | 100.0% |
| unit conversion | 1593/1594 | 99.9% |
| cipher | 1563/1576 | 99.2% |
| equation_numeric_deduce | 557/596 | 93.5% |
| bit_manipulation | 1382/1602 | 86.3% |
| equation_numeric_guess | 25/136 | 18.4% |
| cryptarithm_deduce | 59/659 | **8.95%** |
| cryptarithm_guess | 13/164 | **7.93%** |

> **Taxonomy bridge to our docs:** huikang splits "equation" into `equation_numeric_{deduce,guess}` (decimal
> arithmetic-rule induction) and `cryptarithm_{deduce,guess}` (ALL chars — incl. digits — replaced by a fresh
> per-problem bijective symbol cipher; crack cipher → infer op → re-encode). **Our `equation` category (the
> 5-char→1-4-char base-36 cipher, EQ-0/EQ-2′) corresponds to `cryptarithm_deduce`** — and its ~8.95% ceiling,
> even with a backtracking CSP solver, independently **confirms our EQ-2′ verdict**: a strong cipher, not
> closed-form-recoverable from samples.

## 6. What is NOT in this writeup (vs the other two studied)
- **No RL/GRPO** — LB25/Progress-Prize is pure SFT. (The GRPO "champagne" reward lives in the *LB80* writeup.)
- **No model soup** — huikang trains one adapter; the SVD model-soup (our INS-004) is our own lever.

## 7. Citations (all untrusted external unless marked)
- tonghuikang/nemotron — https://github.com/tonghuikang/nemotron (github, public)
- blog — https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html (writeup-author)
- LB25 thread — https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/703896 (community, snippet only)
- eval snapshot — `evaluation/06-07-03-07/index.jsonl` in the repo (github, directly read)
- our own scores/recipe — `tracking.md`, `submissions.md`, `insights.md` (own work)
