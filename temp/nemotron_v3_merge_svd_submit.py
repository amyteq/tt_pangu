#!/usr/bin/env python3
"""
Version 3: adapter merge/SVD compression and clean submission packaging.

Use case
--------
Public notebooks in this competition often submit an already-trained adapter.
A stronger workflow is to train several adapters (different seeds, LR, CoT
mixes, or public+private adapters), merge their LoRA deltas with weights, and
compress the merged delta back to rank <= 32 via SVD. This script does that and
writes a clean submission.zip whose root contains adapter_config.json and
adapter_model.safetensors.

Examples
--------
Single adapter, clean package only:
    python nemotron_v3_merge_svd_submit.py \
        --adapters /kaggle/input/my-adapter/1 \
        --output-dir /kaggle/working/merged_adapter

Weighted merge:
    python nemotron_v3_merge_svd_submit.py \
        --adapters /kaggle/input/a/1 /kaggle/input/b/1 /kaggle/input/c/1 \
        --weights 0.50 0.30 0.20 \
        --rank 32

Environment default
-------------------
If no --adapters is provided, ADAPTERS can be a semicolon-separated list. If
that is also absent, the script falls back to the commonly used public Tinker
adapter path, so it can replace the trivial zip-only notebooks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import torch

try:
    from safetensors.torch import load_file as safe_load_file
    from safetensors.torch import save_file as safe_save_file
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Please install safetensors to use this script") from exc

DEFAULT_PUBLIC_ADAPTER = "/kaggle/input/models/kienngx/nemotron-nano-30b-trained/triton/tinker-adapter/1"


class AdapterLoadError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge LoRA adapters and create Kaggle submission.zip")
    env_adapters = [p for p in os.getenv("ADAPTERS", "").split(";") if p.strip()]
    default_adapters = env_adapters or ([DEFAULT_PUBLIC_ADAPTER] if Path(DEFAULT_PUBLIC_ADAPTER).exists() else [])
    parser.add_argument("--adapters", nargs="*", default=default_adapters, help="Adapter directories to merge")
    parser.add_argument("--weights", nargs="*", type=float, default=None, help="Merge weights; defaults to uniform")
    parser.add_argument("--rank", type=int, default=int(os.getenv("RANK", "32")), help="Output LoRA rank, must be <=32")
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "/kaggle/working/adapter_v3_merged_svd"))
    parser.add_argument("--zip-path", default=os.getenv("ZIP_PATH", "/kaggle/working/submission.zip"))
    parser.add_argument(
        "--drop-lm-head",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Drop lm_head/modules_to_save tensors; the evaluation adapter normally expects only LoRA modules.",
    )
    parser.add_argument(
        "--copy-if-single",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For one adapter, copy files unchanged instead of SVD recompression. Off by default for clean rank enforcement.",
    )
    return parser.parse_args()


def normalize_weights(weights: Optional[List[float]], n: int) -> List[float]:
    if n <= 0:
        raise ValueError("No adapter paths were provided. Use --adapters or ADAPTERS='path1;path2'.")
    if weights is None or len(weights) == 0:
        return [1.0 / n] * n
    if len(weights) != n:
        raise ValueError(f"Expected {n} weights, got {len(weights)}")
    s = sum(weights)
    if abs(s) < 1e-12:
        raise ValueError("Weights sum to zero")
    return [w / s for w in weights]


def adapter_weight_file(adapter_dir: Path) -> Path:
    candidates = [
        adapter_dir / "adapter_model.safetensors",
        adapter_dir / "pytorch_model.safetensors",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Some Kaggle zips have nested directories; search one level deeper.
    found = list(adapter_dir.glob("**/adapter_model.safetensors"))
    if found:
        return found[0]
    raise AdapterLoadError(f"Could not find adapter_model.safetensors under {adapter_dir}")


def adapter_config_file(adapter_dir: Path) -> Path:
    candidates = [adapter_dir / "adapter_config.json"] + list(adapter_dir.glob("**/adapter_config.json"))
    for p in candidates:
        if p.exists():
            return p
    raise AdapterLoadError(f"Could not find adapter_config.json under {adapter_dir}")


def load_adapter(adapter_dir: str) -> Tuple[dict, Dict[str, torch.Tensor], Path]:
    d = Path(adapter_dir)
    if not d.exists():
        raise AdapterLoadError(f"Adapter directory does not exist: {d}")
    cfg_path = adapter_config_file(d)
    weight_path = adapter_weight_file(d)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    state = safe_load_file(str(weight_path), device="cpu")
    print(f"Loaded {d}: {len(state)} tensors from {weight_path.name}, r={cfg.get('r')}, alpha={cfg.get('lora_alpha')}")
    return cfg, dict(state), cfg_path.parent


def is_lm_head_key(key: str) -> bool:
    return "lm_head" in key or "modules_to_save" in key


def lora_pair_base(key: str, part: str) -> Optional[str]:
    # Handles common PEFT keys such as:
    # base_model.model.layers.0.mixer.in_proj.lora_A.default.weight
    needle = f".lora_{part}."
    if needle not in key or not key.endswith(".weight"):
        return None
    return key.split(needle)[0]


def collect_pairs(state: Mapping[str, torch.Tensor], drop_lm_head: bool) -> Dict[str, Tuple[str, str]]:
    a_by_base: Dict[str, str] = {}
    b_by_base: Dict[str, str] = {}
    for k in state:
        if drop_lm_head and is_lm_head_key(k):
            continue
        a_base = lora_pair_base(k, "A")
        b_base = lora_pair_base(k, "B")
        if a_base is not None:
            a_by_base[a_base] = k
        if b_base is not None:
            b_by_base[b_base] = k
    bases = sorted(set(a_by_base) & set(b_by_base))
    return {base: (a_by_base[base], b_by_base[base]) for base in bases}


def module_scaling(config: Mapping[str, object]) -> float:
    r = float(config.get("r", 1) or 1)
    alpha = float(config.get("lora_alpha", r) or r)
    return alpha / r


def merge_and_svd(
    adapters: List[Tuple[dict, Dict[str, torch.Tensor], Path]], weights: List[float], rank: int, drop_lm_head: bool
) -> Dict[str, torch.Tensor]:
    if rank > 32:
        raise ValueError("Competition output rank must be <= 32")

    ref_cfg, ref_state, _ = adapters[0]
    ref_pairs = collect_pairs(ref_state, drop_lm_head=drop_lm_head)
    if not ref_pairs:
        raise AdapterLoadError("No LoRA A/B tensor pairs found in the first adapter")

    merged_state: Dict[str, torch.Tensor] = {}
    missing_report: List[str] = []

    for base, (ref_a_key, ref_b_key) in ref_pairs.items():
        delta_sum: Optional[torch.Tensor] = None
        out_dtype = ref_state[ref_a_key].dtype

        for (cfg, state, _root), w in zip(adapters, weights):
            pairs = collect_pairs(state, drop_lm_head=drop_lm_head)
            if base not in pairs:
                missing_report.append(f"{base} missing in one adapter; skipped that adapter for this module")
                continue
            a_key, b_key = pairs[base]
            A = state[a_key].float()  # [r, in]
            B = state[b_key].float()  # [out, r]
            delta = (B @ A) * module_scaling(cfg) * float(w)
            delta_sum = delta if delta_sum is None else delta_sum + delta

        if delta_sum is None:
            continue

        # Full SVD is fine here because LoRA target matrices are manageable, and this is a one-off packaging step.
        U, S, Vh = torch.linalg.svd(delta_sum, full_matrices=False)
        r_eff = min(rank, S.numel())
        U_r = U[:, :r_eff]
        S_r = S[:r_eff]
        Vh_r = Vh[:r_eff, :]

        # We set output alpha = rank, so scaling alpha/r = 1. Then B_new @ A_new approximates delta_sum.
        A_new = Vh_r.contiguous().to(dtype=out_dtype)
        B_new = (U_r * S_r.unsqueeze(0)).contiguous().to(dtype=out_dtype)
        merged_state[ref_a_key] = A_new
        merged_state[ref_b_key] = B_new

    if missing_report:
        print("Warnings:")
        for msg in sorted(set(missing_report))[:20]:
            print(" -", msg)
        if len(set(missing_report)) > 20:
            print(f" - ... {len(set(missing_report)) - 20} more")

    print(f"Merged {len(merged_state)//2} LoRA modules at rank <= {rank}")
    return merged_state


def write_adapter_config(ref_config: dict, output_dir: Path, rank: int, drop_lm_head: bool) -> None:
    cfg = dict(ref_config)
    cfg["r"] = rank
    cfg["lora_alpha"] = rank
    cfg["inference_mode"] = True
    # Keep target_modules from reference; remove non-LoRA modules if requested.
    if drop_lm_head:
        cfg.pop("modules_to_save", None)
    with open(output_dir / "adapter_config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)


def copy_single_adapter(adapter_root: Path, output_dir: Path, drop_lm_head: bool) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = adapter_config_file(adapter_root)
    weight_path = adapter_weight_file(adapter_root)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    state = safe_load_file(str(weight_path), device="cpu")
    if drop_lm_head:
        state = {k: v for k, v in state.items() if not is_lm_head_key(k)}
        cfg.pop("modules_to_save", None)
    safe_save_file(state, str(output_dir / "adapter_model.safetensors"))
    with open(output_dir / "adapter_config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)


def make_readme(output_dir: Path, adapter_paths: Iterable[str], weights: Iterable[float], rank: int) -> None:
    lines = [
        "# Nemotron LoRA submission adapter\n",
        "Generated by nemotron_v3_merge_svd_submit.py.\n",
        f"Output rank: {rank}\n",
        "\n## Inputs\n",
    ]
    for p, w in zip(adapter_paths, weights):
        lines.append(f"- weight={w:.6f}: `{p}`\n")
    (output_dir / "README.md").write_text("".join(lines), encoding="utf-8")


def zip_dir(output_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for name in files:
                full = Path(root) / name
                zf.write(full, str(full.relative_to(output_dir)))
    print(f"Created {zip_path}")


def main() -> None:
    args = parse_args()
    adapter_paths = [str(Path(p)) for p in args.adapters if str(p).strip()]
    weights = normalize_weights(args.weights, len(adapter_paths))
    output_dir = Path(args.output_dir)
    zip_path = Path(args.zip_path)

    if args.rank > 32:
        raise ValueError("--rank must be <= 32 for this competition")

    adapters = [load_adapter(p) for p in adapter_paths]

    if len(adapters) == 1 and args.copy_if_single:
        copy_single_adapter(Path(adapter_paths[0]), output_dir, drop_lm_head=args.drop_lm_head)
    else:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        merged_state = merge_and_svd(adapters, weights, rank=args.rank, drop_lm_head=args.drop_lm_head)
        safe_save_file(merged_state, str(output_dir / "adapter_model.safetensors"))
        write_adapter_config(adapters[0][0], output_dir, rank=args.rank, drop_lm_head=args.drop_lm_head)

    make_readme(output_dir, adapter_paths, weights, args.rank)
    zip_dir(output_dir, zip_path)


if __name__ == "__main__":
    main()
