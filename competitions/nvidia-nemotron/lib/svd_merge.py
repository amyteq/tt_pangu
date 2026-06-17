#!/usr/bin/env python3
"""T7 SVD adapter merge: v14 (0.85) + ctx4k (0.67) + v10 (0.59) -> rank-32 LoRA.

All three are rank-32 LoRA over the SAME Nemotron-H backbone. v14 (the Unsloth
replay recipe) is a strict superset: it additionally adapts attention
(q/k/v/o_proj) and lm_head. v10/ctx4k (plain PEFT) only touch the Mamba mixer
in/out_proj + the MoE experts/shared_experts up/down_proj.

Merge policy (v14-dominant, "full strength + bounded correction"):
  - For modules in ALL THREE (the overlap): merged ΔW = SVD_rank32(
        W_V14 * ΔW_v14 + W_CTX * ΔW_ctx4k + W_V10 * ΔW_v10 )
    with v14 at full weight 1.0 so its strong deltas are preserved, the others
    a small additive nudge. Truncating the rank-<=96 sum back to rank 32 keeps
    the competition cap and is dominated by v14.
  - For v14-only modules (attention, lm_head + its base_layer): copy v14 verbatim.
  - Config is copied from v14 verbatim, so the merged adapter has byte-identical
    structure to the known-good 0.85 adapter and loads the same way in vLLM.

ΔW = (alpha/r) * B @ A ; all three have r=alpha=32 -> scaling = 1.
Rank-32 truncation uses the QR trick (never materialises the [out,in] matrix):
    Bcat=[w0 B0 | w1 B1 | w2 B2] (out x 96), Acat=[A0;A1;A2] (96 x in)
    Qb,Rb = qr(Bcat); Qa,Ra = qr(Acat.T); U,S,Vt = svd(Rb @ Ra.T)
    newB = Qb @ (U[:, :32] * S[:32]) ; newA = (Qa @ Vt[:32].T).T
"""

import argparse
import json
import os
import zipfile

import torch
from safetensors import safe_open
from safetensors.torch import save_file

LORA_SUFFIXES = (".lora_A.weight", ".lora_B.weight")


def base_of(key: str) -> str | None:
    for s in LORA_SUFFIXES:
        if key.endswith(s):
            return key[: -len(s)]
    return None


def merge_module(mats, weights, rank=32):
    """mats: list of (A[r,in], B[out,r]); weights: matching list. -> (newA, newB)."""
    a_blocks, b_blocks = [], []
    for (A, B), w in zip(mats, weights):
        a_blocks.append(A.to(torch.float32))
        b_blocks.append(B.to(torch.float32) * float(w))
    Acat = torch.cat(a_blocks, dim=0)  # [sum_r, in]
    Bcat = torch.cat(b_blocks, dim=1)  # [out, sum_r]
    Qb, Rb = torch.linalg.qr(Bcat, mode="reduced")  # Qb[out,k], Rb[k,k]
    Qa, Ra = torch.linalg.qr(Acat.t(), mode="reduced")  # Qa[in,k], Ra[k,k]
    M = Rb @ Ra.t()
    U, S, Vh = torch.linalg.svd(M, full_matrices=False)
    r = min(rank, S.shape[0])
    U32 = U[:, :r]
    S32 = S[:r]
    V32 = Vh[:r, :].t()
    newB = Qb @ (U32 * S32)  # [out, r]
    newA = (Qa @ V32).t()  # [r, in]
    if r < rank:  # pad to exactly `rank` rows/cols with zeros (keeps shape uniform)
        newA = torch.cat([newA, newA.new_zeros(rank - r, newA.shape[1])], dim=0)
        newB = torch.cat([newB, newB.new_zeros(newB.shape[0], rank - r)], dim=1)
    return newA.contiguous(), newB.contiguous()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v14", required=True)
    ap.add_argument("--ctx4k", required=True)
    ap.add_argument("--v10", required=True)
    ap.add_argument("--out", required=True, help="output dir for merged adapter")
    ap.add_argument("--w-v14", type=float, default=1.0)
    ap.add_argument("--w-ctx4k", type=float, default=0.25)
    ap.add_argument("--w-v10", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    st = "adapter_model.safetensors"
    f14 = safe_open(os.path.join(args.v14, st), framework="pt")
    fcx = safe_open(os.path.join(args.ctx4k, st), framework="pt")
    f10 = safe_open(os.path.join(args.v10, st), framework="pt")
    k14, kcx, k10 = set(f14.keys()), set(fcx.keys()), set(f10.keys())

    bases14 = {base_of(k) for k in k14 if base_of(k)}
    overlap = {
        b
        for b in bases14
        if f"{b}.lora_A.weight" in kcx
        and f"{b}.lora_B.weight" in kcx
        and f"{b}.lora_A.weight" in k10
        and f"{b}.lora_B.weight" in k10
    }
    v14_only = bases14 - overlap
    print(
        f"v14 keys={len(k14)} ctx4k={len(kcx)} v10={len(k10)} | "
        f"lora bases v14={len(bases14)} overlap={len(overlap)} "
        f"v14_only={len(v14_only)}"
    )
    print(f"weights: v14={args.w_v14} ctx4k={args.w_ctx4k} v10={args.w_v10}")

    out = {}
    # 1) copy every v14 tensor verbatim (covers v14-only modules + non-lora
    #    tensors like lm_head.base_layer.weight).
    for k in k14:
        out[k] = f14.get_tensor(k)

    # 2) overwrite the overlap lora pairs with the SVD-merged version.
    merged_n = 0
    for b in sorted(overlap):
        ak, bk = f"{b}.lora_A.weight", f"{b}.lora_B.weight"
        mats = [
            (f14.get_tensor(ak), f14.get_tensor(bk)),
            (fcx.get_tensor(ak), fcx.get_tensor(bk)),
            (f10.get_tensor(ak), f10.get_tensor(bk)),
        ]
        newA, newB = merge_module(mats, [args.w_v14, args.w_ctx4k, args.w_v10])
        # match v14's stored dtype for these lora tensors
        out[ak] = newA.to(f14.get_tensor(ak).dtype)
        out[bk] = newB.to(f14.get_tensor(bk).dtype)
        merged_n += 1
    print(f"merged {merged_n} overlap modules; copied {len(out) - 2 * merged_n} v14 tensors")

    # 3) validate before writing: key set + shapes identical to v14, all finite.
    assert set(out.keys()) == k14, "merged key set drifted from v14"
    for k in out:
        assert tuple(out[k].shape) == tuple(f14.get_slice(k).get_shape()), f"shape drift at {k}"
    for b in sorted(overlap):
        a = out[f"{b}.lora_A.weight"]
        assert a.shape[0] == 32, f"rank drift at {b}: {a.shape}"
    # spot finite-check on merged tensors (full check would touch the 704MB bf16
    # lm_head base too; that is copied verbatim from a known-good adapter).
    for b in list(sorted(overlap))[:50]:
        for suf in LORA_SUFFIXES:
            t = out[f"{b}{suf}"]
            assert torch.isfinite(t).all(), f"non-finite at {b}{suf}"

    save_file(out, os.path.join(args.out, st))
    with open(os.path.join(args.v14, "adapter_config.json")) as fh:
        cfg = json.load(fh)
    with open(os.path.join(args.out, "adapter_config.json"), "w") as fh:
        json.dump(cfg, fh, indent=2)

    zip_path = os.path.join(args.out, "submission.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(args.out, "adapter_config.json"), "adapter_config.json")
        zf.write(os.path.join(args.out, st), st)
    print(f"wrote {zip_path} ({os.path.getsize(zip_path) / 1e9:.2f} GB)")
    print("config r=%s alpha=%s tm=%s" % (cfg.get("r"), cfg.get("lora_alpha"), cfg.get("target_modules")))


if __name__ == "__main__":
    main()
