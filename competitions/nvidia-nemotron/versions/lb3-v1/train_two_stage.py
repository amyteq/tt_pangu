"""Two-stage LoRA training driver for lb3-v1 (GPU-gated; NOT executed here).

This is the *executable specification* of the LB3 headline lever — two-stage
memorize -> execute training — wired to the lb3-v1 CPU modules. It is GPU-gated and
intentionally not run in this CPU/closed-competition context; it documents the exact
sequence a future authorized down-scaled run (RTX Pro 6000, ~10-20h) would execute,
and fails loudly if invoked without torch/GPU rather than silently doing nothing.

Pipeline:
  stage 0 (CPU): build mul-pattern lookup, stage-1 drills, real+resampled traces;
  stage 1 (GPU): SFT on packed masked drills (memorize the lookup table);
  stage 2 (GPU): init from stage-1 adapter, SFT on real traces + 3K retained drills;
  package    (CPU): zip the rank<=32 adapter -> submission.zip (package_submission.py).

Run (when authorized):  python train_two_stage.py --stage all --config config.yaml
"""

from __future__ import annotations

import argparse
import sys

import drill_gen
import package_submission as pkg
from mul_pattern_lookup import build_lookup


def _require_gpu():
    try:
        import torch  # noqa: F401
    except ImportError:
        sys.exit(
            "train_two_stage.py is GPU-gated and requires torch + a CUDA GPU.\n"
            "This repo context (CPU / competition closed 2026-06-15) does NOT run it.\n"
            "It documents the two-stage sequence for a future authorized down-scaled run."
        )
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA device available; two-stage training is GPU-gated.")


def stage0_prepare(cfg):
    """CPU: build the lookup + stage-1 drill corpus + (real-data) resampled traces."""
    lut = build_lookup(
        row_cap=cfg["catalogs"]["mul_pattern_lookup"]["row_cap"],
        max_operand=cfg["catalogs"]["mul_pattern_lookup"]["max_operand"],
    )
    drills = drill_gen.build_drill_samples(
        cfg["synth"]["downscaled_targets"]["cryptarithm_pattern_drill"] // drill_gen.PACK + 1, lut=lut
    )
    print(f"[stage0] lookup signatures={len(lut.signatures())}; drill samples={len(drills)}")
    print("[stage0] real-trace build from train.csv (resample originals, leakage-excluded) -> handoff")
    return lut, drills


def stage1_memorize(cfg, drills):
    _require_gpu()
    t = cfg["training"]["two_stage"]["stage1"]
    print(
        f"[stage1] SFT on {len(drills)} packed masked drills; eff_batch={t['effective_batch_size']} "
        f"lr={t['lr']} (memorize lookup table; request masked).  -> adapter_stage1/"
    )
    raise NotImplementedError("wire to the CCE manual loop (huikang) on the GPU box")


def stage2_execute(cfg):
    _require_gpu()
    t = cfg["training"]["two_stage"]["stage2"]
    print(
        f"[stage2] init from adapter_stage1/; SFT on real traces + 3K retained drills; "
        f"eff_batch={t['effective_batch_size']}, MoE-tie={cfg['training']['moe_tie_weights']}."
    )
    raise NotImplementedError("wire to the CCE manual loop; save rank<=32 adapter")


def package(adapter_dir, out="submission.zip"):
    z = pkg.build_submission_zip(adapter_dir, out)
    print(f"[package] wrote {z}")
    return z


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["0", "1", "2", "all"], default="0")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter-dir", default="adapter_stage2")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))

    lut, drills = stage0_prepare(cfg)
    if args.stage in ("1", "all"):
        stage1_memorize(cfg, drills)
    if args.stage in ("2", "all"):
        stage2_execute(cfg)
        package(args.adapter_dir)


if __name__ == "__main__":
    main()
