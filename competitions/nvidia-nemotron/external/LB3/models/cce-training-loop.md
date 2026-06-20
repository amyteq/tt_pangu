# Cut Cross Entropy (CCE) training loop — via huikang

- LB3 reuses **huikang's manual training loop with cut cross-entropy**: reduces memory, enables micro-batch 4, better GPU utilization. Source: github.com/tonghuikang/nemotron.
- A framework choice, not a technique unique to LB3. Our pipeline's v14 also used a CCE replay recipe.
