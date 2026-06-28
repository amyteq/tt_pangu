# TTT solver — ARC-AGI-2

Implementation of the test-time-training pipeline from `../ttt-recipe.md`. The **model-agnostic
core is complete and validated**; the **GPU/model layer is the next step** and depends on the
compute decision (base model + where it runs).

## Pipeline
```
build 16 augmentations (D8 x color-perm)         augment.py
  -> per-task LoRA TTT on leave-one-out demos    ttt_data.py  +  [GPU layer: TODO]
  -> decode each augmented test prompt           serialize.py +  [GPU layer: TODO]
  -> de-augment predictions + PoE/vote -> top-2  selection.py
  -> {attempt_1, attempt_2} per test input       run.solve_task
```

## Modules (all stdlib, CPU, unit-tested)
| File | Role | Status |
|---|---|---|
| `augment.py` | D8 transforms + color perms, exact inverses; `build_augmentations(16)` | ✅ done |
| `serialize.py` | grid <-> compact string, task-prompt formatting | ✅ done |
| `ttt_data.py` | leave-one-out augmented TTT examples; inference prompts | ✅ done |
| `selection.py` | PoE / vote selection of the 2 pass@2 candidates | ✅ done |
| `run.py` | `solve_task(train, tests, decode_fn)` — orchestration; model injected as `DecodeFn` | ✅ done |
| `validate.py` | oracle/dummy end-to-end check on the public eval set | ✅ done |
| `model.py` | GPU layer: Qwen2.5-0.5B + per-task LoRA TTT + greedy decode → `DecodeFn` | ✅ done (runs on snorlax) |
| `run_eval.py` | run the solver over a split + score (pass@2) | ✅ done |
| `debug_decode.py` | dump what the model actually emits (decode-quality probe) | ✅ done |
| *(offline pretrain)* | give the 0.5B an ARC prior (1000 train tasks / RE-ARC) before TTT | ⏳ **TODO — the missing ingredient** |

> **Result so far (rung-1, no pretrain):** 10-task eval sample = **0/10 (0%)**. The model emits well-formed
> grids after TTT but can't induce rules with no ARC prior. The **offline pretrain** is the next gating step
> (ironbar's 0.5B reaches ~40% on ARC-1 *with* it; without it, ~0%).

## Validation (the scaffolding is correctly wired)
```sh
python solver/validate.py --decoder oracle   # -> 100.00% over 120 eval tasks (167 outputs)
python solver/validate.py --decoder dummy    # -> 0.00% (proves no score inflation)
PYTHONPATH=<pytest-target> python -m pytest tests/test_solver.py -q   # -> 23 passed
```
The oracle check is the solver analogue of the metric oracle check: a decoder that emits the
correct *augmented* output must score 100% after de-augmentation + voting — confirming
`augment.apply/invert`, prompt building, candidate de-augmentation, and selection all compose.

## The `DecodeFn` contract (how the model plugs in)
```python
DecodeFn = Callable[[str], tuple[Grid, float | None]]   # (prompt) -> (predicted_grid, logprob?)
```
`run.solve_task` builds the augmented prompts, calls `decode_fn` per augmentation, and selects
the top-2. The real model layer implements `decode_fn` as: load base model + per-task LoRA TTT
(rank 32, ~64 steps, leave-one-out augmented demos from `ttt_data`), then greedy/DFS-decode the
prompt and return `(grid, logprob)`. Nothing else in the pipeline changes.

## Next step — GPU layer (T2 cont.)
Blocked on the compute/base-model decision (see `../tasks.md`):
- **rung 1 (cheap):** Qwen2.5-0.5B on a single 4090 → honest >0% floor; fastest to a real submission.
- **rung 2:** Mistral-NeMo-8B / Qwen3-4B 4-bit + DFS+PoE → >5%, needs a one-time offline pretrain.
Once chosen, implement `decode_fn` (transformers + peft) + a Kaggle kernel that runs it offline
within 12h / L4x4, validate locally on a few eval tasks, then push.
