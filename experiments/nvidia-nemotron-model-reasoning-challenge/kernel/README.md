# Nemotron Model Reasoning Challenge — LoRA SFT kernel

Kaggle GPU notebook that fine-tunes a **rank-32 LoRA** adapter for
`metric/nemotron-3-nano-30b-a3b-bf16` and writes `submission.zip` to
`/kaggle/working`. Driven via `kca kaggle push` / submitted from Kaggle storage
with `kca kaggle submit --kernel <slug> --version <v> --file submission.zip`.

## Files
- `nemotron-lora-baseline.py` — **source of truth** (percent-format `# %%` cells).
- `nemotron-lora-baseline.ipynb` — generated from the `.py` via `kca nb to-ipynb`
  (same stem); build artifact, gitignored, do not hand-edit.
- `kernel-metadata.json` — sources (competition + `dgxchen/nemotron-cot-tong` +
  `ryanholbrook/nvidia-utility-script`), `NvidiaRtxPro6000`, internet off.
- `validate_kernel.py` — **pre-push, no-GPU** validation (run before every push).

## Recipe
Train on **CoT reasoning traces** (`dgxchen/nemotron-cot-tong`, attributed), chat-
templated (`… </think> \boxed{answer}`), **response-only loss masking**, seq 4096,
α=32, LR 2e-4 cosine. Metric = accuracy of the extracted `\boxed{}` answer.

## Score progression (public LB)
| ver | change | LB |
|----|--------|----|
| identity | untrained adapter | 0.47 |
| v5 | bare-answer SFT, 120 steps | 0.61 |
| v6 | CoT but loss over prompt+padding (bug) | 0.44 |
| v7 | CoT + response-only masking, 400 steps | **0.65** |
| v9 | + held-out eval + fail-fast preflight | (running) |

## Hard-won gotchas (why the guards below exist)
- **ptxas-blackwell** is non-executable on the read-only mount and the bundled
  Triton ignores `TRITON_PTXAS_PATH` → copy to `/tmp`, `chmod +x`, set
  `TRITON_PTXAS_BLACKWELL_PATH`, and monkeypatch `get_ptxas_version`.
- Kaggle data mounts at `/kaggle/input/competitions/<slug>/` (resolve with a glob).
- `apply_chat_template(..., return_tensors="pt")` can return a `BatchEncoding`
  (no `.shape`) → pass `return_dict=True` and index `["input_ids"]`.

## Failure-prevention (each cost a ~2h GPU run once)
1. **Static lint** (`kca kaggle push` gate / `validate_kernel.py`): `ruff` F821 —
   catches undefined-name typos (e.g. the v7 `texts` NameError) in seconds.
2. **Fail-fast preflight**: the generate/eval path runs on ONE example right after
   model load, *before* the long train — runtime bugs (e.g. the v8 `.shape` error)
   surface in minutes, not after ~2h.
3. **Isolated eval**: the held-out accuracy eval is wrapped so a failure there can
   never mislabel a successful train or waste the saved adapter.

## Rebuild + validate
```
kca nb to-ipynb nemotron-lora-baseline.py        # regenerate the .ipynb (same stem)
python validate_kernel.py <path/to/problem_ids_matched.csv>   # E9/F821 lint + masking
```
