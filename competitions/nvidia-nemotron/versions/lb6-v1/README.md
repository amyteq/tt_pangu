# `lb6-v1` — Post-LB6 next-version implementation

Reproducible CPU implementation of the **LB6** method (2nd public / 6th private),
derived from `../../external/LB6/analysis/next_version_plan.md` + the writeup. LB6's
signature contribution is a **third validation paradigm** — per-domain **DUMMY-masking
LB probing** + full-train-as-validation — alongside template bit and DFS cryptarithm solvers.

> **Competition status: CLOSED (deadline 2026-06-15 23:59 UTC).** No live Kaggle
> submission — the submit preflight gate cannot pass for a closed competition with no
> completed GPU run (see "Submit gate"). GPU Unsloth SFT is **handed off** (gated;
> ~6–14h RTX Pro 6000). Everything here is the **no-GPU, CPU-runnable** half.

## Measured results (run `bash run.sh`)

| module | what it measures | result |
|---|---|---|
| `eq_reprobe.py` | **equation premise re-test on REAL `train.csv`** (732 prompts) | **deduce 566/596 = 95.0%**, guess 47.8% — refutes "global cipher" |
| `equation_solver.py` | add/sub/mul + **maxmodmin** families, family-exclusion guess (n=300) | deduce **100%**; guess 47.7% (synthetic; writeup guess 92.6%) |
| `bit_template_solver.py` | shl/shr/rotr × pairwise/ternary templates, hex cheatsheet (n=200) | pairwise+shift **99.5%**, ternary **100%** (writeup 1508/1602 = 94.1%) |
| `cryptarithm_dfs.py` | DFS + reversed search + leading-zero/units/equation-sorting pruning (n) | `*` **100%**, `+` 93% (writeup deduce 240/654 = 37%) |
| `dummy_probe.py` | **per-domain DUMMY-masking attribution** (the signature lever; B8 fix) | isolates each domain's signal; non-target rows emit `\boxed{DUMMY}` |
| `tradeoff_cv.py` | bit/cryptarithm trade-off calibration (LB6's selection regret) | predicts bit-CV drop when cryptarithm tokens are added |
| `validate.py --self` | full-train-as-validation + DUMMY probe + perfect-trace-rate + preflight | **PASS** (rank=32≤32) |

**Signature lever — DUMMY-masking attribution.** LB6 reads a *single* domain's signal
by emitting the target domain's real CoT and `I will ignore this problem\n\boxed{DUMMY}`
for every other domain. This directly addresses our recurring **B8** ("single-category
gain ≠ total gain"). Run offline here (competition over) against a local labelled set;
0.01 LB ≈ 3 problems (LB6's −0/−1/−2 notation). **Equation premise:** the real-data
re-probe (95.0% deduce) is another independent refutation of the global-cipher verdict.

> Note: the DFS **reversed pass contributes 0** on clean forward-solvable synthetic — it
> is the fallback for the real reversed-structured cases (LB6: ~40% of solves). The
> `guess` and cryptarithm numbers are mechanism validation, not LB6's harder real rates.

## Files
- `dummy_probe.py` — **per-domain DUMMY-masking** attribution harness (signature LB6 lever; offline).
- `bit_template_solver.py` — **template** bit solver: shl/shr/rotr × pairwise (XOR/AND/OR/AND-NOT/OR-NOT) + ternary (MAJ/CH), shift iteration + monotonic skips + **hex cheatsheet**.
- `cryptarithm_dfs.py` — **DFS** bijection solver with **reversed search** + leading-zero/units/equation-sorting pruning.
- `equation_solver.py` — add/sub/mul + **maxmodmin** families, family-exclusion guess.
- `tradeoff_cv.py` — **bit/cryptarithm trade-off** calibration (predict the bit-CV drop before committing the mix — LB6's regret).
- `corpus.py` — ties solvers into `{category, answer, trace}` records (traces end `\boxed{}`).
- `validate.py` — full-train-as-validation + DUMMY-probe attribution + perfect-trace-rate + adapter rank/zip preflight + fail-fast.
- `scorer.py` / `package_submission.py` — official-metric scorer / root-level rank≤32 LoRA zip (shared).
- `eq_reprobe.py` + `rules24.py` — equation premise re-probe (shared with lb1/lb3/lb5/lb13-v1).
- `train_lb6.py` — **GPU-gated** Unsloth SFT driver (BS 32, LR 3.5e-4, rank32/α32, 1 epoch); fails loudly without a GPU.
- `config.yaml` — single source of truth; `run.sh` — runs all CPU steps.

## Training (GPU-gated — NOT run here)
Single-epoch Unsloth LoRA SFT (BS 32, LR 3.5e-4, rank-32/α32) on a massive
distribution-matched synthetic corpus with **bit over-weighted to ~69% of tokens**;
validate on the real set (full-train-as-validation) with per-domain DUMMY probing.
**Calibrate the bit/cryptarithm trade-off first** (`tradeoff_cv.py`) — under-estimating
it cost LB6 2nd–3rd place. LB6 ≈ 0.25–0.5B tokens; down-scaled validation ≈ 6–14h on an
RTX Pro 6000. Driver: `python train_lb6.py --config config.yaml --do-train`.

## Submit gate (why there is no submission)
`config.yaml:submit.require_preflight_pass: true`. The competition **closed 2026-06-15**
and no GPU run was performed → **no `submission.zip`**, so the preflight blocks. The
guarded-submit attempt is executed (`kca kaggle submit`) and its BLOCKED decision is
recorded to `.agent/kca/audit.jsonl`. Hold-best (soup 0.86/0.85, eq-aug 0.86/0.86)
untouched. For a future live run: per-domain DUMMY probing for attribution, calibrate
the bit/cryptarithm mix, then package + preflight + submit.
