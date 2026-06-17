# ruff: noqa: E402  (Kaggle kernel: imports follow env/setup cells)
# Nemo v11 stage-1 — rejection-sampling self-distillation, SAMPLE+FILTER (account B shard).
#
# On-policy STaR/RFT: sample K CoT per hard-category train prompt from base + our best
# adapter (the 0.86 soup) via vLLM, extract \boxed{}, and KEEP only samples whose answer
# matches the train.csv ground truth (official metric). Output: a verified-CoT JSONL corpus
# (kernel output) for a post-competition stage-2 SFT run. NO submission here.
#
# Why vLLM: it is the throughput-viable path for 30B sampling AND the exact loader the grader
# uses for our adapters (so the soup LoRA loads). Fail-fast preflight: if the offline vLLM/LoRA
# path does not work in this image, error in minutes (then the external GPU #83 is the route).
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
SHARD = 1  # account B
USE_SOUP = False  # B: classic RFT from base (no soup; firefly2006 lacks the private soup dataset)
CATEGORIES = ["bit", "equation", "cipher"]  # hardest categories (where SFT plateaus)
N_PROMPTS = 1200  # prompts to sample this shard
N_SAMPLES = 4  # samples per prompt
SAMPLE_MAX_TOKENS = 4096
TEMPERATURE = 0.8
import time as _time

T0 = _time.time()
SAMPLE_DEADLINE_SEC = 25200  # 7h wall-clock guard; always reach the save

# %%
import json
import math
import re
import subprocess

import kagglehub

# vLLM must be importable offline; if not, try the attached offline wheels, else fail-fast.
try:
    import vllm  # noqa: F401
except Exception:  # noqa: BLE001
    for _wd in glob.glob("/kaggle/input/**/wheels", recursive=True) + glob.glob(
        "/kaggle/input/**/packages", recursive=True
    ):
        subprocess.run(
            ["pip", "install", "-q", "--no-index", "--find-links", _wd, "vllm"],
            check=False,
        )
    import vllm  # noqa: F401
print("vllm", vllm.__version__)

MODEL_PATH = kagglehub.model_download("metric/nemotron-3-nano-30b-a3b-bf16/transformers/default")
SOUP_PATH = None
if USE_SOUP:
    _cfg = glob.glob("/kaggle/input/**/adapter_config.json", recursive=True)
    assert _cfg, "USE_SOUP but soup adapter not found under /kaggle/input"
    SOUP_PATH = os.path.dirname(_cfg[0])
_train = glob.glob("/kaggle/input/competitions/*/train.csv") or glob.glob("/kaggle/input/**/train.csv", recursive=True)
assert _train, "train.csv not found"
print("model:", MODEL_PATH, "| soup:", SOUP_PATH, "| train:", _train[0])

# %%
# official-metric extract + verify (binary string-matched; numeric within 1e-2)
_BOXED = re.compile(r"\\boxed\{([^}]*)(?:\}|$)")
_LZ = re.compile(r"0\d+")


def extract_final_answer(text):
    if not text:
        return "NOT_FOUND"
    m = _BOXED.findall(text)
    if m:
        ne = [x.strip() for x in m if x.strip()]
        return ne[-1] if ne else m[-1].strip()
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    return nums[-1] if nums else "NOT_FOUND"


def verify(gold, pred):
    gold, pred = str(gold).strip(), str(pred).strip()
    if not _LZ.fullmatch(gold) and not _LZ.fullmatch(pred):
        try:
            return math.isclose(float(pred), float(gold), rel_tol=1e-2, abs_tol=1e-5)
        except (ValueError, TypeError):
            pass
    return pred.lower() == gold.lower()


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

rows = [r for r in csv.DictReader(open(_train[0], encoding="utf-8")) if classify(r["prompt"]) in CATEGORIES]
rows = [r for i, r in enumerate(rows) if i % 2 == SHARD][:N_PROMPTS]  # shard split
print(f"shard {SHARD}: {len(rows)} prompts over {CATEGORIES}")

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
    enable_lora=USE_SOUP,
    max_lora_rank=32,
)
tok = llm.get_tokenizer()
SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"
lora = LoRARequest("soup", 1, SOUP_PATH) if USE_SOUP else None


def build_prompt(p):
    return tok.apply_chat_template(
        [{"role": "user", "content": p + SUFFIX}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )


# fail-fast: one prompt must load+generate before the full shard
_sp1 = SamplingParams(temperature=0.0, max_tokens=512)
_o = llm.generate([build_prompt(rows[0]["prompt"])], _sp1, lora_request=lora)
assert _o and _o[0].outputs, "fail-fast: vLLM+LoRA produced no output"
print("preflight OK; sample text:", _o[0].outputs[0].text[:120].replace("\n", " "))

# %%
sp = SamplingParams(temperature=TEMPERATURE, top_p=0.95, max_tokens=SAMPLE_MAX_TOKENS, n=N_SAMPLES)
kept = []
BATCH = 64
for i in range(0, len(rows), BATCH):
    if _time.time() - T0 > SAMPLE_DEADLINE_SEC:
        print("wall-clock budget hit; stopping sampling")
        break
    batch = rows[i : i + BATCH]
    outs = llm.generate([build_prompt(r["prompt"]) for r in batch], sp, lora_request=lora)
    for r, out in zip(batch, outs):
        for cand in out.outputs:
            if verify(r["answer"], extract_final_answer(cand.text)):
                kept.append(
                    {
                        "id": r["id"],
                        "category": classify(r["prompt"]),
                        "prompt": r["prompt"],
                        "cot": cand.text,
                        "answer": str(r["answer"]).strip(),
                    }
                )
                break  # one verified CoT per prompt is enough
    print(f"  {i + len(batch)}/{len(rows)} prompts | kept {len(kept)}")

# %%
out_path = "/kaggle/working/verified_cot.jsonl"
with open(out_path, "w") as f:
    for rec in kept:
        f.write(json.dumps(rec) + "\n")
by_cat = {}
for rec in kept:
    by_cat[rec["category"]] = by_cat.get(rec["category"], 0) + 1
print(f"VERIFIED_COT: kept {len(kept)} / {len(rows)} prompts ({by_cat}); wrote {out_path}")
print("Done.")
