"""LoRA SFT driver for lb6-v1 (GPU-gated; NOT executed here).

Executable specification of the LB6 training setup (method_summary.md §3): a single
Unsloth LoRA SFT on a **massive distribution-matched synthetic** corpus, **bit
over-weighted to ~69% of tokens**, validated on the real set (full-train-as-validation)
with per-domain DUMMY probing for attribution. GPU-gated; fails loudly without a GPU.

  stage 0 (CPU): distribution-matched synthetic; bit over-weight; calibrate the
                 bit/cryptarithm trade-off (tradeoff_cv.py) BEFORE committing the mix;
  train  (GPU):  Unsloth, BS 32, LR 3.5e-4, rank32/a32, 1 epoch;
  package (CPU): zip the rank<=32 adapter -> submission.zip.

Run (authorized): python train_lb6.py --config config.yaml
"""

from __future__ import annotations

import argparse
import sys

import package_submission as pkg
import tradeoff_cv


def _require_gpu():
    try:
        import torch  # noqa: F401
    except ImportError:
        sys.exit(
            "train_lb6.py is GPU-gated and requires torch + a CUDA GPU.\n"
            "This repo context (CPU / competition closed 2026-06-15) does NOT run it.\n"
            "It documents the LB6 single-epoch Unsloth SFT for a future run."
        )
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA device available; lb6-v1 training is GPU-gated.")


def stage0_calibrate(cfg):
    points = [(0.50, 0.86), (0.60, 0.90), (0.69, 0.935), (0.75, 0.95)]
    slope, intercept = tradeoff_cv.fit_sensitivity(points)
    share = cfg["synth"]["bit_token_share"]
    print(f"[stage0] bit over-weight target share={share}; calibrated bit_cv slope={slope:.3f}")
    print("[stage0] calibrate the bit/cryptarithm trade-off BEFORE committing the mix (LB6 regret).")
    return slope, intercept


def train(cfg):
    _require_gpu()
    t = cfg["training"]
    print(
        f"[train] Unsloth SFT: BS={t['effective_batch_size']} LR={t['lr']} rank={t['lora_rank']} epochs={t['epochs']}"
    )
    raise NotImplementedError(
        "wire to Unsloth (or Tinker for velocity); validate full-train-as-validation + DUMMY probe"
    )


def package(adapter_dir, out="submission.zip"):
    z = pkg.build_submission_zip(adapter_dir, out)
    print(f"[package] wrote {z}")
    return z


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter-dir", default="adapter_lb6")
    ap.add_argument("--do-train", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    stage0_calibrate(cfg)
    if args.do_train:
        train(cfg)
        package(args.adapter_dir)


if __name__ == "__main__":
    main()
