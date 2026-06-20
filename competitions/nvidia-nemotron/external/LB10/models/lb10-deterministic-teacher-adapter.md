# LB10 LoRA adapter (deterministic-teacher imitation)

- A single LoRA adapter SFT'd to imitate program-generated deterministic reasoning traces. **Score is bounded by the teacher's oracle coverage** (the writeup's central thesis).
- alpha/r=4 to follow the deterministic CoT strongly; priority 2× for fragile modes; low-logprob problems added and retrained.
- **LoRA merge / seed soup FAILED** to beat the single best adapter (rank-32 SVD can't extract complementarity; soup → worst member).
- Not downloaded (weights ≫ 20 MB; not publicly linked).
