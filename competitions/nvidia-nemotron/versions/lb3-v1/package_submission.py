"""Package a rank<=32 LoRA adapter into a competition-valid submission.zip (lb1-v1).

Submission format (rules.md / submissions.md): a rank<=32 LoRA adapter for
Nemotron-3-Nano-30B, zipped so that ``adapter_config.json`` and
``adapter_model.safetensors`` sit at the **zip root** (NOT nested under a
sub-directory). The Kaggle GPU kernel writes ``submission.zip`` to
``/kaggle/working``; this module is the local packaging + a dummy-adapter builder
so the packaging path and the preflight gate can be exercised without a GPU run.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile

REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors")


def build_submission_zip(adapter_dir: str, out_zip: str) -> str:
    """Zip the adapter files at the zip ROOT (no nesting)."""
    files = [f for f in os.listdir(adapter_dir) if os.path.isfile(os.path.join(adapter_dir, f))]
    missing = [f for f in REQUIRED_FILES if f not in files]
    if missing:
        raise FileNotFoundError(f"adapter dir missing required files: {missing}")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(adapter_dir, f), arcname=f)  # arcname=f => root-level
    return out_zip


def make_dummy_adapter(dest_dir: str, rank: int = 32) -> str:
    """Write a minimal placeholder adapter (config + tiny weights stub) for tests.

    The weights file is a placeholder (not loadable) — sufficient to exercise the
    packaging/structure/rank gates locally. A real adapter comes from the kernel.
    """
    os.makedirs(dest_dir, exist_ok=True)
    config = {
        "peft_type": "LORA",
        "r": rank,
        "lora_alpha": rank,
        "target_modules": [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "in_proj",
            "out_proj",
            "up_proj",
            "down_proj",
            "gate_proj",
        ],
        "base_model_name_or_path": "nvidia/Nemotron-3-Nano-30B-A3B",
        "task_type": "CAUSAL_LM",
    }
    with open(os.path.join(dest_dir, "adapter_config.json"), "w") as f:
        json.dump(config, f, indent=2)
    # minimal empty-safetensors (8-byte little-endian header length = 2, then "{}")
    with open(os.path.join(dest_dir, "adapter_model.safetensors"), "wb") as f:
        header = b"{}"
        f.write(len(header).to_bytes(8, "little"))
        f.write(header)
    return dest_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-dir", help="dir containing adapter_config.json + adapter_model.safetensors")
    ap.add_argument("--out", default="submission.zip")
    ap.add_argument("--dummy", action="store_true", help="build a dummy adapter first (testing)")
    args = ap.parse_args()

    adir = args.adapter_dir
    if args.dummy:
        adir = adir or "._dummy_adapter"
        make_dummy_adapter(adir)
        print(f"built dummy adapter -> {adir}")
    if not adir:
        raise SystemExit("provide --adapter-dir or --dummy")
    z = build_submission_zip(adir, args.out)
    print(f"wrote {z} ({os.path.getsize(z)} bytes)")


if __name__ == "__main__":
    main()
