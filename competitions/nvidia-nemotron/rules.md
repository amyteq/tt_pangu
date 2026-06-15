# Rules — NVIDIA Nemotron Model Reasoning Challenge

> Facts with evidence; uncertain items marked **⚠ unverified**. Evidence: issue #86 (赛制一句话 + snapshot),
> `competitions/nvidia-nemotron/kernels/README.md`, `work/00.nemo.md`.

## Problem
9 categories of reasoning problems (incl. cryptarithm, bit-manipulation, equation/symbol transforms).
The challenge is **hidden-rule generalization**, not train-set memorization (`work/00.nemo.md` §6).

## Data
- train ~9500 rows; hidden real test set.
- Reported finding: `test.csv` ≈ first 3 rows of train (`work/00.nemo.md`; ⚠ as reported, treat with care).

## Metric
- **accuracy**: extract the `\boxed{}` answer from model output; compare by **exact match or numeric within 1e-2**.

## Submission format
- Submit a **rank ≤ 32 LoRA adapter** for base model **Nemotron-3-Nano-30B-A3B** (Mamba + MoE hybrid).
- A Kaggle GPU kernel produces `submission.zip` in `/kaggle/working`; submitted from Kaggle storage.

## Constraints
- Evaluation: **greedy decode**, `max_tokens=7680`, `temp=0`.
- Submission quota: **5 per team per day**.
- internet off; GPU kernel (`NvidiaRtxPro6000`).
- LoRA rank 32 → limited capacity (`work/00.nemo.md` 挑战 3); MoE/hybrid target-module choice is non-trivial (挑战 4).

## Deadline / schedule
- **2026-06-15 23:59 UTC** (issue #86 snapshot). ⚠ confirm on the official page.

## External data / kernel / internet / GPU rules
- Compliant **real training** of a fresh LoRA (no repack). Public Kaggle datasets used (attributed):
  `tonghuikang` corpus snapshot (recording order), `mohamedamr992/replay-math`,
  `mayukh18/nemotron-packages` (offline wheels), `llkh0a/rtx-wheels`, `dgxchen/nemotron-cot-tong` (CoT traces).
- Compliance red line (issue #86): rank≤32; real training (no repack); dual account = real registered
  teammates (buys only concurrent sessions; submissions shared per-team/day); never print/submit credentials.

## Unclear rules (⚠ unverified)
- Exact train row count (9500 vs corpus variants).
- `test.csv` = first 3 train rows claim (as reported in `work/00.nemo.md`).
- Private-LB weighting / final scoring details.
