"""Pipeline driver — ties the model-agnostic core into a full per-task solve.

The GPU/model layer is injected as a `DecodeFn`: given an inference prompt it returns a
decoded grid (in the prompt's augmented frame) and an optional log-prob. This keeps the
orchestration testable on CPU (inject an oracle/dummy decoder) and lets the real model
(per-task LoRA TTT + DFS decode) plug in unchanged once a base model + compute are chosen.

    DecodeFn = Callable[[str], tuple[Grid, float | None]]

`solve_task` does: build A augmented inference prompts -> decode each -> wrap as Candidates
(carrying the augmentation so predictions de-augment correctly) -> PoE/vote select top-2.
"""

from __future__ import annotations

from typing import Callable

from .augment import build_augmentations
from .selection import Candidate, select_top2, to_submission_entry
from .ttt_data import build_inference_prompts

Grid = list
DecodeFn = Callable[[str], tuple]  # (prompt) -> (Grid, Optional[float])


def solve_task(
    train_pairs: list[dict],
    test_inputs: list[Grid],
    decode_fn: DecodeFn,
    *,
    n_augmentations: int = 16,
    seed: int = 0,
) -> list[dict]:
    """Return one Kaggle attempt dict ({attempt_1, attempt_2}) per test input."""
    augs = build_augmentations(n=n_augmentations, seed=seed)
    entries = []
    for test_input in test_inputs:
        prompts = build_inference_prompts(train_pairs, test_input, augs)
        cands: list[Candidate] = []
        for aug, prompt in prompts:
            grid, logprob = decode_fn(prompt)
            if grid:  # skip empty/failed decodes
                cands.append(Candidate(aug=aug, grid=grid, logprob=logprob))
        top2 = select_top2(cands)
        entries.append(to_submission_entry(top2))
    return entries
