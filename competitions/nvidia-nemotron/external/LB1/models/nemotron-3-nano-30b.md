# Base model — Nemotron-3-Nano-30B

- The competition base model. Submissions are **LoRA adapters (rank ≤ 32)** loaded with vLLM at eval.
- Per our repo (notes.md): a Mamba-2 / MoE-128 SSM model (in_proj/out_proj are Mamba modules; 128-expert MoE).
- LB1 LoRA targets: `q_proj, k_proj, v_proj, o_proj, in_proj, out_proj, up_proj, down_proj, gate_proj, lm_head`
  (a commenter notes vLLM does not use `lm_head` at inference → likely no score effect).
- Not downloaded (weights ≫ 20 MB; out of scope).
