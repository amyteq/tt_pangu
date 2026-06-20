# LB109 / 109th Place "Heuristics" — post-competition archive

Post-competition archive for **"Heuristics for bit, cryptarithm and equations"** by **Andrey Kulakov (jex398)**
of the NVIDIA Nemotron Model Reasoning Challenge. Final ~0.82; the equation-guess change (+50) moved him 1000+ → ~109.

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB109_task.md`; competition ended).

## Contents
```
LB109/
  README.md  source_index.md
  writeup/   lb109-writeup.md  lb109-writeup.zh.md  raw/lb109-pdftotext-layout.txt
  analysis/  method_summary.md  score_tricks.md  gap_analysis.md  next_version_plan.md
  models/  datasets/  links/  notebooks/ (empty)
```

## One-paragraph takeaway
An **ideas writeup** — most heuristics were too long to ship, and only the **equation-guess sign-deduction (+50
tasks)** actually moved the leaderboard (1000+ → ~109). But the ideas are valuable angles we lack: a **bit ANF
(algebraic normal form) trick** (`XOR(A,B,C)⊕C=A⊕B` → match a 2-param table; generalizable to OR/Choice/Maj/etc. via
partial-ANF + XOR-on-output matching) that shrinks the 3-arg bit search; **negation canonicalization**
(`Shift(Not(x))`); and **modular branch-cutting for cryptarithm** (mod-10 carries + mod 37/11/100) that lets a
deterministic search converge within the 7k-token budget. The cryptarithm solver overfit (rushed training → 0.82).
The honest meta-lesson: **ship partial wins** (just XOR3, just mod-10) instead of chasing a perfect solver. See
`analysis/` and the `lb109-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
