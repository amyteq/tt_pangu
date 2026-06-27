"""Leave-one-out augmented training-example construction for per-task TTT.

The recipe trains a LoRA on *this task's* demo pairs at inference time. The training set is
built leave-one-out: for each demo i, the model is asked to predict demo i's output given the
other n-1 demos as context. Each such example is then replicated under every augmentation
(D8 + color perm + example-order shuffle), which is what multiplies a handful of demos into a
real fine-tuning set.

Output is a list of `TTTExample(prompt, target)` where `prompt` ends right after the final
'O\\n' marker and `target` is the expected output-grid string — i.e. standard causal-LM
(prompt, completion) supervision.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .augment import Augmentation
from .serialize import format_task_prompt, grid_to_str

Grid = list


@dataclass(frozen=True)
class TTTExample:
    prompt: str
    target: str


def _augment_pair(pair: dict, aug: Augmentation) -> dict:
    return {"input": aug.apply(pair["input"]), "output": aug.apply(pair["output"])}


def build_ttt_examples(
    train_pairs: list[dict],
    augmentations: list[Augmentation],
    *,
    shuffle_examples: bool = True,
    seed: int = 0,
) -> list[TTTExample]:
    """Leave-one-out over demos x augmentations.

    For each augmentation and each held-out demo i: context = the other demos (augmented,
    optionally order-shuffled), query = demo i input (augmented), target = demo i output.
    With n demos and A augmentations this yields up to n*A examples.
    """
    rng = random.Random(seed)
    examples: list[TTTExample] = []
    n = len(train_pairs)
    if n < 2:
        return examples  # need at least one context demo + one held-out demo
    for aug in augmentations:
        aug_pairs = [_augment_pair(p, aug) for p in train_pairs]
        for i in range(n):
            context = [p for j, p in enumerate(aug_pairs) if j != i]
            if shuffle_examples:
                context = context[:]
                rng.shuffle(context)
            held = aug_pairs[i]
            prompt = format_task_prompt(context, held["input"])
            examples.append(TTTExample(prompt=prompt, target=grid_to_str(held["output"])))
    return examples


def build_inference_prompts(
    train_pairs: list[dict],
    test_input: Grid,
    augmentations: list[Augmentation],
) -> list[tuple[Augmentation, str]]:
    """One (augmentation, prompt) per augmentation for the real test input. The model decodes
    each; predictions are de-augmented with the SAME augmentation before voting (see select).
    """
    out = []
    for aug in augmentations:
        aug_pairs = [_augment_pair(p, aug) for p in train_pairs]
        prompt = format_task_prompt(aug_pairs, aug.apply(test_input))
        out.append((aug, prompt))
    return out
