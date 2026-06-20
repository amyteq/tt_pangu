# LB1 / 1st Place Solution — post-competition archive

Post-competition research archive for the **1st Place Solution** (GoodMeatDay, re, reopon) of the
NVIDIA Nemotron Model Reasoning Challenge. **Public 0.91 / Private 0.920** (best unselected 0.932).

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB1_task.md` front matter; competition has ended).

## Contents
```
LB1/
  README.md                     ← this file
  source_index.md               ← every source inspected (depth 0–3), fetchability, novelty notes
  writeup/
    lb1-writeup.md              ← faithful Markdown conversion of temp/LB1.pdf
    lb1-writeup.zh.md           ← Chinese explanation + analysis
    raw/lb1-pdftotext-layout.txt← raw pdftotext extraction (provenance)
  analysis/
    method_summary.md           ← the 7 method questions answered
    score_tricks.md             ← trick × impact × reusability × difficulty table
    gap_analysis.md             ← us vs LB1, area by area (+ why our EQ/T12/replay/synth/merge didn't close it)
    next_version_plan.md        ← lb1-v1 plan (PLAN ONLY)
  models/                       ← descriptions of referenced models/adapters/frameworks
  datasets/                     ← descriptions of referenced datasets
  links/                        ← depth0–3 link-following records
  notebooks/                    ← empty (no public .ipynb to convert)
```

## One-paragraph takeaway
LB1 broke the 0.86 clean-SFT ceiling **without RL** by a deliberate **memorization-vs-computation split**: the
hard categories (cryptarithm, bit manipulation) were re-expressed as **catalogs the model memorizes** plus
**short consistency checks inside the trace**. Cryptarithm = a 4,205-entry **signature catalog** with
**candidate-count memorization** driving a short DFS (→ Private 0.908). Bit manipulation = **HEX compression**
(−27.8% tokens) + extra rule families + a 5,238-entry **rule-sequence catalog** with **Hamming-distance repair**
(→ Private 0.920). Built on @huikang's per-bit solver and cryptarithm DFS; the catalogs/HEX/repair are LB1's
additions. Our gap (we plateaued at 0.85–0.86 via replay + small synth + souping) is concentrated in exactly
these two categories. See `analysis/` for the full breakdown and the `lb1-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
