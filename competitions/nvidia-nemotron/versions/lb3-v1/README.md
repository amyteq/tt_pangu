# `lb3-v1` — Post-LB3 next-version implementation

Reproducible CPU implementation of the **LB3 / 3rd-place** method (Private 0.900),
derived from `../../external/LB3/analysis/next_version_plan.md` + the writeup.

> **Competition status: CLOSED (deadline 2026-06-15 23:59 UTC; today is later).**
> There is **no live Kaggle submission** — the submit preflight gate cannot pass for a
> closed competition (see "Submit gate" below). GPU two-stage training is **handed off**
> (gated; ~10–20h on an RTX Pro 6000) and **not run here**. Everything in this directory
> is the **no-GPU, CPU-runnable** half of the plan: solvers, drill/corpus generation,
> the private-tracking validation harness, and the equation-deduce premise re-probe.

## What this validates (the *mechanism*, not LB3's 0.900)
The plan explicitly scopes post-competition work to validating the **mechanism**
(two-stage sample efficiency, CSP recall quality, hex token savings, equation-deduce
solvability), not reproducing the full private score. All numbers below are measured by
running the modules; synthetic numbers come from self-generated instances with known
ground truth (we have the competition `train.csv` only for the equation re-probe).

## Measured results (run `bash run.sh`)

| module | what it measures | result |
|---|---|---|
| `eq_reprobe.py` | **equation-numeric premise re-test on REAL `train.csv`** (732 prompts) | **deduce 95.0% (566/596)**, guess 47.8% (65/136) |
| `cryptarithm_csp.py` | CSP solve + full-mapping recovery (synthetic, n=150) | `*` deduce **100%** (map 100%); `+` 98%; `-` 94.7%; `*` guess 94% |
| `bit_hex_trace.py` | bit solver + HEX+tail-2-bit token saving (n=300) | solved **100%**; tokens **−23.4%** (LB3 ref ≈ −25%) |
| `numeric_solver.py` | minimal 13-op solver (n=300) | deduce **98.3%**; guess 11% (synthetic guess is adversarial — see note) |
| `drill_gen.py` | stage-1 packed/masked drills | 16 items/sample; **28.5%** chars masked (loss on recalled rows only) |
| `validate.py --self` | stratified hold-out + leakage exclusion + perfect-trace-rate + adapter preflight | **PASS** (rank=32 ≤32, zip root OK) |

**The equation re-probe is the headline real-data result:** equation-numeric **deduce
is ~95% solvable** via a per-prompt operator inventory — a **2nd independent refutation**
(after LB1) of our `equation-frontier.md` "unrecoverable global cipher" verdict for the
*deduce* subset. Only **guess** (unseen operator) stays hard (~48%), consistent with
LB3's ~57%. This closes the plan's checklist item #1.

> Note on `numeric` guess: our synthetic generator assigns operators at random, so the
> "unused-family" guess heuristic has little signal; LB3's ~57% relies on the official
> generator's **family co-occurrence** structure, which we can't reproduce without the
> generator. Deduce (the solvable subset) is the meaningful synthetic number here.

## Files
- `mul_pattern_lookup.py` — signature→{domains,rows} multiplication lookup (cap 48/sig; a*b, a*b±1).
- `cryptarithm_csp.py` — **headline lever**: lookup → domains → intersect → anchor → bounded
  backtracking (units-digit forward-checking); emits `<RECALL_DOMAINS>/<RECALL_ROWS>`-tagged traces.
- `bit_hex_trace.py` — bit solver, HEX+tail-2-bit compression, OR-NOT-first ordering, MAJ in set.
- `numeric_solver.py` — minimal **13-op** inventory, global simple/reverse, operation-family guessing.
- `drill_gen.py` — stage-1 **memorize drills** (16 packed/sample, request masked).
- `corpus.py` — ties solvers into `{category, answer, trace}` records (every trace ends `\boxed{}`).
- `validate.py` — **private-tracking** 10% stratified hold-out, leakage exclusion, perfect-trace-rate,
  official-extractor within-budget accuracy, adapter rank/zip preflight, fail-fast self-check.
- `scorer.py` — official-metric within-7680-token scorer + per-category coverage.
- `package_submission.py` — root-level rank≤32 LoRA → `submission.zip` (+ dummy-adapter builder).
- `eq_reprobe.py` + `rules24.py` — equation-numeric premise re-probe (shared with `lb1-v1`).
- `train_two_stage.py` — **GPU-gated** two-stage driver (memorize→execute); fails loudly without a GPU.
- `config.yaml` — single source of truth (catalogs, two-stage training, validation, submit).
- `run.sh` — runs all CPU steps end-to-end.

## Training (GPU-gated — NOT run here)
Two-stage, from `config.yaml`: stage 1 memorizes the lookup table (drills, eff batch 8);
stage 2 inits from the stage-1 adapter and trains real traces + 3K retained drills (eff
batch 4, **MoE-tie OFF**, rank-32/α32 fp32, CCE loop, seq 8192, seed 42). LB3 reference
≈ 58 GPU-h; our down-scaled method-validation ≈ 10–20h on an RTX Pro 6000.
Driver: `python train_two_stage.py --stage all --config config.yaml` (on the GPU box).

## Submit gate (why there is no submission)
`config.yaml:submit.require_preflight_pass: true`. Preflight item *"the run completed
successfully"* and a live, **open** competition cannot be satisfied: the competition
**closed 2026-06-15**, and no GPU run was performed. Therefore **no `submission.zip` was
produced and no submit was attempted** — the guard correctly blocks. Hold-best remains
our soup (0.86/0.85) + eq-aug (0.86/0.86); nothing here regresses it.

For a **future live** symbolic-reasoning competition, the authorized flow is:
```sh
# 1) GPU: two-stage train -> rank<=32 adapter (on the GPU box)
python train_two_stage.py --stage all --config config.yaml
# 2) package + preflight
python package_submission.py --adapter-dir adapter_stage2 --out submission.zip
python validate.py --self
# 3) submit (select on the private-tracking offline metric, NOT the public LB)
kaggle competitions submit -c <slug> -f submission.zip -m "postlb3-v1: ..."
```
