# Depth 1 — direct references from the 10th-place writeup (budget ≤10; 2 followed)

The writeup is unusually self-contained — the only external references are the base model and the competition.

| # | ref | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | Base model | Nemotron-3-Nano-30B-A3B-BF16 | https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | model | metadata YES | 30B MoE, ~3B active; the single base model |
| 2 | Competition | NVIDIA Nemotron Model Reasoning Challenge | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge | documentation | JS-gated | task / grader |
| 3 | (provided) | local PDF | `temp/LB10.pdf` | writeup | YES | depth-0 body |

**Attribution conclusion:** LB10's contributions are its own reasoners (rotate/shift key-table bit; candidate-ordering equation) on the common deterministic-teacher approach (@huikang-style baseline implied). No third-party code is linked.
