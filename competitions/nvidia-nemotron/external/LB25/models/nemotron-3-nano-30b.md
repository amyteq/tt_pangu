# Base model — Nemotron-3-Nano-30B (huikang Progress-Prize lineage)

- LB25 = huikang's Progress-Prize submission + 5 improvements. LoRA (rank ≤ 32), vLLM eval (temp=0, 7680-token budget). Trained with the huikang CCE loop (`tonghuikang/nemotron` `train_sft.py`) — **our v14 derives from this lineage**.
- Exact hyperparameters of each LB25 change: `unknown` (the writeup lists changes, not a full config).
- Not downloaded (weights ≫ 20 MB; adapter is a private Kaggle model — title only).
