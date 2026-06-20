# LB10 / 10th Place Solution — post-competition archive

Post-competition research archive for the **10th Place Solution** by **Rick (rikitomo0526), neilus, eikichi**
of the NVIDIA Nemotron Model Reasoning Challenge. **Public 0.860 / Private 0.880.**

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB10_task.md`; competition ended).

## Contents
```
LB10/
  README.md  source_index.md
  writeup/   lb10-writeup.md  lb10-writeup.zh.md  raw/lb10-pdftotext-layout.txt
  analysis/  method_summary.md  score_tricks.md  gap_analysis.md  next_version_plan.md
  models/  datasets/  links/  notebooks/ (empty)
```

## One-paragraph takeaway
LB10 is the cleanest statement of **"improve the deterministic teacher, not the SFT hyperparameters"**: validation
accuracy is bounded by the reasoner's **oracle coverage**, so the work is in better reasoners. Its standout is a
**rotate/shift key-table bit reasoner** — model `out[i]=F(rotl(x,a),shl(x,b),shr(x,c))` and **read F from the
examples as a 3-bit-key→bit table**, recovering `(a,b,c)` from boundary bits — which lifted bit oracle **85.14% →
98.75%** with shorter, loop-free traces. Equation gains came from candidate reordering (deduce) and a two-axis guess
rebuild. Two **negative results matter for us**: **excluding failed/low-confidence traces HURT** accuracy (our c1/c2
keep only solver-correct rows), and **LoRA merge (SVD + seed soup) FAILED** to beat the single best adapter (tension
with our soup +0.01 and LB5's iterative soup). They **selected by validation, not public LB** (the lower-public,
higher-validation run won private). See `analysis/` and the `lb10-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
