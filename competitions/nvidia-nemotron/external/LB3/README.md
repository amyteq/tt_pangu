# LB3 / 3rd Place Solution — post-competition archive

Post-competition research archive for the **3rd Place Solution** by **YS-L (liauys)** of the
NVIDIA Nemotron Model Reasoning Challenge. **Private LB 0.900** (local validation 90.46%).

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB3_task.md`; competition ended).

## Contents
```
LB3/
  README.md               ← this file
  source_index.md         ← sources (depth 0–3), fetchability, novelty notes
  writeup/
    lb3-writeup.md        ← faithful Markdown of temp/LB3.pdf
    lb3-writeup.zh.md     ← Chinese explanation + analysis
    raw/lb3-pdftotext-layout.txt
  analysis/
    method_summary.md     ← the 7 method questions
    score_tricks.md       ← trick × impact × reusability table
    gap_analysis.md       ← us vs LB3, area by area
    next_version_plan.md  ← lb3-v1 plan (PLAN ONLY)
  models/                 ← referenced models/adapters/frameworks
  datasets/               ← referenced datasets
  links/                  ← depth0–3 link-following records
  notebooks/              ← empty (no public .ipynb to convert)
```

## One-paragraph takeaway
LB3 reaches **0.900 private without RL** via two standout moves on top of huikang/llkh0a/youkinasa/kemshim:
a **two-stage training** that **decouples memorization from execution** (stage 1 drills the lookup table via
`<RECALL_DOMAINS>`/`<RECALL_ROWS>` completions; stage 2 learns to execute the trace — ~3× more sample-efficient,
12K samples: direct 0 vs two-stage 7 solved), and a **CSP cryptarithm solver** (multiplication-pattern lookup →
multi-example domain intersection → anchor mappings → bounded backtracking, 24.2% within budget). It also adds
**hex+tail-bit bit-trace compression** (−25% tokens → MAJ search) and a **leakage-controlled local validation that
tracks the PRIVATE LB** (the public 0.86 "wall" is a public-LB artifact). See `analysis/` and the `lb3-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
