# LB6 / 6th Place (2nd public) Solution — post-competition archive

Post-competition research archive for **"[2nd public / 6th private] place solution"** by **Yurnero, Alehandreus**
of the NVIDIA Nemotron Model Reasoning Challenge.

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB6_task.md`; competition ended).

## Contents
```
LB6/
  README.md  source_index.md
  writeup/   lb6-writeup.md  lb6-writeup.zh.md  raw/lb6-pdftotext-layout.txt
  analysis/  method_summary.md  score_tricks.md  gap_analysis.md  next_version_plan.md
  models/  datasets/  links/  notebooks/ (empty)
```

## One-paragraph takeaway
LB6 (2nd public / 6th private) leans on a **validation strategy** more than a single modeling trick. Its standout
is **per-domain LB probing**: mask every non-target domain with `I will ignore this problem\n\boxed{DUMMY}` so the
public LB returns a **pure single-domain signal** (directly the attribution tool we lacked for our B8 "single-category
gain ≠ total gain"). It also uses **full-train-as-validation** (≈10× the holdout) via distribution-matched synthetic,
a **template bit solver** (shl/shr/rotr + ternary MAJ/CH, monotonic skips, **hex arithmetic + cheatsheet**; 1508/1602),
and a **DFS cryptarithm solver with reversed search** (~40% solved reversed; 240/654 deduce). A key documented finding:
**bit CV is fragile to any data-mix change** (bit = 69%/66% of tokens), and a mis-estimated bit/cryptarithm trade-off
(the 0.5B dataset) **cost them 2nd-3rd** — they shipped two seeds of the safer 0.25B instead. See `analysis/` and the
`lb6-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
