# `lb10-v1` — Post-LB10 next-version implementation

Reproducible CPU implementation of the **LB10** method (Public 0.860 / Private 0.880),
derived from `../../external/LB10/analysis/next_version_plan.md` + the writeup. LB10's
distinctive contributions are an **"improve the teacher"** discipline (raise oracle
coverage first), a **rotate/shift key-table bit reasoner**, and **oracle-vs-fidelity +
logprob-learnability** diagnostics.

> **Competition status: CLOSED (deadline 2026-06-15 23:59 UTC).** No live Kaggle
> submission — the submit preflight gate cannot pass for a closed competition with no
> completed GPU run (see "Submit gate"). GPU SFT is **handed off** (gated; ~8–16h RTX
> Pro 6000). Everything here is the **no-GPU, CPU-runnable** half.

## Measured results (run `bash run.sh`)

| module | what it measures | result |
|---|---|---|
| `eq_reprobe.py` | **equation premise re-test on REAL `train.csv`** (732 prompts) | **deduce 566/596 = 95.0%**, guess 47.8% — 5th independent refutation |
| `bit_keytable_reasoner.py` | rotate/shift key-table reasoner (single-operand; n=200) | 8-ex **96.5%**; 16-ex **100%**; **oracle ~98–100%** once all 8 keys are covered |
| `equation_solver.py` | frequency-deduce + two-axis guess (n=300) | deduce **99.3%**; guess 48.3% (synthetic) |
| `learnability.py --self` | oracle-ceiling vs model-fidelity + logprob learnability | split reported; fragile-trace tail flagged for priority-2× |
| `validate.py --self` | keep-failures + oracle ceiling + perfect-trace-rate + preflight | **PASS** (rank=32≤32; unsolved traces retained) |

**The bit key-table reasoner is the headline lever.** LB10 models the bit generator as
`out[i] = F(rotl(x,a)[i], shl(x,b)[i], shr(x,c)[i])` with a 3-bit-key→bit table; once
the examples cover all 8 keys the **oracle reaches ~98–100%** (the "improve the teacher"
ceiling), and `learnability.py` separates that ceiling from the model's *imitation gap*
so fixes target the right thing. **Equation premise:** the real-data re-probe (95.0%
deduce) is another independent refutation of the global-cipher verdict.

> Note: the bit/equation `guess`/synthetic numbers validate the *mechanism*, not LB10's
> harder real rates. Cryptarithm stays weak (~9% in LB10) — graft LB1/LB3 for the top end.

## Files
- `bit_keytable_reasoner.py` — **rotate/shift key-table** bit reasoner: `(a,b,c)` boundary-bit recovery, conflict-pruned key→bit accumulation, agreement/majority fallback, compact `key>value` traces.
- `equation_solver.py` — **frequency-ordered deduce** + **two-axis guess** (op = conventional-if-free else first-unused {add, absdiff, mul}; wrapper pinned from the most-seen operator).
- `learnability.py` — **oracle-ceiling vs model-fidelity** split + **per-example logprob** learnability export (fragile-trace flagging for priority-2× upsampling).
- `corpus.py` — ties solvers into `{id, category, answer, trace, solved}` records (keeps failed/low-conf traces; every trace ends `\boxed{}`).
- `validate.py` — keep-failures assertion, oracle ceiling, perfect-trace-rate, adapter rank/zip preflight, fail-fast, **select-by-validation** rule.
- `scorer.py` / `package_submission.py` — official-metric scorer / root-level rank≤32 LoRA zip (shared).
- `eq_reprobe.py` + `rules24.py` — equation premise re-probe (shared with lb1/lb3/lb5/lb6/lb13-v1).
- `train_lb10.py` — **GPU-gated** SFT driver (alpha/r=4, 2 epochs); keep-failures + LoRA-merge A/B flags; fails loudly without a GPU.
- `config.yaml` — single source of truth; `run.sh` — runs all CPU steps.

## Training (GPU-gated — NOT run here)
Single base model + LoRA from `config.yaml`: **rank-32 / alpha-128 (alpha/r = 4)**,
all-proj + lm_head, LR 2e-4 linear, **2 epochs**, eff batch 32, stratified. "Improve the
teacher" first (raise oracle coverage); **keep failed/low-conf traces**; priority-2× the
fragile (low-logprob) modes; **select by validation, never the public LB**. Two A/Bs are
wired: keep-failures vs verified-only, and LoRA-merge (LB10 reported merge *failed*).
Down-scaled validation ≈ 8–16h on an RTX Pro 6000.
Driver: `python train_lb10.py --config config.yaml --do-train`.

## Submit gate (why there is no submission)
`config.yaml:submit.require_preflight_pass: true`. The competition **closed 2026-06-15**
and no GPU run was performed → **no `submission.zip`**, so the preflight blocks. The
guarded-submit attempt is executed (`kca kaggle submit`) and its BLOCKED decision is
recorded to `.agent/kca/audit.jsonl`. Hold-best (soup 0.86/0.85, eq-aug 0.86/0.86)
untouched. For a future live run: select by validation, ship the higher-validation run
even if public is lower (LB10's lesson), then package + preflight + submit.
