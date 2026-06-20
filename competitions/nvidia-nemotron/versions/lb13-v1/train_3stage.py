"""3-stage decreasing-LR LoRA SFT driver for lb13-v1 (GPU-gated; NOT executed here).

Executable specification of the LB13 training schedule (method_summary.md §3):
  stage 0 (CPU): build improved-teacher traces, KEEP teacher-incorrect, rebalance 1:1
                 (rebalance.py), robust aggregation, cryptarithm-from-equation aug;
  stage 1 (GPU): 2 epochs, LR 2e-4 linear (align);
  stage 2 (GPU): 1 epoch,  LR 2e-5 cosine (smooth);
  stage 3 (GPU): 1 epoch,  LR 5e-6 cosine, upsample bit + cryptarithm (sharpen hard);
  package (CPU): zip the rank<=32 adapter (targets without lm_head) -> submission.zip.

GPU-gated; fails loudly without torch/GPU. Run (authorized): python train_3stage.py --stage all
"""

from __future__ import annotations

import argparse
import sys

import package_submission as pkg
import rebalance


def _require_gpu():
    try:
        import torch  # noqa: F401
    except ImportError:
        sys.exit(
            "train_3stage.py is GPU-gated and requires torch + a CUDA GPU.\n"
            "This repo context (CPU / competition closed 2026-06-15) does NOT run it.\n"
            "It documents the 3-stage decreasing-LR SFT for a future run."
        )
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA device available; lb13-v1 training is GPU-gated.")


def stage0_prepare(cfg, traces):
    bal = rebalance.rebalance_one_to_one(traces)
    bc = sum(t.get("correct") for t in bal)
    print(f"[stage0] 1:1 rebalance -> {len(bal)} traces (correct={bc}, incorrect={len(bal) - bc}; keep failures)")
    return bal


def _stage(cfg, idx):
    _require_gpu()
    s = cfg["training"]["stages"][idx]
    print(f"[stage{idx + 1}] epochs={s['epochs']} LR={s['lr']} {s['schedule']} upsample={s.get('upsample', [])}")
    raise NotImplementedError("wire to the Unsloth trainer (rank32/a32, targets without lm_head, eff batch 32)")


def package(adapter_dir, out="submission.zip"):
    z = pkg.build_submission_zip(adapter_dir, out)
    print(f"[package] wrote {z}")
    return z


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["0", "1", "2", "3", "all"], default="0")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter-dir", default="adapter_stage3")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    # placeholder teacher set; real traces come from the improved reasoners
    traces = [{"id": i, "correct": (i % 5 != 0)} for i in range(1000)]
    stage0_prepare(cfg, traces)
    for k in (1, 2, 3):
        if args.stage in (str(k), "all"):
            _stage(cfg, k - 1)
    if args.stage == "all":
        package(args.adapter_dir)


if __name__ == "__main__":
    main()
