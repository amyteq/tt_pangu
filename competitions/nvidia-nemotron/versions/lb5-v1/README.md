# `lb5-v1` — Post-LB5 next-version implementation

Reproducible CPU implementation of the **LB5 / 5th-place** method (Private 0.900,
*"RL with Infinite Training Data Generator and Iterative LoRA Averaging"*), derived
from `../../external/LB5/analysis/next_version_plan.md` + the writeup.

> **Competition status: CLOSED (deadline 2026-06-15 23:59 UTC).** No live Kaggle
> submission — the submit preflight gate cannot pass for a closed competition with no
> completed GPU run (see "Submit gate"). GPU 3-phase soup training is **handed off**
> (gated; ~10–25h RTX Pro 6000). Everything here is the **no-GPU, CPU-runnable** half:
> solvers, the no-leakage generator, the private-tracking validation, and the shared
> equation-deduce premise re-probe.

## What this validates (the *mechanism*, not LB5's 0.900)
Per the plan, post-competition work validates the **mechanism** (soup stability,
no-leakage CV tracking private, ternary bit lift, equation solvability), not the full
score. All numbers below are measured by running the modules. Synthetic numbers use
self-generated instances with known ground truth; the equation re-probe uses the real
(uncommitted) competition `train.csv`.

## Measured results (run `bash run.sh`)

| module | what it measures | result |
|---|---|---|
| `eq_reprobe.py` | **equation premise re-test on REAL `train.csv`** (732 prompts) | **deduce 566/596 = 95.0%**, guess 47.8% — **3rd independent refutation** (after LB1 95.5%, LB3 93.3%) |
| `equation_solver.py` | LB5 2-world/4-family/13-rule solver (synthetic, n=300) | deduce **99.7%**; guess 20.7% (synthetic guess adversarial) |
| `bit_ternary_solver.py` | ternary raw-bit solver, 7-vs-10-example cut (n=300) | binary **100%**, ternary **100%**; **7-example cut loses nothing** |
| `tokenizer_probe.py` | HEX-vs-raw-bits merge risk (LB5 negative lesson) | flags merged `5A`/`AB` as HIGH risk; spaced raw bits / spaced hex safe |
| `generator.py` | no-leakage statistics-matched generator | fits train stats (bit 1602 / eq 1555); **no-leakage PASS** vs 9500 prompts; unique answers |
| `validate.py --self` | no-leakage discipline + oracle solvability + soup-stability proxy + preflight | **PASS** (rank=32≤32, deterministic offline metric) |

**Equation premise — 3rd independent refutation.** The real-data re-probe (95.0%
deduce) confirms equation-numeric *deduce* is per-prompt-operator solvable, not a
global cipher (matches LB1/LB3/LB5). Our `equation-frontier.md` verdict holds only for
the *guess* subset (~48%). LB5's contribution: it reaches 0.90 **without** cryptarithm
by maxing bit/equation/trivials + **iterative LoRA-averaging soup stability**.

## Files
- `equation_solver.py` — LB5 **2-world / 4-family / 13-rule** equation solver (deterministic priority, family guessing).
- `bit_ternary_solver.py` — **ternary** byte-level bit solver: 15 primitives (8 binary + 7 ternary: MAJ3/CHOICE/XOR_NOT_OR/...), **raw bits**, 7-example cut.
- `generator.py` — **no-leakage** statistics-matched synthetic generator (train.csv = validation only); `assert_no_leakage`.
- `tokenizer_probe.py` — HEX-vs-raw-bits per-symbol token granularity check (the LB5 merged-token negative lesson).
- `corpus.py` — wraps the generator into `{category, answer, trace}` records (traces end `\boxed{}`).
- `validate.py` — **private-tracking** no-leakage validation, per-category oracle solvability, perfect-trace-rate, soup-stability proxy, adapter rank/zip preflight, fail-fast.
- `scorer.py` — official-metric within-7680-token scorer + per-category coverage.
- `package_submission.py` — root-level rank≤32 LoRA → `submission.zip` (+ dummy builder).
- `eq_reprobe.py` + `rules24.py` — equation premise re-probe (shared with lb1-v1 / lb3-v1).
- `train_phases.py` — **GPU-gated** 3-phase driver (multi-round SFT → LoRA averaging → multi-seed soup); fails loudly without a GPU.
- `config.yaml` — single source of truth; `run.sh` — runs all CPU steps.

## Training (GPU-gated — NOT run here)
3 phases from `config.yaml` (@huikang trainer, **no quant / no packing / no DoRA**,
rank-32/α32, LR 1e-4→2e-4, grad_clip 1.0): (1) multi-round high-LR SFT (all categories
each round); (2) **LoRA averaging** before/after each step (soup regularizer →
stability); (3) **multi-seed soup** (3 adapters from one checkpoint, averaged). LB5
reference ≈ 2B tokens / 15 iterations; down-scaled validation ≈ 10–25h on an RTX Pro
6000. Driver: `python train_phases.py --phase all --config config.yaml`.

## Submit gate (why there is no submission)
`config.yaml:submit.require_preflight_pass: true`. The competition **closed 2026-06-15**
and no GPU run was performed → **no `submission.zip`**, so the preflight items
"submission.zip exists" / "run completed" fail and the guard blocks. Hold-best (soup
0.86/0.85, eq-aug 0.86/0.86) untouched. The guarded-submit attempt is executed and its
BLOCKED decision recorded to `.agent/kca/audit.jsonl`.

For a **future live** competition, select on the **no-leakage CV** (not the public LB);
soup-stabilized adapters reduce selection variance; then package + preflight + submit.
