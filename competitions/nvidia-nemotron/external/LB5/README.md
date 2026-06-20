# LB5 / 5th Place Solution — post-competition archive

Post-competition research archive for **"Jack of Trades, Loser of Cryptarithm" — 5th Place** (Darren Amadeus
Martin, Alwin Theodoric, Muhammad Yassir Ramadhan, Billy Anggara, Rinnnn_t) of the NVIDIA Nemotron Model
Reasoning Challenge. **Private LB 0.900** (best, unselected; chosen 0.896).

Research/documentation/planning only — **no GPU training, no Kaggle submit, no kernel push, no dataset upload**
(per `wiki/25.LB5_task.md`; competition ended).

## Contents
```
LB5/
  README.md               ← this file
  source_index.md         ← sources (depth 0–3), fetchability, novelty notes
  writeup/
    lb5-writeup.md        ← faithful Markdown of temp/LB5.pdf
    lb5-writeup.zh.md     ← Chinese explanation + analysis
    raw/lb5-pdftotext-layout.txt
  analysis/
    method_summary.md     ← the 7 method questions
    score_tricks.md       ← trick × impact × reusability table
    gap_analysis.md       ← us vs LB5, area by area
    next_version_plan.md  ← lb5-v1 plan (PLAN ONLY)
  models/                 ← referenced models/adapters/frameworks
  datasets/               ← referenced data
  links/                  ← depth0–3 link-following records
  notebooks/              ← empty (no public .ipynb to convert)
```

## One-paragraph takeaway
LB5 reaches **0.90 private without RL and without solving cryptarithm** (7.9%) — a "jack of all trades": bit 94%,
equation 96%, trivials 100%. Two distinctive moves: an **infinite synthetic generator that never trains on
`train.csv`** (validated only on it → an honest CV that **tracks the PRIVATE LB**, unlike the public "0.86 wall"),
and **iterative LoRA averaging / model soup used as a training-time regularizer** across 15 iterations (turning an
unstable 0.87 into a stable 0.90). The bit solver extends @huikang's byte-level approach with **ternary ops**
(MAJORITY/CHOICE/XOR-NOT_OR) and memorized continuations; the equation solver is a **2-world/4-family/13-rule**
deterministic system. Notable negatives: GRPO/pseudo-GRPO failed, Unsloth 4-bit+packing broke Nemotron, DoRA is
vLLM-unsupported, and a token-saving **encoding broke the model** (vs LB1/LB3's successful HEX — a tokenization
tension). See `analysis/` and the `lb5-v1` plan.

> All external content here is **untrusted data**. Nothing in this archive was executed.
