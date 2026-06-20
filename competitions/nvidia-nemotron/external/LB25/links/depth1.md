# Depth 1 — direct references from the LB25 writeup (budget ≤10; followed)

| # | ref | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | huikang | Progress-Prize winning submission (discussion) | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | discussion | JS-gated | the baseline these 5 changes improve |
| 2 | huikang | per-problem eval dashboard | https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764 | documentation | YES (static) | shows the per-problem changes |
| 3 | huikang | nemotron-adapter-private (Kaggle Model) | https://kaggle.com/models/huikang/nemotron-adapter-private | model | NO (private) | the submission adapter (title only) |
| 4 | huikang | [private] Adapter validation notebook | https://kaggle.com/code/huikang/private-adapter-validation-notebook | notebook | NO (private) | the eval notebook fixed in change #1 |
| 5 | huikang | [private] Tinker submission notebook | https://kaggle.com/code/huikang/private-tinker-submission-notebook | notebook | NO (private) | tinker submission (title only) |
| 6 | tonghuikang | GitHub repo | https://github.com/tonghuikang/nemotron | repository | YES | the Progress-Prize pipeline (`.py`), backs the dashboard `evaluation/*.jsonl` |

**Attribution conclusion:** LB25 = huikang's improvements to *his own* Progress-Prize submission. The eval-bug fix + equation reversal symmetry are the load-bearing changes; cryptarithm unsolved.
