# `lb13-v1` — Post-LB13 next-version implementation

Reproducible CPU implementation of the **LB13 / 13th-place** method (teacher oracle
89.4%), derived from `../../external/LB13/analysis/next_version_plan.md` + the writeup.
LB13 contributes the **batch's sharpest equation_numeric structural model** and a
keep-failures data discipline.

> **Competition status: CLOSED (deadline 2026-06-15 23:59 UTC).** No live Kaggle
> submission — the submit preflight gate cannot pass for a closed competition with no
> completed GPU run (see "Submit gate"). GPU 3-stage decreasing-LR SFT is **handed off**
> (gated; ~8–16h RTX Pro 6000). Everything here is the **no-GPU, CPU-runnable** half.

## What this validates (the *mechanism*, not LB13's score)
All numbers below are measured by running the modules. Synthetic numbers use
self-generated instances with known ground truth; the equation re-probe uses the real
(uncommitted) competition `train.csv`.

## Measured results (run `bash run.sh`)

| module | what it measures | result |
|---|---|---|
| `eq_reprobe.py` | **equation premise re-test on REAL `train.csv`** (732 prompts) | **deduce 566/596 = 95.0%**, guess 47.8% — **6th independent refutation** |
| `equation_solver.py` | LB13 4-family / global majority-vote reversal / robust-aggregation (synthetic n=300) | deduce **100%**; guess 84.7%; **robust 100% vs strict 54% under transcription noise** |
| `bit_3input_verify.py` | MAJ/XNOR3 + bit-position search + left-edge fallback (n=300) | solved **100%** (mostly global-verify; fallback recovers the rest) |
| `rebalance.py` | keep-failures 1:1 rebalance + robust aggregation + cryptarithm-from-equation | 1:1 ratio asserted; robust(4/5)=valid, strict=invalid; 3× cryptarithm seeds |
| `validate.py --self` | teacher oracle + robust>strict + 1:1 rebalance + perfect-trace-rate + adapter preflight | **PASS** (rank=32≤32) |

**Two headline results.** (1) The real-data re-probe (**95.0% deduce**) is the **6th
independent refutation** of our `equation-frontier.md` "global cipher" verdict for the
*deduce* subset. (2) LB13's distinct robustness lever is demonstrated directly:
**robust aggregation (op valid if it matches ≥1 example) scores 100% under injected
transcription noise where strict all-example matching collapses to 54%** — this is why
LB13 keeps and tolerates noisy teacher traces instead of discarding them.

## Files
- `equation_solver.py` — **4 mutually-exclusive families** (SUB/ADD/MUL/CONCAT) + **global majority-vote reversal** (both-in-out-or-neither, shared across examples) + **robust ≥1-match aggregation** + family-exclusion guess (tie sub>add>mul>concat).
- `bit_3input_verify.py` — **3-input verification** (MAJORITY/XNOR3) + bit-position-restricted search + left-edge fallback.
- `rebalance.py` — **keep teacher-incorrect** traces, **1:1** correct:incorrect rebalance, robust aggregation, cryptarithm-from-equation augmentation.
- `corpus.py` — ties solvers into `{category, answer, trace, correct}` records (traces end `\boxed{}`).
- `validate.py` — teacher-oracle coverage, robust-vs-strict demonstration, rebalance check, perfect-trace-rate, adapter rank/zip preflight, fail-fast.
- `scorer.py` / `package_submission.py` — official-metric scorer / root-level rank≤32 LoRA zip (shared).
- `eq_reprobe.py` + `rules24.py` — equation premise re-probe (shared with lb1/lb3/lb5-v1).
- `train_3stage.py` — **GPU-gated** 3-stage decreasing-LR SFT driver (2e-4→2e-5→5e-6, upsample hard last); fails loudly without a GPU.
- `config.yaml` — single source of truth; `run.sh` — runs all CPU steps.

## Training (GPU-gated — NOT run here)
3-stage decreasing-LR SFT from `config.yaml` (Unsloth, rank-32/α32, targets **without
lm_head**, eff batch 32): (1) 2ep LR 2e-4 linear; (2) 1ep LR 2e-5 cosine; (3) 1ep LR
5e-6 cosine, upsample bit+cryptarithm. Data: improved-teacher traces, **keep-failures
1:1 rebalanced**. LB13 stage sizes 9277/9277/11315; down-scaled validation ≈ 8–16h on
an RTX Pro 6000. Driver: `python train_3stage.py --stage all --config config.yaml`.

## Submit gate (why there is no submission)
`config.yaml:submit.require_preflight_pass: true`. The competition **closed 2026-06-15**
and no GPU run was performed → **no `submission.zip`**, so the preflight blocks. The
guarded-submit attempt is executed (`kca kaggle submit`) and its BLOCKED decision is
recorded to `.agent/kca/audit.jsonl`. Hold-best (soup 0.86/0.85, eq-aug 0.86/0.86)
untouched. For a future live run: select by validation/oracle, ship the trace-fidelity-best
run, package + preflight + submit.
