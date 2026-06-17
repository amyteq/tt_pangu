# %%
# ruff: noqa: E402  (Kaggle kernel: imports follow env/ptxas setup)
import glob
import site

# The NVIDIA utility script (attached via kernel_sources) ships mamba_ssm +
# cutlass for the hybrid-Mamba Nemotron model. Kaggle mounts it under
# /kaggle/usr/lib/notebooks/ryanholbrook/<dir>, slugifying the name with
# UNDERSCORES (nvidia_utility_script), so glob for the cutlass python_packages
# dir rather than hardcoding the demo's (wrong) hyphenated path.
_cutlass = glob.glob("/kaggle/usr/lib/notebooks/ryanholbrook/*nvidia*util*/nvidia_cutlass_dsl/python_packages")
for _p in _cutlass:
    site.addsitedir(_p)
print("cutlass sitedirs:", _cutlass)

# The bundled Blackwell ptxas (used by Triton JIT for the Mamba kernels during
# TRAINING) loses its execute bit on the read-only mount -> EACCES. The bundled
# Triton fork resolves it via TRITON_PTXAS_BLACKWELL_PATH (NOT the standard
# TRITON_PTXAS_PATH) and also shells out to `ptxas --version`, so we copy the
# binary to a writable /tmp dir, chmod +x, point both env vars at it, and
# monkeypatch get_ptxas_version. (Recipe from the public LB-0.85 training
# notebooks — dennisfong / dgxchen.)
import os
import shutil
import stat as _stat

_ptxas = glob.glob("/kaggle/usr/lib/notebooks/ryanholbrook/*/triton/backends/nvidia/bin/ptxas-blackwell")
if _ptxas:
    _dst = "/tmp/ptxas-blackwell"
    try:
        shutil.copy2(_ptxas[0], _dst)
        os.chmod(
            _dst,
            os.stat(_dst).st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH,
        )
        os.environ["TRITON_PTXAS_BLACKWELL_PATH"] = _dst
        os.environ["TRITON_PTXAS_PATH"] = _dst
        print("ptxas-blackwell ->", _dst)
    except OSError as _e:
        print("ptxas copy failed:", _e)
try:
    import triton.backends.nvidia.compiler as _nvc

    _nvc.get_ptxas_version = lambda *a, **k: "12.0"
    print("patched triton get_ptxas_version")
except Exception as _e:  # noqa: BLE001
    print("triton patch skipped:", _e)

import kagglehub
import mamba_ssm  # noqa: F401  (import has side effects the model needs)
import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

# %%
MODEL_PATH = kagglehub.model_download("metric/nemotron-3-nano-30b-a3b-bf16/transformers/default")
OUTPUT_DIR = "/kaggle/working"
LORA_RANK = 32  # competition max is 32
MAX_STEPS = 400  # v7: ~3.3x v6 (~4h training) for better CoT convergence
MAX_LEN = 4096  # CoT reasoning traces are long
N_EXAMPLES = 6000  # subsample of the CoT corpus for the bounded SFT

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    trust_remote_code=True,
    dtype=torch.bfloat16,
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
print("Model + tokenizer loaded.")

# %%
lora_config = LoraConfig(
    r=LORA_RANK,
    lora_alpha=32,  # alpha == rank, per the LB-0.85 recipe
    target_modules=r".*\.(in_proj|out_proj|up_proj|down_proj)$",
    lora_dropout=0.0,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# %%
# Bounded supervised fine-tune. Wrapped so ANY failure still leaves us with a
# valid (initialized) adapter to submit — baseline-first / pipeline validation.
TRAIN_OK = False
TRAIN_INFO = {"trained": False}
try:
    import glob
    import re

    import polars as pl

    # Train on CoT REASONING TRACES (the LB-0.85 recipe), not bare answers — this
    # is a reasoning challenge. Dataset: dgxchen/nemotron-cot-tong
    #   problem_ids_matched.csv columns: id, prompt, answer, type, generated_cot
    _cands = glob.glob("/kaggle/input/**/problem_ids_matched.csv", recursive=True)
    print("CoT csv candidates:", _cands[:5])
    if not _cands:
        raise FileNotFoundError("CoT csv not found under /kaggle/input")
    _full = pl.read_csv(_cands[0])
    df = _full.head(N_EXAMPLES)
    # Held-out split from rows AFTER the training slice (truly unseen) — used to
    # measure boxed-answer accuracy and catch overfitting at training time.
    val_df = _full.slice(N_EXAMPLES, 64)
    print(
        "using CoT csv at:",
        _cands[0],
        "| train rows:",
        df.height,
        "| val rows:",
        val_df.height,
    )

    SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"

    def build_pair(prompt, answer, cot):
        # Strip any boxed answer inside the trace; append the canonical one after
        # </think>, matching the public recipe's reasoning format.
        cot = re.sub(r"\\boxed\{[^}]*\}", "", str(cot)).rstrip()
        assistant = f"{cot}\n</think>\n\\boxed{{{answer}}}"
        user = [{"role": "user", "content": f"{prompt}{SUFFIX}"}]
        full = tokenizer.apply_chat_template(user + [{"role": "assistant", "content": assistant}], tokenize=False)
        prompt_only = tokenizer.apply_chat_template(user, tokenize=False, add_generation_prompt=True)
        return full, prompt_only

    import datasets

    # Proper SFT masking: compute labels with the PROMPT tokens set to -100 so the
    # loss is only on the assistant reasoning + boxed answer (not the prompt, and
    # — via the collator — not padding). v6 trained on prompt+padding and regressed.
    examples = []
    for r in df.iter_rows(named=True):
        cot = r.get("generated_cot")
        if cot is None or str(cot) == "nan" or len(str(cot).strip()) < 5:
            continue
        full, prompt_only = build_pair(r["prompt"], str(r["answer"]), cot)
        ids = tokenizer(full, truncation=True, max_length=MAX_LEN)["input_ids"]
        plen = len(tokenizer(prompt_only, truncation=True, max_length=MAX_LEN)["input_ids"])
        plen = min(plen, len(ids))
        labels = [-100] * plen + ids[plen:]
        examples.append({"input_ids": ids, "labels": labels})
    print("training examples:", len(examples))
    if not examples:
        raise ValueError("no CoT training examples built")

    ds = datasets.Dataset.from_list(examples)

    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments

    collator = DataCollatorForSeq2Seq(tokenizer, label_pad_token_id=-100, padding="longest")

    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    import torch as _torch

    _boxed = re.compile(r"\\boxed\{([^}]*)\}")

    def _gen_boxed(prompt):
        # Generate for one prompt; return the last \boxed{...} answer.
        # apply_chat_template may return a BatchEncoding (dict-like) which has no
        # .shape — request return_dict and index input_ids explicitly (v8 crashed
        # on `_ids.shape[1]` exactly here: KeyError 'shape').
        enc = tokenizer.apply_chat_template(
            [{"role": "user", "content": f"{prompt}{SUFFIX}"}],
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        input_ids = enc["input_ids"].to(model.device)
        attn = enc.get("attention_mask")
        attn = attn.to(model.device) if attn is not None else None
        with _torch.no_grad():
            out = model.generate(
                input_ids=input_ids,
                attention_mask=attn,
                max_new_tokens=1024,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        txt = tokenizer.decode(out[0][input_ids.shape[1] :], skip_special_tokens=True)
        hits = _boxed.findall(txt)
        return hits[-1].strip() if hits else ""

    # Fail-fast preflight: exercise the generate/eval path on ONE example BEFORE the
    # ~2h train, so a runtime bug here surfaces in minutes, not after training.
    # Non-fatal — a broken eval must never waste the trained adapter.
    if val_df.height:
        model.config.use_cache = True
        model.eval()
        try:
            _gen_boxed(val_df.row(0, named=True)["prompt"])
            print("preflight: generate/eval path OK")
        except Exception as _pe:  # noqa: BLE001
            print(
                "preflight: eval path FAILED (held-out eval will be skipped):",
                repr(_pe),
            )
        model.config.use_cache = False
        model.train()

    args = TrainingArguments(
        output_dir="/kaggle/working/trainer",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        max_steps=MAX_STEPS,
        learning_rate=2e-4,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        bf16=True,
        logging_steps=10,
        save_strategy="no",
        report_to=[],
    )
    _out = Trainer(model=model, args=args, train_dataset=ds, data_collator=collator).train()
    TRAIN_OK = True

    # Held-out boxed accuracy (overfitting signal) — ISOLATED in its own try so a
    # failure here can never flip the trained status or waste the trained adapter.
    _val_acc = None
    _n = 0
    try:
        model.config.use_cache = True
        model.eval()
        _correct = 0
        for vr in val_df.iter_rows(named=True):
            if vr.get("answer") is None:
                continue
            _pred = _gen_boxed(vr["prompt"])
            _correct += int(_pred == str(vr["answer"]).strip())
            _n += 1
        _val_acc = round(_correct / _n, 4) if _n else None
        model.config.use_cache = False
        model.train()
        print(f"held-out boxed accuracy: {_val_acc} ({_correct}/{_n})")
    except Exception as _ee:  # noqa: BLE001
        print("held-out eval failed (non-fatal):", repr(_ee))

    TRAIN_INFO = {
        "trained": True,
        "steps": int(getattr(_out, "global_step", MAX_STEPS) or MAX_STEPS),
        "train_loss": float(getattr(_out, "training_loss", float("nan"))),
        "examples": len(examples),
        "val_accuracy": _val_acc,
        "val_n": _n,
    }
    print("SFT complete:", TRAIN_INFO)
except Exception as e:  # noqa: BLE001
    import traceback

    TRAIN_INFO = {"trained": False, "error": repr(e)[:300]}
    print("Training skipped — saving initialized adapter instead:", e)
    traceback.print_exc()

# %%
import glob
import subprocess

# Drop any trainer checkpoints so only the adapter lands in the zip.
subprocess.run("rm -rf /kaggle/working/trainer", shell=True, check=False)

model.save_pretrained(OUTPUT_DIR)
print("Adapter files:", sorted(glob.glob(f"{OUTPUT_DIR}/adapter*")))

subprocess.run(
    "cd /kaggle/working && zip -r submission.zip adapter_config.json adapter_model.safetensors",
    shell=True,
    check=True,
)
print("Wrote /kaggle/working/submission.zip")

# Tiny report so training status can be checked without downloading the
# multi-GB adapter; then drop the raw adapter (it is inside submission.zip).
import json as _json

with open(f"{OUTPUT_DIR}/train_report.json", "w") as _f:
    _json.dump(TRAIN_INFO, _f)
print("TRAIN_REPORT:", _json.dumps(TRAIN_INFO))
for _f in glob.glob(f"{OUTPUT_DIR}/adapter_model.safetensors") + glob.glob(f"{OUTPUT_DIR}/adapter_config.json"):
    try:
        os.remove(_f)
    except OSError:
        pass

# %%
print("Done.")
