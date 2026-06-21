# `lb25-v1` — Post-LB25 method (huikang Progress-Prize improvements)

Reproducible packaging of the **LB25** method (Tong Hui Kang's "Improvements to the
progress prize submission", the baseline lineage our v14 derives from), from
`../../external/LB25/analysis/{next_version_plan,method_summary,score_tricks}.md`.

> **Already realized — read before running a GPU job.** The LB25 `next_version_plan`'s
> version is **`v16-evalfix`**, which was trained + submitted on 2026-06-20 (late
> window): **Public 0.832 / Private 0.828 — below the 0.86 held-best; "hypothesis NOT
> supported"** (LEVER 1 is measurement-only; LEVER 2+3 diluted, the b2/v15/c2 lesson).
> See `../../submissions.md` and the plan's EXECUTED banner. This directory is the
> clean, reusable packaging of the LB25 levers — **not** a new method expected to beat
> 0.86. A fresh `lb25-v1` GPU run would reproduce that known below-best result.

## The five LB25 levers (packaged here, all CPU)

| module | LB25 lever | what it does | result |
|---|---|---|---|
| `eval_parity.py` | #1 (HIGH, ~free) | eval prompt + decode byte-identical to the grader (the boxed-prompt bug huikang fixed; = our B4/INS-002) | reusable audit; measurement-only (can't move an LB the grader already scores right) |
| `eq_reversal.py` | #2 (Med-High) | one REVERSE/NORMAL world per prompt (Obs.1) → halve equation search; reuses `rules24`/`eq_reprobe` | the earliest of 7 confirmations equation is per-problem-structured (cf. eq-deduce 95%) |
| `easy_cat_synth.py` | #3/#4 (Med) | cipher/unit/gravity/numeral + cipher-prefix synth, verified | no-regression guard only (easy cats already ~ceiling) |
| `bit_cot.py` | #5 (Med) | reorganized, own-solver-verified bit CoT (grader-faithful `bit_verify`) | the realized v16-evalfix bit solver |
| (config) `min_logprob_replay` | ours | replay the hardest residual rows by min logprob (≤15% dose) | base-pipeline signal; diluted at this scale |

Shared pipeline pieces are reused from the lb1-v1 batch (copied per the version-dir
convention): `rules24.py`, `eq_reprobe.py`, `hex_compress.py`, `scorer.py`,
`validate.py`, `package_submission.py`; the official metric is
`../../eval/official_metric.py`.

## Run (CPU, no GPU)

```bash
cd competitions/nvidia-nemotron/versions/lb25-v1
bash run.sh
# or individually:
python eval_parity.py        # the headline lever (self-demonstration; reusable tool)
python eq_reversal.py        # needs train.csv — reversal symmetry on real prompts
python bit_cot.py            # reorganized bit CoT self-check
python easy_cat_synth.py --n 200 --report
python validate.py --self    # extraction + fail-fast preflight
```

## Submit gate (guarded)

`require_preflight_pass_before_submit: true`. The LB25 method's real LB result
**already exists** (v16-evalfix 0.832/0.828). A fresh `lb25-v1` adapter would need a
GPU run (~7h, v14 backbone + Phase-B levers) and reproduce ~the same below-best
number, consuming a submission slot for no expected gain (submission-strategy
scenario 2: don't spend slots when nothing beats best). The held-best is untouched
either way (soup 0.86/0.85, v14 0.85, eq-aug 0.86/0.86).

## Provenance

External writeup content is treated as untrusted data. Anchors:
`../../external/LB25/{analysis,writeup}`, the realized kernel
`../../kernels/nemo-v16-evalfix.py`, `../../{tracking,submissions,insights,bugs}.md`.
