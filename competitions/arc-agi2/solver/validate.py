"""End-to-end validation of the solver scaffolding with an ORACLE decoder.

This proves the augment -> infer -> de-augment -> select -> submission pipeline is wired
correctly: a decoder that always emits the correct (augmented) output must score 100% after
de-augmentation + voting. It is the solver-level analogue of the metric oracle check.

    python competitions/arc-agi2/solver/validate.py --split evaluation --n 16

Also offers a `--decoder dummy` mode (emits the augmented test input unchanged -> ~0%) to
confirm the pipeline does NOT inflate scores.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_COMP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_COMP))  # for `solver.*`
sys.path.insert(0, str(_COMP / "eval"))  # for arc_io / metric

from arc_io import load_github_split, load_solutions  # noqa: E402
from metric import score_submission  # noqa: E402

from solver.augment import build_augmentations  # noqa: E402
from solver.run import solve_task  # noqa: E402
from solver.ttt_data import build_inference_prompts  # noqa: E402


def make_prompt_lookup_decoder(train_pairs, test_inputs, test_outputs, n_aug, seed, mode):
    """Build a decode_fn keyed by exact prompt string. `mode`:
    - 'oracle': returns the augmented ground-truth output for each augmented prompt
    - 'dummy' : returns the augmented test input (a wrong-shape-ish stand-in) -> ~0%
    Because build_inference_prompts is deterministic, the prompts here match those solve_task
    rebuilds with the same (n_aug, seed).
    """
    augs = build_augmentations(n=n_aug, seed=seed)
    table: dict[str, tuple] = {}
    for ti, test_input in enumerate(test_inputs):
        prompts = build_inference_prompts(train_pairs, test_input, augs)
        for aug, prompt in prompts:
            if mode == "oracle":
                table[prompt] = (aug.apply(test_outputs[ti]), 0.0)
            else:  # dummy
                table[prompt] = (aug.apply(test_input), 0.0)

    def decode_fn(prompt: str):
        return table.get(prompt, ([], None))

    return decode_fn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="evaluation", choices=["training", "evaluation"])
    ap.add_argument("--n", type=int, default=16, help="number of augmentations")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--decoder", default="oracle", choices=["oracle", "dummy"])
    ap.add_argument("--limit", type=int, default=0, help="limit #tasks (0 = all)")
    args = ap.parse_args(argv)

    tasks = load_github_split(args.split)
    sols = load_solutions(tasks)
    items = list(tasks.items())
    if args.limit:
        items = items[: args.limit]

    submission = {}
    for tid, t in items:
        if t.test_outputs is None:
            continue
        decode_fn = make_prompt_lookup_decoder(t.train, t.test_inputs, t.test_outputs, args.n, args.seed, args.decoder)
        submission[tid] = solve_task(t.train, t.test_inputs, decode_fn, n_augmentations=args.n, seed=args.seed)

    sub_sols = {tid: sols[tid] for tid, _ in items if tid in sols}
    report = score_submission(submission, sub_sols)
    print(f"decoder={args.decoder}  n_aug={args.n}  tasks={len(submission)}")
    print(report)
    if args.decoder == "oracle" and abs(report.score - 1.0) > 1e-9:
        print("FAIL: oracle did not reach 100% — pipeline mis-wired")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
