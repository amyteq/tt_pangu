"""Decode-quality probe: solve one task and dump what the model actually emits.

Tells us whether 0% is "hard task" vs "model isn't emitting parseable grids" (the common
failure for an un-pretrained instruct model). Prints, for the first 3 augmentations: the raw
generated text (head), the parsed grid shape, and the true output shape.

    python solver/debug_decode.py --task 0934a4d8 --ttt-steps 32 --n-aug 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_COMP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_COMP))
sys.path.insert(0, str(_COMP / "eval"))

from arc_io import load_github_split  # noqa: E402

from solver.augment import build_augmentations  # noqa: E402
from solver.model import TTTConfig, TTTSolver  # noqa: E402
from solver.ttt_data import build_inference_prompts  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=None, help="task id (default: first eval task)")
    ap.add_argument("--split", default="evaluation")
    ap.add_argument("--n-aug", type=int, default=8)
    ap.add_argument("--ttt-steps", type=int, default=32)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--pretrained-adapter", default=None)
    args = ap.parse_args(argv)

    tasks = load_github_split(args.split)
    tid = args.task or next(iter(tasks))
    t = tasks[tid]
    print(
        f"task {tid}: {len(t.train)} demos, test {t.n_test}, true out shape "
        f"{len(t.test_outputs[0])}x{len(t.test_outputs[0][0])}"
    )

    cfg = TTTConfig(
        n_augmentations=args.n_aug,
        ttt_steps=args.ttt_steps,
        max_new_tokens=args.max_new_tokens,
        pretrained_adapter=args.pretrained_adapter,
    )
    solver = TTTSolver(cfg)
    solver._reset_adapter()
    solver._train_on_task(t.train)
    print(f"ttt examples kept: {getattr(solver, 'n_ttt_examples', 'n/a')}")
    decode_fn = solver._make_decode_fn()

    augs = build_augmentations(n=args.n_aug, seed=0)
    prompts = build_inference_prompts(t.train, t.test_inputs[0], augs)
    for i, (aug, prompt) in enumerate(prompts[:3]):
        grid, logprob = decode_fn(prompt)
        # raw text (re-decode without parsing)
        import torch

        ids = solver.tok(prompt, add_special_tokens=False, return_tensors="pt").to(solver.device)
        with torch.no_grad():
            out = solver.model.generate(
                **ids, max_new_tokens=args.max_new_tokens, do_sample=False, pad_token_id=solver.tok.pad_token_id
            )
        raw = solver.tok.decode(out[0][ids["input_ids"].shape[1] :], skip_special_tokens=True)
        shape = f"{len(grid)}x{len(grid[0])}" if grid else "EMPTY"
        print(f"\n--- aug {i} (k={aug.k},flip={aug.flip}) parsed={shape} logprob={logprob} ---")
        print("RAW HEAD:", repr(raw[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
