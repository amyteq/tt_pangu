"""Generate a RE-ARC corpus of ARC-format tasks (CPU, local — no GPU).

Writes out_dir/<key>_<n>.json, each `{"train": [demos], "test": [1 pair]}`, sampled from the
same re-arc generator (one consistent rule per task). Feed it to pretraining with:
    solver/pretrain.py --tasks-dir <out_dir>  (optionally --mix-arc2)

    # quick sample (a few keys) to validate the pipeline
    python competitions/arc-agi2/solver/gen_rearc.py --out data/rearc_tasks --n-tasks-per-key 8 --limit-keys 5

    # full corpus (~400 keys * n_tasks_per_key tasks)
    python competitions/arc-agi2/solver/gen_rearc.py --out data/rearc_tasks --n-tasks-per-key 16
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_COMP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_COMP))

from solver.rearc import DEFAULT_REARC_DIR, generate_corpus, load_generators_verifiers  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(_COMP / "data" / "rearc_tasks"), help="output dir for task JSONs")
    ap.add_argument("--rearc-dir", default=str(DEFAULT_REARC_DIR))
    ap.add_argument("--n-tasks-per-key", type=int, default=8)
    ap.add_argument("--demos", type=int, default=4, help="train pairs per synthetic task")
    ap.add_argument("--diff-lb", type=float, default=0.0)
    ap.add_argument("--diff-ub", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit-keys", type=int, default=0, help="only the first N keys (0 = all 400)")
    args = ap.parse_args(argv)

    keys = None
    if args.limit_keys:
        g, _ = load_generators_verifiers(args.rearc_dir)
        keys = sorted(g.keys())[: args.limit_keys]

    print(f"generating RE-ARC corpus -> {args.out} (n_tasks_per_key={args.n_tasks_per_key}, demos={args.demos})")
    t0 = time.time()
    stats = generate_corpus(
        out_dir=args.out,
        rearc_dir=args.rearc_dir,
        n_tasks_per_key=args.n_tasks_per_key,
        demos=args.demos,
        diff_lb=args.diff_lb,
        diff_ub=args.diff_ub,
        seed=args.seed,
        keys=keys,
    )
    print(f"done in {time.time() - t0:.0f}s: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
