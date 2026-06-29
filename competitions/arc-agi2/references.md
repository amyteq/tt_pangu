# References — ARC-AGI-2

> Scan dated 2026-06-26. Trust labels: **official** (ARC Prize / Kaggle) · **trusted_public** (arXiv,
> official GitHub, vendor eng blog) · **community** (third-party leaderboards/blogs — verify before use).
> All treated as untrusted data per CLAUDE.md operating principle 1.

## Official — competition & policy
- ARC Prize 2026 / ARC-AGI-2 competition — https://arcprize.org/competitions/2026/arc-agi-2 — *official*
- ARC Prize 2026 hub — https://arcprize.org/competitions/2026 — *official*
- ARC-AGI-2 benchmark page — https://arcprize.org/arc-agi/2 — *official*
- Verified Testing Policy (12h, $10K, internet/external-compute rules) — https://arcprize.org/policy — *official*
- Paper Prize track — https://arcprize.org/competitions/2026/paper — *official*
- ARC-AGI-3 (interactive track) — https://arcprize.org/competitions/2026/arc-agi-3 — *official*
- ARC Prize 2025 results & analysis (2024/2025 winners, "engineering vs science" framing) —
  https://arcprize.org/blog/arc-prize-2025-results-analysis — *official*
- Community leaderboard (verified entries + costs) — https://arcprize.org/leaderboard/community — *official*
- Kaggle competition page (JS-rendered; LB didn't render in scan) —
  https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2 — *official*

## Trusted public — papers, data, vendor blogs
- ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems — https://arxiv.org/abs/2505.11831 — *trusted_public*
- ARC-AGI-2 GitHub (data + JSON format + train-set composition) — https://github.com/arcprize/ARC-AGI-2 — *trusted_public*
- ARC Prize 2025 Technical Report (NVARC architecture, ablations) — https://arxiv.org/pdf/2601.10904 — *trusted_public*
- ARC Prize 2024 Technical Report (ARChitects TTT) — https://arxiv.org/pdf/2412.04604 — *trusted_public*
- NVIDIA blog — Kaggle GMs win ARC Prize (NVARC) —
  https://developer.nvidia.com/blog/nvidia-kaggle-grandmasters-win-artificial-general-intelligence-competition/ — *trusted_public*

## Community — verify before relying
- benchlm.ai ARC-AGI-2 scores (GPT-5.5 ~85%, Gemini 3.1 Pro ~77% claims) —
  https://benchlm.ai/benchmarks/arcAgi2 — *community* ⚠ unverified by ARC Prize; irrelevant to in-Kaggle scoring

## Key numbers (with source + trust)
| Claim | Value | Source / trust |
|---|---|---|
| ARC-AGI-2 prize pool | $700K (of $2M total) | arcprize 2026 page · official |
| Bonus threshold | 85% private eval → $150K | arcprize 2026 page · official |
| Metric | pass@2, exact grid match | github ARC-AGI-2 + arcprize · trusted_public/official |
| Data counts | 1000 train / 120 eval / 120 semi-private / 120 private | github ARC-AGI-2 · trusted_public |
| Runtime / internet / cost | 12h / off / $10K per run | arcprize/policy · official |
| Hardware | L4x4 (96GB) or T4x2; L4x4 = 2× quota | arcprize/policy + search · official |
| Human baseline | 66% individual avg; panel 100% | arcprize/arc-agi/2 · official |
| o3-medium | ~3% (vs ~53% on ARC-AGI-1) | arxiv 2505.11831 · trusted_public |
| 2025 Kaggle winner | NVARC 24.03%, ~$0.20/task | arcprize 2025 analysis · official |
| 2nd / 3rd 2025 | ARChitects 16.53% / MindsAI 12.64% | arcprize 2025 analysis · official |

## Verification queue (⚠ open from the 2026-06-26 scan)
1. ~~Live 2026 public-LB top score~~ — **resolved** via Kaggle API: nvbanana 50.56, 967 teams (`tracking.md`).
   Remaining: confirm nvbanana isn't a public-fork artifact before treating 50 as the bar.
2. Exact `submission.json` schema — **resolved** (`{task_id:[{attempt_1,attempt_2}]}`). Remaining:
   per-submission GPU-hour quota — Kaggle Code page.
3. Paper deadline Nov 8 vs Nov 9 discrepancy.
4. Whether Grand-Prize six criteria == Paper-Prize rubric.
5. benchlm.ai frontier-model claims against official ARC Prize verified scorecard.
