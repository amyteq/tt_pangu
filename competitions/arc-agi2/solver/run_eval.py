"""Run the TTT solver over a split and score it locally (pass@2).

    # smoke: a few tasks first
    python competitions/arc-agi2/solver/run_eval.py --split evaluation --limit 3 --ttt-steps 24

    # full public-eval run
    python competitions/arc-agi2/solver/run_eval.py --split evaluation --out sub_eval.json

Designed to run on a GPU box (snorlax). Heavy deps (torch/transformers/peft) load only when
the solver is constructed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_COMP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_COMP))
sys.path.insert(0, str(_COMP / "eval"))

from arc_io import load_github_split, load_solutions  # noqa: E402
from metric import score_submission  # noqa: E402

from solver.model import TTTConfig, TTTSolver  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="evaluation", choices=["training", "evaluation"])
    ap.add_argument("--limit", type=int, default=0, help="limit #tasks (0 = all)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--n-aug", type=int, default=16)
    ap.add_argument("--ttt-steps", type=int, default=48)
    ap.add_argument("--lora-rank", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-new-tokens", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pretrained-adapter", default=None, help="dir of an offline-pretrained LoRA")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", help="write submission.json here")
    args = ap.parse_args(argv)

    tasks = load_github_split(args.split)
    sols = load_solutions(tasks)
    items = list(tasks.items())
    if args.limit:
        items = items[: args.limit]

    cfg = TTTConfig(
        model_name=args.model,
        lora_rank=args.lora_rank,
        ttt_steps=args.ttt_steps,
        ttt_lr=args.lr,
        n_augmentations=args.n_aug,
        max_new_tokens=args.max_new_tokens,
        seed=args.seed,
        pretrained_adapter=args.pretrained_adapter,
    )
    print(f"loading {cfg.model_name} on {args.device} ...", flush=True)
    t0 = time.time()
    solver = TTTSolver(cfg, device=args.device)
    print(f"loaded in {time.time() - t0:.1f}s; solving {len(items)} tasks", flush=True)

    submission = {}
    for i, (tid, t) in enumerate(items):
        ts = time.time()
        submission[tid] = solver.solve(t.train, t.test_inputs)
        dt = time.time() - ts
        solved = ""
        if t.test_outputs is not None and tid in sols:
            r = score_submission({tid: submission[tid]}, {tid: sols[tid]})
            solved = f" pass@2={r.score:.2f}"
        print(f"[{i + 1}/{len(items)}] {tid} {dt:.1f}s{solved}", flush=True)

    if args.out:
        Path(args.out).write_text(json.dumps(submission))
        print(f"wrote {args.out}", flush=True)

    sub_sols = {tid: sols[tid] for tid, _ in items if tid in sols}
    if sub_sols:
        report = score_submission(submission, sub_sols)
        print("\n" + str(report), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
