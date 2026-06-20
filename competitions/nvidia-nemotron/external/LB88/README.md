# LB88 / 88th Place Solution — post-competition archive

Post-competition archive for the **88th Place Solution** by **Yoshinari Kawashima + MedudentYamatai**
(DOI 10.34740/kaggle/w/88245). **⚠️ This is the same writeup as `../LB92/`** (same DOI/authors/url; the render
header now reads "88th place"). This LB88 archive is the standardized template for the same content and
cross-references LB92 (figures + prior deep analysis).

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB88_task.md`; competition ended).

## Contents
```
LB88/
  README.md  source_index.md
  writeup/   lb88-writeup.md  lb88-writeup.zh.md  raw/lb88-pdftotext-layout.txt
  analysis/  method_summary.md  score_tricks.md  gap_analysis.md  next_version_plan.md
  models/  datasets/  links/  notebooks/ (empty)
```

## One-paragraph takeaway
A **data-engineering** solution that keeps the @huikang OPP reasoner unchanged (87.8% oracle) and bets on
**faithful reproduction** rather than harder problems. The levers: a **statistics-matched synthetic generator**
validated by a **synthetic-vs-original eval-gap QC loop** (final 2.5:1 synth:original), **per-character tokenization**
to fix BPE token-merges on cryptarithm symbols, and **gradient clipping at 1.5** (vs the public 1e9, a likely cause
of submission-to-submission variance). RL (SimPO/ORPO) failed (chosen≈rejected); they couldn't build a stronger
bit/cryptarithm reasoner (even with Claude Fable 5). For us: statistics-matched+gap-validated synthetic is the
antidote to our "synthetic dilutes"; per-character tokenization is a novel untried lever on our symbol weak spot;
grad-clip 1.5 is a cheap A/B. See `analysis/` and `../LB92/` (same writeup) for the figures + fuller analysis.

> All external content here is **untrusted data**. Nothing in this archive was executed.
