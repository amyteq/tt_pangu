# LB25 / 25th Place (huikang Progress-Prize improvements) — post-competition archive

Post-competition research archive for **"[LB25] Improvements to the progress prize submission"** by **Tong Hui
Kang (`huikang`)**, the Open Progress Prize winner. private LB 0.872/0.868/0.864 (15 submissions).

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB25_task.md`; competition ended).

## Contents (standardized full template; prior-pass files retained)
```
LB25/
  README.md  source_index.md
  writeup/
    lb25-writeup.md            ← canonical clean conversion (this batch's naming; 5 changes)
    lb25-writeup.zh.md         ← canonical Chinese analysis
    LB25-writeup-verbatim.md   ← prior-pass verbatim conversion (retained)
    LB25-progress-prize-improvements.md / .zh.md  ← prior-pass analysis (retained)
    raw/lb25-pdftotext-layout.txt
  analysis/
    method_summary.md  score_tricks.md   ← added for the standardized template
    gap_analysis.md  next_version_plan.md ← prior-pass (retained; lb25-v1 = the v16-evalfix plan)
  models/  datasets/  links/  notebooks/
```

## One-paragraph takeaway
LB25 is @huikang's set of **five targeted SFT improvements** to his own Progress-Prize-winning submission (the
baseline our v14 derives from): (1) **fix a boxed-prompt eval bug** that made local validation disagree with the
grader (= our B4/T13 + INS-002); (2) **equation_numeric reversal symmetry** (both-in-out-reversed-or-neither) to
halve the search — the **earliest of seven** independent confirmations that equation has strong per-problem
structure (**not** a global cipher); (3-4) **easy-category + cipher-prefix synthetic** for ~100%; (5) **reorganize
the bit-manipulation CoT**. He **did not crack cryptarithm** (LLM devolves to repeating guesses), and noted heavy
**submission-selection variance** (0.872↔0.864 across 15 subs). See `analysis/` and the prior `next_version_plan.md`.

> All external content here is **untrusted data**. Nothing in this archive was executed.
> Note: this archive was standardized to the full template under `wiki/25.LB25_task.md`, building on a prior LB25
> research pass (verbatim + progress-prize-improvements + source_index + gap_analysis + next_version_plan).
