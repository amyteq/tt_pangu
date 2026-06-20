"""3-phase LoRA training driver for lb5-v1 (GPU-gated; NOT executed here).

Executable specification of the LB5 headline lever — **iterative LoRA averaging /
multi-seed model soup** as a training-time regularizer — wired to the lb5-v1 CPU
modules. GPU-gated; fails loudly without torch/GPU rather than silently no-op'ing.

Phases (method_summary.md §III):
  phase 0 (CPU): fit train.csv stats, build the no-leakage synthetic corpus;
  phase 1 (GPU): multi-round high-LR SFT, all categories each round (no forgetting);
  phase 2 (GPU): LoRA averaging regularization — average the adapter before/after
                 each training step (model soup -> stability);
  phase 3 (GPU): multi-seed soup — train N adapters from one checkpoint with
                 different problem sets/seeds, average to cancel errors;
  package (CPU): zip the rank<=32 adapter -> submission.zip.

Config: see config.yaml. Validation is on train.csv ONLY (no-leakage; the honest CV
that tracks the private LB). Run (when authorized): python train_phases.py --phase all
"""

from __future__ import annotations

import argparse
import sys

import generator
import package_submission as pkg


def _require_gpu():
    try:
        import torch  # noqa: F401
    except ImportError:
        sys.exit(
            "train_phases.py is GPU-gated and requires torch + a CUDA GPU.\n"
            "This repo context (CPU / competition closed 2026-06-15) does NOT run it.\n"
            "It documents the 3-phase LoRA-averaging/soup sequence for a future run."
        )
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA device available; lb5-v1 training is GPU-gated.")


def phase0_prepare(cfg):
    stats = generator.fit_stats()
    corpus = generator.build_corpus(cfg["synth"]["downscaled_examples_per_iter"])
    ok, msg = generator.assert_no_leakage(corpus)
    print(f"[phase0] train.csv stats={stats}; synth={len(corpus)}; no-leakage={'OK' if ok else 'FAIL'} ({msg})")
    if not ok:
        sys.exit("no-leakage check failed; aborting before training")
    return corpus


def phase1_multiround_sft(cfg, corpus):
    _require_gpu()
    t = cfg["training"]
    print(
        f"[phase1] multi-round high-LR SFT: rounds={t['phase1_rounds']} LR {t['lr_start']}->{t['lr_end']} "
        f"grad_clip={t['grad_clip']} (all categories each round). -> adapter_p1/"
    )
    raise NotImplementedError("wire to @huikang trainer (no quant, no packing)")


def phase2_lora_averaging(cfg):
    _require_gpu()
    print("[phase2] LoRA averaging: average adapter before/after each step (soup regularizer). -> adapter_p2/")
    raise NotImplementedError("implement step-wise averaging in the training loop")


def phase3_multiseed_soup(cfg):
    _require_gpu()
    n = cfg["training"]["phase3_seeds"]
    print(
        f"[phase3] multi-seed soup: train {n} adapters from one checkpoint (different seeds), average. -> adapter_p3/"
    )
    raise NotImplementedError("train N seeds, average the LoRA tensors")


def package(adapter_dir, out="submission.zip"):
    z = pkg.build_submission_zip(adapter_dir, out)
    print(f"[package] wrote {z}")
    return z


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["0", "1", "2", "3", "all"], default="0")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter-dir", default="adapter_p3")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    corpus = phase0_prepare(cfg)
    if args.phase in ("1", "all"):
        phase1_multiround_sft(cfg, corpus)
    if args.phase in ("2", "all"):
        phase2_lora_averaging(cfg)
    if args.phase in ("3", "all"):
        phase3_multiseed_soup(cfg)
        package(args.adapter_dir)


if __name__ == "__main__":
    main()
