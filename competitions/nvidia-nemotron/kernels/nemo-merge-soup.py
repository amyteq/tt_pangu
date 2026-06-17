# Nemo Merge T7 — package the SVD-merged adapter as the competition submission.
#
# The merge itself (v14 @ 1.0 + ctx4k @ 0.25 + v10 @ 0.25, per-module rank-32 SVD
# of the summed LoRA deltas over the shared Mamba/MoE modules; v14's attention +
# lm_head carried verbatim) is done by
#   kernels/nvidia-nemotron-model-reasoning-challenge/merge/svd_merge.py
# and committed to the repo for audit. Its output (adapter_config.json +
# adapter_model.safetensors) is attached to this kernel as a private dataset.
# This kernel just zips those two files into /kaggle/working/submission.zip so a
# code-competition submission can reference a kernel version. Internet off.
#
# All three source adapters were really trained by us (rank<=32, no repack of
# third-party adapters) — compliant with the issue #86 red lines / D3.
import glob
import json
import os
import zipfile

# Locate the merged adapter on the attached dataset. Prefer a path under a
# *merge* dataset so we never accidentally grab a base-model config.
cfgs = [p for p in glob.glob("/kaggle/input/**/adapter_config.json", recursive=True) if "merge" in p.lower()]
sts = [p for p in glob.glob("/kaggle/input/**/adapter_model.safetensors", recursive=True) if "merge" in p.lower()]
assert len(cfgs) == 1, f"expected exactly 1 merged adapter_config.json, got {cfgs}"
assert len(sts) == 1, f"expected exactly 1 merged adapter_model.safetensors, got {sts}"
CFG_PATH, ST_PATH = cfgs[0], sts[0]
print("merged config:", CFG_PATH)
print("merged weights:", ST_PATH, f"({os.path.getsize(ST_PATH) / 1e9:.2f} GB)")

with open(CFG_PATH) as fh:
    cfg = json.load(fh)
assert cfg.get("r") == 32 and cfg.get("lora_alpha") == 32, cfg
print("config OK: r=32 alpha=32 tm=", cfg.get("target_modules"))

os.makedirs("/kaggle/working", exist_ok=True)
OUT = "/kaggle/working/submission.zip"
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(CFG_PATH, "adapter_config.json")
    zf.write(ST_PATH, "adapter_model.safetensors")

# Validate the artifact: exactly the two expected members, sane sizes.
with zipfile.ZipFile(OUT) as zf:
    names = set(zf.namelist())
    assert names == {"adapter_config.json", "adapter_model.safetensors"}, names
    assert zf.getinfo("adapter_model.safetensors").file_size > 1_000_000_000
print(f"wrote {OUT} ({os.path.getsize(OUT) / 1e9:.2f} GB)")
print("Done.")
