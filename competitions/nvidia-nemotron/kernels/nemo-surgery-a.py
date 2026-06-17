# ruff: noqa: E402  (Kaggle kernel: imports follow env/setup cells)
# Nemo Surgery A — post-hoc Spectral Surgery on the 0.86 model-soup adapter.
#
# Training-free refinement (arXiv 2603.03995 "Spectral Surgery"; the public
# lopure/amplify-top-50-singular-value-retain-84.4%-energy notebook is an instance):
# per LoRA module, take the efficient rank-r SVD of the delta B@A, REWEIGHT the
# singular values (amplify the dominant directions / truncate the low-energy tail)
# while keeping the learned directions fixed, then re-factor back to a rank-32 LoRA
# (rank-preserving → submission-compliant). Several reweighting configs are swept and
# each is scored on the fixed category-stratified hard-val set with the OFFICIAL metric
# (eval/hard_val_ids.json + eval/official_metric.py). The best variant that beats the
# untouched soup on hard-val is packaged as submission.zip. NO new training.
import glob
import site

_cutlass = glob.glob("/kaggle/usr/lib/notebooks/ryanholbrook/*nvidia*util*/nvidia_cutlass_dsl/python_packages")
for _p in _cutlass:
    site.addsitedir(_p)

import os
import shutil
import stat as _stat

_ptxas = glob.glob("/kaggle/usr/lib/notebooks/ryanholbrook/*/triton/backends/nvidia/bin/ptxas-blackwell")
if _ptxas:
    _dst = "/tmp/ptxas-blackwell"
    try:
        shutil.copy2(_ptxas[0], _dst)
        os.chmod(_dst, os.stat(_dst).st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)
        os.environ["TRITON_PTXAS_BLACKWELL_PATH"] = _dst
        os.environ["TRITON_PTXAS_PATH"] = _dst
        print("ptxas-blackwell ->", _dst)
    except OSError as _e:
        print("ptxas copy failed:", _e)

# %%
# Surgery configs to sweep. Each reweights the singular values of every (or only the
# Mamba in_proj/out_proj) LoRA delta. "scale" multiplies all SVs; "energy"+"amp" keeps
# the top SVs up to `energy` cumulative Frobenius energy (zeroing the tail) and
# multiplies the kept ones by `amp`. The first entry is the untouched-soup baseline.
SURGERY_CONFIGS = [
    {"name": "soup_baseline", "mode": "identity"},
    {"name": "scale_0.90", "mode": "scale", "scale": 0.90},
    {"name": "scale_1.15", "mode": "scale", "scale": 1.15},
    {"name": "scale_1.30", "mode": "scale", "scale": 1.30},
    {"name": "denoise_e0.95", "mode": "energy", "energy": 0.95, "amp": 1.0},
    {"name": "lopure_e0.844_a1.25", "mode": "energy", "energy": 0.844, "amp": 1.25},
    {"name": "lopure_e0.844_a1.50", "mode": "energy", "energy": 0.844, "amp": 1.50},
    {
        "name": "mamba_e0.95_a1.30",
        "mode": "energy",
        "energy": 0.95,
        "amp": 1.30,
        "modules": ["in_proj", "out_proj"],
    },
]
import time as _time

T0 = _time.time()
EVAL_DEADLINE_SEC = 21600  # 6h guard; always reach the save+zip

# Fixed category-stratified hard-val IDs (eval/hard_val_ids.json; hard + anchors).
EVAL_IDS = set(
    [
        "034930e2",
        "094de91f",
        "145c9296",
        "18544cb0",
        "221798d9",
        "2411f83a",
        "2a5e45a4",
        "2d790c98",
        "2f46a715",
        "2f485a40",
        "2f7f58de",
        "34b9db0e",
        "39e10935",
        "3db042cf",
        "4166067c",
        "41a702a8",
        "4292f351",
        "42dd5593",
        "44405d5d",
        "4dbb8138",
        "51125e5e",
        "51da116f",
        "5374b4ba",
        "5738dc2a",
        "58fed63a",
        "5953f4c8",
        "5c4e308a",
        "5fbcebc2",
        "6806d715",
        "69aa57b3",
        "6a186446",
        "6b393b81",
        "6fd6e409",
        "7447875a",
        "750adc0c",
        "76006f59",
        "7af6e047",
        "7b3d06f7",
        "7ce54d1f",
        "904e3a54",
        "9081e954",
        "9346686a",
        "94e41495",
        "985ec868",
        "9cfc388d",
        "abdda9e5",
        "b989c740",
        "baab28bb",
        "c0c70a35",
        "c3d2893c",
        "ca109b5e",
        "cf4c04c0",
        "d300a576",
        "d441b4aa",
        "d4519f28",
        "d67cbe5f",
        "d75ea138",
        "d78128b2",
        "d7d182c5",
        "db564ba9",
        "dcf4518b",
        "df6ead3d",
        "e07fffa6",
        "e379414c",
        "e3890bf7",
        "e8011eb6",
        "e8970401",
        "ec14170e",
        "ec192379",
        "eda9e743",
        "ef9b4967",
        "f05e77f3",
        "f17db8d6",
        "f692a1d8",
        "f6a95641",
        "f84c009a",
        "fc7e4f9b",
        "fd48ee2f",
    ]
)

# %%
import json
import math
import re
import subprocess

import kagglehub

# vLLM offline bootstrap (py3.12 / cu128 / vllm 0.17.1 from aimo-3-utils; --target +
# PYTHONPATH + invalidate_caches to dodge the read-only nvidia mount / import caches).
import importlib
import sys

_PYENV = "/kaggle/tmp/pyenv"
os.environ["PYTHONPATH"] = _PYENV + os.pathsep + os.environ.get("PYTHONPATH", "")
try:
    import vllm  # noqa: F401
except Exception:  # noqa: BLE001
    _arch = sorted(
        glob.glob("/kaggle/input/notebooks/*/aimo-3-utils*/wheels.tar.gz")
        + glob.glob("/kaggle/input/**/wheels.tar.gz", recursive=True)
    )
    assert _arch, "aimo-3-utils wheels.tar.gz not attached (add it as a kernel source)"
    _setup = "/kaggle/tmp/setup"
    if not os.path.exists(_setup + "/wheels"):
        os.makedirs(_setup, exist_ok=True)
        subprocess.run(["tar", "-xzf", _arch[0], "-C", _setup], check=True)
    os.makedirs(_PYENV, exist_ok=True)
    subprocess.run(
        [
            "pip",
            "install",
            "-q",
            "--no-index",
            "--find-links",
            _setup + "/wheels",
            "--target",
            _PYENV,
            "--ignore-installed",
            "vllm",
        ],
        check=True,
    )
    if _PYENV not in sys.path:
        sys.path.insert(0, _PYENV)
    importlib.invalidate_caches()
    import vllm  # noqa: F401
print("vllm", vllm.__version__)

import torch
from safetensors.torch import load_file, save_file

# %%
# ---- official metric (port of eval/official_metric.py) ----------------------
_BOXED = re.compile(r"\\boxed\{([^}]*)(?:\}|$)")
_FALLBACK_PATTERNS = [
    r"final answer is:?\s*([^\n]+)",
    r"final answer\s*[:：]\s*([^\n]+)",
    r"answer is:?\s*([^\n]+)",
]
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_LEADING_ZERO_INT = re.compile(r"0\d+")


def extract_final_answer(text):
    if text is None:
        return "NOT_FOUND"
    matches = _BOXED.findall(text)
    if matches:
        non_empty = [m.strip() for m in matches if m.strip()]
        return non_empty[-1] if non_empty else matches[-1].strip()
    for pat in _FALLBACK_PATTERNS:
        m = re.findall(pat, text, re.IGNORECASE)
        if m:
            return m[-1].strip()
    nums = _NUMBER.findall(text)
    if nums:
        return nums[-1]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else "NOT_FOUND"


def verify(gold, predicted):
    gold = str(gold).strip()
    predicted = str(predicted).strip()
    if not _LEADING_ZERO_INT.fullmatch(gold) and not _LEADING_ZERO_INT.fullmatch(predicted):
        try:
            return math.isclose(float(predicted), float(gold), rel_tol=1e-2, abs_tol=1e-5)
        except (ValueError, TypeError):
            pass
    return predicted.lower() == gold.lower()


def classify(p):
    pl = p.lower()
    if "8-bit binary" in pl or "bit manipulation" in pl:
        return "bit"
    if "gravitational constant" in pl:
        return "gravity"
    if "unit conversion" in pl or "convert the following measurement" in pl:
        return "unit"
    if "secret encryption" in pl or "decrypt" in pl:
        return "cipher"
    if "numeral system" in pl:
        return "numeral"
    if "transformation rules is applied to equations" in pl:
        return "equation"
    return "other"


# %%
import csv

_train = glob.glob("/kaggle/input/competitions/*/train.csv") or glob.glob("/kaggle/input/**/train.csv", recursive=True)
assert _train, "train.csv not found"
all_rows = list(csv.DictReader(open(_train[0], encoding="utf-8")))
rows = [r for r in all_rows if r["id"] in EVAL_IDS]
for r in rows:
    r["category"] = classify(r["prompt"])
print(f"hard-val rows matched: {len(rows)} / {len(EVAL_IDS)} ids")
assert len(rows) >= 60, "too few hard-val rows matched; check id set vs train.csv"

MODEL_PATH = kagglehub.model_download("metric/nemotron-3-nano-30b-a3b-bf16/transformers/default")
print("model:", MODEL_PATH)

# %%
# ---- locate the 0.86 soup adapter (attached as a private dataset) -----------
_cfgs = [
    p
    for p in glob.glob("/kaggle/input/**/adapter_config.json", recursive=True)
    if "soup" in p.lower() or "merge-soup" in p.lower()
]
_sts = [
    p
    for p in glob.glob("/kaggle/input/**/adapter_model.safetensors", recursive=True)
    if "soup" in p.lower() or "merge-soup" in p.lower()
]
assert len(_cfgs) == 1 and len(_sts) == 1, f"expected 1 soup adapter; got {_cfgs} {_sts}"
SOUP_CFG, SOUP_ST = _cfgs[0], _sts[0]
print(
    "soup config:",
    SOUP_CFG,
    "| weights:",
    SOUP_ST,
    f"({os.path.getsize(SOUP_ST) / 1e9:.2f} GB)",
)
soup_config = json.load(open(SOUP_CFG))
print("soup LoRA r/alpha:", soup_config.get("r"), soup_config.get("lora_alpha"))


# %%
# ---- spectral surgery: rewrite the soup state dict per a reweighting config ----
def _refactor(B, A, reweight_fn):
    """Efficient rank-r SVD of delta = B@A (B:[out,r], A:[r,in]); reweight singular
    values via reweight_fn(S)->S'; re-factor to (B',A') with B'@A' = U diag(S') V^T.
    Rank (r columns) preserved. All math in float32 on CPU."""
    Bf = B.float()
    Af = A.float()
    Qb, Rb = torch.linalg.qr(Bf)  # Qb:[out,r], Rb:[r,r]
    Qa, Ra = torch.linalg.qr(Af.T)  # Af.T:[in,r] -> Qa:[in,r], Ra:[r,r]
    M = Rb @ Ra.T  # [r,r]; delta = Qb @ M @ Qa.T
    U, S, Vh = torch.linalg.svd(M)  # U:[r,r], S:[r], Vh:[r,r]
    S2 = reweight_fn(S)
    left = Qb @ U  # [out,r]
    right = Qa @ Vh.T  # [in,r]
    sq = torch.sqrt(S2.clamp(min=0.0))
    B2 = left * sq.unsqueeze(0)  # [out,r]
    A2 = (right * sq.unsqueeze(0)).T  # [r,in]
    return B2, A2


def _make_reweight(cfg):
    mode = cfg["mode"]
    if mode == "scale":
        c = float(cfg["scale"])
        return lambda S: S * c
    if mode == "energy":
        e = float(cfg["energy"])
        amp = float(cfg["amp"])

        def fn(S):
            order = torch.argsort(S, descending=True)
            S_sorted = S[order]
            energy = (S_sorted**2).cumsum(0)
            total = energy[-1].clamp(min=1e-12)
            keep_sorted = (energy / total) <= e
            keep_sorted[0] = True  # always keep the top component
            out = torch.zeros_like(S)
            out[order] = torch.where(keep_sorted, S_sorted * amp, torch.zeros_like(S_sorted))
            return out

        return fn
    return lambda S: S  # identity


def build_variant(cfg, src_state, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    reweight = _make_reweight(cfg)
    target_mods = cfg.get("modules")  # None => all modules
    new_state = {}
    a_keys = [k for k in src_state if k.endswith("lora_A.weight")]
    touched = 0
    for ak in a_keys:
        bk = ak[: -len("lora_A.weight")] + "lora_B.weight"
        A = src_state[ak]
        B = src_state[bk]
        do_it = cfg["mode"] != "identity" and (target_mods is None or any(m in ak for m in target_mods))
        if do_it:
            B2, A2 = _refactor(B, A, reweight)
            new_state[ak] = A2.to(A.dtype).contiguous()
            new_state[bk] = B2.to(B.dtype).contiguous()
            touched += 1
        else:
            new_state[ak] = A.clone()
            new_state[bk] = B.clone()
    # carry over any non-lora tensors verbatim (e.g., embeddings if present)
    for k, v in src_state.items():
        if k not in new_state:
            new_state[k] = v.clone()
    save_file(new_state, os.path.join(out_dir, "adapter_model.safetensors"))
    json.dump(soup_config, open(os.path.join(out_dir, "adapter_config.json"), "w"))
    return touched


print("loading soup state dict (cpu)...")
SOUP_STATE = load_file(SOUP_ST, device="cpu")
_n_pairs = sum(1 for k in SOUP_STATE if k.endswith("lora_A.weight"))
print(f"soup tensors: {len(SOUP_STATE)} ({_n_pairs} lora_A/B pairs)")

# %%
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

llm = LLM(
    model=str(MODEL_PATH),
    tensor_parallel_size=1,
    max_num_seqs=64,
    gpu_memory_utilization=0.85,
    dtype="auto",
    max_model_len=8192,
    trust_remote_code=True,
    enable_lora=True,
    max_lora_rank=int(soup_config.get("r", 32)),
)
tok = llm.get_tokenizer()
SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"
GEN = SamplingParams(temperature=0.0, top_p=1.0, max_tokens=7680)
prompts = [
    tok.apply_chat_template(
        [{"role": "user", "content": r["prompt"] + SUFFIX}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    for r in rows
]


def eval_adapter(adapter_dir, lora_id):
    lora = LoRARequest(f"v{lora_id}", lora_id, adapter_dir)
    outs = llm.generate(prompts, GEN, lora_request=lora)
    per_cat = {}
    correct = 0
    for r, o in zip(rows, outs):
        ok = bool(o.outputs) and verify(r["answer"], extract_final_answer(o.outputs[0].text))
        correct += int(ok)
        d = per_cat.setdefault(r["category"], [0, 0])
        d[0] += int(ok)
        d[1] += 1
    return correct / len(rows), {c: f"{v[0]}/{v[1]}" for c, v in per_cat.items()}


# %%
# fail-fast preflight: build the identity variant + score 2 prompts (validates the
# surgery -> save -> vLLM-load path before the full sweep).
_pf_dir = "/kaggle/tmp/variant_preflight"
build_variant({"name": "pf", "mode": "identity"}, SOUP_STATE, _pf_dir)
_pf = llm.generate(
    prompts[:2],
    SamplingParams(temperature=0.0, max_tokens=256),
    lora_request=LoRARequest("pf", 999, _pf_dir),
)
assert _pf and _pf[0].outputs, "preflight produced no output"
print("preflight OK:", _pf[0].outputs[0].text[:80].replace("\n", " "))
shutil.rmtree(_pf_dir, ignore_errors=True)

# %%
# ---- sweep configs: build -> eval -> keep best (one variant on disk at a time) ----
BEST_DIR = "/kaggle/working/best_adapter"
results = {}
best_name, best_acc = None, -1.0
for i, cfg in enumerate(SURGERY_CONFIGS):
    if _time.time() - T0 > EVAL_DEADLINE_SEC:
        print("deadline hit; stopping sweep")
        break
    vdir = f"/kaggle/tmp/variant_{i}"
    touched = build_variant(cfg, SOUP_STATE, vdir)
    acc, per_cat = eval_adapter(vdir, i + 1)
    results[cfg["name"]] = {
        "acc": acc,
        "per_category": per_cat,
        "modules_touched": touched,
    }
    print(f"[{cfg['name']}] hard-val acc = {acc:.4f}  touched={touched}  per-cat={per_cat}")
    if acc > best_acc:
        best_acc, best_name = acc, cfg["name"]
        shutil.rmtree(BEST_DIR, ignore_errors=True)
        shutil.copytree(vdir, BEST_DIR)
    shutil.rmtree(vdir, ignore_errors=True)

print(f"\nBEST: {best_name}  acc={best_acc:.4f}")

# %%
import hashlib
import zipfile

ranking = sorted(results.items(), key=lambda kv: kv[1]["acc"], reverse=True)
json.dump(
    {
        "best": best_name,
        "best_acc": best_acc,
        "baseline_acc": results.get("soup_baseline", {}).get("acc"),
        "results": results,
        "ranking": [k for k, _ in ranking],
    },
    open("/kaggle/working/surgery_ranking.json", "w"),
    indent=2,
)
print("=== surgery hard-val ranking (best first) ===")
for k, v in ranking:
    print(f"  {k}: {v['acc']:.4f}  {v['per_category']}")

# Package the best variant as submission.zip ONLY if it strictly beats the soup baseline;
# otherwise leave the soup as the standing best (do not regress).
base_acc = results.get("soup_baseline", {}).get("acc", -1.0)
if best_name and best_name != "soup_baseline" and best_acc > base_acc:
    sub = "/kaggle/working/submission.zip"
    with zipfile.ZipFile(sub, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(BEST_DIR, "adapter_config.json"), "adapter_config.json")
        zf.write(
            os.path.join(BEST_DIR, "adapter_model.safetensors"),
            "adapter_model.safetensors",
        )
    with zipfile.ZipFile(sub) as zf:
        names = set(zf.namelist())
        assert names == {"adapter_config.json", "adapter_model.safetensors"}, names
    h = hashlib.sha256(open(sub, "rb").read()).hexdigest()
    print(f"WROTE submission.zip ({os.path.getsize(sub) / 1e9:.2f} GB) sha256={h}")
    print(f"  -> surgery '{best_name}' beat soup baseline {base_acc:.4f} -> {best_acc:.4f}")
else:
    print(
        f"No surgery variant beat the soup baseline ({base_acc:.4f}); NOT writing submission.zip (hold the 0.86 soup)."
    )
print("Done.")
