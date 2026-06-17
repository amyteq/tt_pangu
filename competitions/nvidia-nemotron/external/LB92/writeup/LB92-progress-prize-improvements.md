# LB92 — "92th PLACE SOLUTION" (from the writeup itself)

> **Source:** the Kaggle writeup by a **team — Yoshinari Kawashima (`yoshinarikawashima`) + MedudentYamatai
> (`taikiyamamura`)**, **read directly from `temp/LB92.pdf`** (a render of the full page; Jun 16 2026; DOI
> `10.34740/kaggle/w/88245`). **Recoverability: FULL** — supersedes the earlier ecosystem-only reconstruction
> (author/score/method were `unknown`; now confirmed). External content = untrusted data (competitor claims),
> cited inline; our scores from `tracking.md`.

## 0. Headline
A **clean, data-engineering-first** solution that explicitly does **not** try to solve the hard categories — it
aims to **faithfully reproduce the public reasoner's 87.8% solve-rate** and close the gap to the LB via **more,
statistics-matched synthetic data** + two stability tricks. Built on public notebooks ("End-to-end finetuning
for LB 0.85", "Training with Unsloth to Achieve 0.85 LB", "Tinker submission notebook"); the **reasoner is Tong
Hui Kang's** (Open Progress Prize) with **almost no changes** (same root as LB25/LB80).

## 1. The three pillars
**(1) Almost no changes to the reasoner (CoT generation logic).** The deterministic reasoner solves **87.8%**
of train (8341/9500), but the best public notebook scores only **0.86**. Thesis: *the model is failing to
reproduce problems the reasoner already solves* → **goal = avoid losing already-solvable problems, not solve
harder ones.** Per-category reasoner accuracy (their table; = huikang's):

| category | found/total | acc |
|---|---|---:|
| cipher | 1576/1576 | 100.0% |
| gravity | 1597/1597 | 100.0% |
| numeral | 1576/1576 | 100.0% |
| unit_conversion | 1594/1594 | 100.0% |
| equation_numeric_deduce | 541/596 | 90.8% |
| bit_manipulation | 1364/1602 | 85.1% |
| equation_numeric_guess | 21/136 | 15.4% |
| cryptarithm_deduce | 59/659 | **9.0%** |
| cryptarithm_guess | 13/164 | **7.9%** |
| **TOTAL** | **8341/9500** | **87.8%** |

**(2) New generator + statistics-matched synthetic data (the signature lever).** Hypothesis: the reasoner-vs-LB
gap is a **training-data shortage**. They built a generator producing arbitrary `rule_found` samples using
**task-level statistics extracted from `train.csv`** — character frequencies, numeric ranges/distributions, and
transformation-method distributions. **Quality-control loop:** train **only on synthetic**, evaluate on **both
synthetic and original**; if the synthetic perfectly imitates the original, the two eval accuracies match — the
**gap reveals missing factors** in the generator, fixed iteratively (analyze → generate → train → eval both →
compare gap → fix → repeat). **Final submission: synthetic : original = 2.5 : 1** (synthetic first, then
original). Longer training improved loss, especially on hard tasks.

**(3) Two stability tricks:**
- **Per-character tokenization for cryptarithm.** BPE sometimes merges multiple symbols into one token
  (e.g. `}!` → token 119020). They used **synthetic tokens that force each character to encode as one token**
  → more stable learning on the symbol categories. *(A genuinely novel lever directly relevant to our
  equation/cipher work — we never did this.)*
- **Gradient clipping at 1.5** (the public notebook used **1e9 = effectively off**). The 1e9 setting caused
  **training instability** and **submission-to-submission score variance** (a grad-norm spike to **25,089 @
  step 107** in one run); clipping at 1.5 stabilized it. *(Contradicts our v14 / mspawar "grad-clip off" — a
  concrete fix for run-to-run variance.)*

## 2. Validation strategy (eval-mistrust theme, again)
Until mid-competition they validated by **training on synthetic, evaluating on original**. But as the generator
improved, the model **overfit the original** and **local validation diverged from Public LB** → for the final
stage they **prioritized Public LB** (unseen data) over local validation. *(Echoes LB25's eval-bug and our T12
"trust the LB aggregate" lesson — local proxies drift.)*

## 3. What did NOT work
- **RL via SimPO / ORPO.** To build *rejected*, they sampled the SFT model at **temp 1.3**; *chosen* = the
  reasoner's output. Preference learning **did not improve accuracy** and was dropped. In the logs, the *chosen*
  probability rose but the *rejected* probability **barely fell** (the reward plot shows `chosen` flat ~0,
  `rejected` noisy-negative). Their diagnosis: **chosen and rejected were too similar** → insufficient learning
  signal. *(Another independent "RL doesn't beat SFT here" result — cf. mspawar's binary-failure / DPO-limited.)*
- **Solving the new hard problems.** bit_manipulation & cryptarithm CoTs that an LLM can *imitate* were very
  hard: the solving algorithms need **large search**, infeasible for an LLM within the token budget. They even
  used **Claude Fable 5** but could not build a sufficiently strong reasoner. *(Confirms the discovery /
  token-budget wall — same as LB80's "discovery leakage" + 8192-token limit.)*

## 4. What this means for us
- **Per-char tokenization** is a **new, untried lever** for our symbol categories (equation/cipher) — cheap to test.
- **Grad-clip 1.5** may cut our submission variance (we use 1e9-off, like the public notebook they fixed).
- **Statistics-matched synthetic + the gap-closing validation loop** refines our "synthetic dilutes" finding:
  our synth (b1/b2/v15) regressed, but theirs *helped* because it **matched train.csv statistics**, used a
  **2.5:1 ratio with synthetic-vs-original gap QC**, and trained longer. Naive synth dilutes; **statistics-
  matched, gap-validated synth can help.**
- **RL (SimPO/ORPO) failed for them too** — corroborates LB80's binary-failure diagnosis and our RL skepticism.
- They, like everyone, **could not crack cryptarithm/equation** (the bounded wall) and explicitly chose to
  protect the easy categories instead.

## 5. Citations
- **writeup (full): `temp/LB92.pdf`** (render of the Kaggle writeup; DOI 10.34740/kaggle/w/88245; primary source).
- public notebooks it builds on (Kaggle, JS-gated): "End-to-end finetuning for LB 0.85", "Training with Unsloth
  to Achieve 0.85 LB", "Tinker submission notebook"; reasoner = Open Progress Prize Publication (huikang).
- our scores/recipe + EQ-0/EQ-2′ — `tracking.md`, `submissions.md`, `equation-frontier.md §8`, `insights.md` (own work).
