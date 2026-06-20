# `lb1-v1` — Post-LB1 next-version adapter pipeline

Reproducible implementation of the 1st-place ("LB1") symbolic-reasoning method for
the NVIDIA Nemotron Model Reasoning Challenge, derived from
`../../external/LB1/analysis/next_version_plan.md` and the writeup
`../../external/LB1/writeup/lb1-writeup.md`.

> **Status / scope.** The competition's official deadline was **2026-06-15 23:59 UTC**;
> it is closed for ranking (private LB released 2026-06-16, no shake-up). This
> version is therefore **reusable methodology + method-validation**, not a live
> competition entry. LB1 is a *training-data* method — a real `lb1-v1` submission
> requires a GPU-trained rank≤32 LoRA adapter (the base model alone is ~0.47), so
> the **CPU pipeline here is complete and validated; the GPU training + the
> guarded late-submission are a documented handoff** (see "Submit gate" below).
> A post-deadline **late-submission window (100/team/day)** does still score the
> LB without affecting the final ranking (the EQ campaign used it 2026-06-16).

## What this implements (all CPU, no GPU)

| module | role | validated result |
|---|---|---|
| `rules24.py` | the 24-rule operator inventory (equation-numeric + cryptarithm) | reproduces the writeup's published `ABCCCDD` catalog rows exactly |
| `signature_catalog.py` | cryptarithm signature catalog (100×100 operands × 22 non-join rules) | **4,205 signatures — exact match** to the writeup; `ABCCCDD` → 15 candidates (add 1 / flip_add 8 / flip_add+1 6) |
| `eq_reprobe.py` | re-test the "global cipher" premise on real `train.csv` | **deduce 95.0%** (writeup 95.5%), guess 47.8% (52.9%); split 596/136 exact |
| `hex_compress.py` | HEX compression of bit columns (len ≥ 4) | `1101000001` → `341` exact; ~75% char reduction on 8-bit strings |
| `rule_sequence_catalog.py` | bit transform catalog + Hamming-distance repair | repair recovers a Hamming-3-corrupted transform exactly; **count is train-tuned, see below** |
| `solvers.py` | staged cryptarithm DFS trace + per-bit/HEX/repair bit trace | traces verify against ground truth (no-poison rule) |
| `synth_gen.py` | programmatic synth with Obs.1/Obs.2 + consistency filter | 32.7% accept rate; trace medians 265–415 tokens (≪ 5,000 bit gate) |
| `scorer.py` | "correct within 7680 tokens" + per-category coverage | reuses the ported official metric (`../../eval/official_metric.py`) |
| `validate.py` | fail-fast preflight: extraction, rank≤32, zip structure, no secrets | rank-64 and nested-zip both correctly rejected |
| `package_submission.py` | build a root-structured `submission.zip` from an adapter | dummy rank-32 adapter → valid zip → preflight PASS |

### The two re-derivation outcomes (honest)

* **Signature catalog: reproduced exactly (4,205).** A clean enumeration; my rule
  semantics match the writeup's own published slot strings byte-for-byte.
* **Bit rule-sequence catalog: NOT reproduced (target ≈5,238).** A pure grammar
  enumeration over the writeup's operation list yields **857,692 distinct per-bit
  sequences / 115,826 distinct 8-bit functions** — two orders of magnitude over
  5,238. The writeup states the catalog was **tuned to `train.csv` coverage**
  ("added and removed rule families while keeping the ability to explain all bit
  examples"), so 5,238 is a tuned subset that is *not recoverable from the prose*.
  The plan flagged this as "≈ 5,238". The repair **mechanism** is faithful and
  tested; a tractable `build_core_catalog()` (~50k, restricted primitives) backs
  the repair NN. Closing the bit-coverage gap to LB1's 93–97% needs their tuned
  solver + the GPU volume, both out of scope here.

## Run

```bash
cd competitions/nvidia-nemotron/versions/lb1-v1
bash run.sh            # catalogs + eq-reprobe + synth sample + preflight (CPU, minutes)
```

Individual steps:

```bash
python signature_catalog.py                 # 4205 check
python eq_reprobe.py                         # needs train.csv (see config.yaml)
python rule_sequence_catalog.py              # bit catalog count (overshoots; see above)
python synth_gen.py --n 2000 --report        # synth corpus + token histogram
python validate.py --self                    # extraction + fail-fast
python package_submission.py --dummy --adapter-dir /tmp/a --out /tmp/submission.zip
python validate.py --zip /tmp/submission.zip # full preflight gate
```

## Submit gate (guarded) — EXECUTED

`require_preflight_pass_before_submit: true`. The full GPU pipeline ran and the one
guarded late-window submit was executed (2026-06-20): kernel `harrysun2006/nemo-lb1-v1`
trained on RTX Pro 6000 (step 619/786, 7h B7 guard) → preflight PASS on the real
1.37 GB rank-32 adapter → submit → **Public LB 0.828 / Private LB 0.816**.

Below the held-best (soup 0.86/0.85, v14 0.85, eq-aug 0.86/0.86) — as predicted for
a down-scaled run (17k synth ≪ LB1's 360k; crypt under-weighted; partial epoch). The
*method* is validated CPU-side (4,205 exact, eq-deduce 95.0%); this confirms volume
is the moat. Held-best untouched (late window = no ranking effect). See
`../../submissions.md` for the full reading + the scale-up next step. Follow-up: drop
`lm_head` from `target_modules` to shrink the 1.37 GB adapter (no score effect).

## Provenance

All external writeup content is treated as untrusted data. Anchors:
`../../external/LB1/{writeup,analysis}`, `../../{notes,submissions,insights,bugs}.md`,
`../../eval/official_metric.py`, `../../lib/nemo_solver.py`.
