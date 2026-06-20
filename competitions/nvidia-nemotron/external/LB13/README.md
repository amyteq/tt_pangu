# LB13 / 13th Place Solution — post-competition archive

Post-competition research archive for the **13th Place Solution** by **Haraguchi-T (haraguchit)** of the NVIDIA
Nemotron Model Reasoning Challenge. (No final LB number given; teacher oracle 87.7% → 89.4%.)

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB13_task.md`; competition ended).

## Contents
```
LB13/
  README.md  source_index.md
  writeup/   lb13-writeup.md  lb13-writeup.zh.md  raw/lb13-pdftotext-layout.txt
  analysis/  method_summary.md  score_tricks.md  gap_analysis.md  next_version_plan.md
  models/  datasets/  links/  notebooks/ (empty)
```

## One-paragraph takeaway
LB13 is a **training-data-construction** solution (improve the @huikang teacher reasoners, then SFT) with the
**sharpest equation_numeric structural model** of the batch: four mutually-exclusive operator categories +
**reversal symmetry shared across all examples** + global reversal by majority vote, giving the **highest guess
rate in the batch (50.7%)** and 95.3% deduce. Two data findings matter for us: it **keeps teacher-incorrect traces
and rebalances them 1:1** (echoing LB10's "excluding failures hurts" — vs our c1/c2 verified-only filter), and uses
**robust aggregation** (an op is valid if it matches ≥1 example, not all). Bit gains came from **3-input verification
(MAJORITY/XNOR)**; training used a **3-stage decreasing-LR SFT** (2e-4 → 2e-5 → 5e-6, upsampling hard categories
last). cryptarithm stayed weak (~10%). See `analysis/` and the `lb13-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
