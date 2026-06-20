"""LoRA SFT driver for lb10-v1 (GPU-gated; NOT executed here).

Executable specification of the LB10 training setup (method_summary.md): a single
base model + LoRA (**alpha/r = 4**, i.e. rank-32/alpha-128), all-proj + lm_head, LR
2e-4 linear, **2 epochs**, eff batch 32, stratified. "Improve the teacher" first:
build deterministic traces (bit key-table + equation + others), **keep failed/low-conf
traces**, priority-2x the fragile (low-logprob) modes, and **select by validation**.

GPU-gated; fails loudly without torch/GPU. The two LB10 A/Bs (keep-failures vs
verified-only; LoRA-merge when it helps) are wired as flags. Run (authorized):
    python train_lb10.py --config config.yaml --do-train
"""

from __future__ import annotations

import argparse
import sys

import corpus
import learnability
import package_submission as pkg


def _require_gpu():
    try:
        import torch  # noqa: F401
    except ImportError:
        sys.exit(
            "train_lb10.py is GPU-gated and requires torch + a CUDA GPU.\n"
            "This repo context (CPU / competition closed 2026-06-15) does NOT run it.\n"
            "It documents the LB10 alpha/r=4, 2-epoch SFT for a future run."
        )
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA device available; lb10-v1 training is GPU-gated.")


def stage0_prepare(cfg, keep_failures=True):
    recs = corpus.build_demo_corpus(cfg["training"].get("corpus_size", 4000))
    if not keep_failures:
        recs = [r for r in recs if r.get("solved")]  # the verified-only A/B arm
    cov = learnability.oracle_coverage(recs)
    kept = len(recs)
    print(
        f"[stage0] corpus={kept} (keep_failures={keep_failures}); oracle ceiling per cat={ {c: f'{o}/{t}' for c, (o, t) in cov.items()} }"
    )
    return recs


def train(cfg, merge=False):
    _require_gpu()
    t = cfg["training"]
    print(
        f"[train] LoRA r={t['lora_rank']} alpha={t['lora_alpha']} (alpha/r={t['lora_alpha'] // t['lora_rank']}) "
        f"LR={t['lr']} epochs={t['epochs']} eff_batch={t['effective_batch_size']} stratified={t['stratified']}"
    )
    if merge:
        print("[train] LoRA-merge A/B arm (LB10 reported merge FAILED — characterize when soup helps)")
    raise NotImplementedError(
        "wire to the trainer; export per-example logprobs (learnability.py) + select by validation"
    )


def package(adapter_dir, out="submission.zip"):
    z = pkg.build_submission_zip(adapter_dir, out)
    print(f"[package] wrote {z}")
    return z


def main():
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter-dir", default="adapter_lb10")
    ap.add_argument("--no-keep-failures", action="store_true", help="verified-only A/B arm")
    ap.add_argument("--merge", action="store_true", help="LoRA-merge A/B arm")
    ap.add_argument("--do-train", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    stage0_prepare(cfg, keep_failures=not args.no_keep_failures)
    if args.do_train:
        train(cfg, merge=args.merge)
        package(args.adapter_dir)


if __name__ == "__main__":
    main()
