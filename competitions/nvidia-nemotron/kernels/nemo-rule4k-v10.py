# ruff: noqa: E402  (Kaggle kernel: imports follow env/setup cells)
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
MAX_STEPS = 800  # secondary cap; the wall-clock budget below is the real bound
MAX_LEN = 4096  # CoT reasoning traces are long
N_EXAMPLES = 4000  # long-CoT corpus rows, mixed ~1:1 with the rule traces

# Time budget (Kaggle hard limit 12h; v9 timed out because a 64-example
# autoregressive eval ran on top of training). Cap training by WALL CLOCK and
# keep the eval tiny + time-boxed so we always reach save+zip.
import time as _time

T0 = _time.time()
TRAIN_BUDGET_SEC = 19800  # 5.5h training cap -> finishes with margin to submit
EVAL_N = 8  # tiny held-out eval (was 64 -> too slow)
# T13 fix: 512 truncated the CoT before \boxed{} appeared, so val read 0/8 on
# adapters that scored 0.65-0.67 on the LB. Match the official evaluator's
# generation cap and bound the WHOLE eval loop by wall clock instead.
EVAL_MAX_NEW = 7680  # official eval allows 7680 generated tokens
EVAL_TIME_CAP_SEC = 1800  # hard cap for the whole held-out eval loop
EVAL_SKIP_AFTER_SEC = 23400  # 6.5h: skip eval entirely if already this deep
N_RULE = 4000  # deterministic rule-CoT traces built from train.csv

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
    val_df = _full.slice(N_EXAMPLES, EVAL_N)
    print(
        "using CoT csv at:",
        _cands[0],
        "| train rows:",
        df.height,
        "| val rows:",
        val_df.height,
    )

    SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"

    # ---- v10: deterministic rule-aware CoT traces from the competition train.csv.
    # For 6 of the 9 categories the transformation rule is recoverable from the
    # prompt itself, so the trace SHOWS the rule being applied (numbers computed,
    # mapping tables decoded) instead of free-form reasoning. Answers are the
    # ground-truth ones from train.csv, so every trace ends in a correct \boxed{}.
    def _classify(p):
        p = p.lower()
        if "8-bit binary" in p or "bit manipulation" in p:
            return "bit_manipulation"
        if "gravitational constant" in p:
            return "gravity"
        if "unit conversion" in p or "convert the following measurement" in p:
            return "unit_conversion"
        if "secret encryption" in p or "decrypt" in p:
            return "cipher"
        if "wonderland numeral" in p or "different numeral system" in p:
            return "numeral"
        if "transformation rules is applied to equations" in p:
            return "equation"
        return "other"

    def _roman(n):
        out = []
        for v, s in [
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        ]:
            while n >= v:
                out.append(s)
                n -= v
        return "".join(out)

    def _last_float(pattern, text):
        m = re.findall(pattern, text, flags=re.I | re.S)
        if not m:
            return None
        v = m[-1][-1] if isinstance(m[-1], tuple) else m[-1]
        try:
            return float(v)
        except ValueError:
            return None

    def _rule_trace(prompt, answer, cat):
        # `answer` intentionally unused: build_pair() appends the canonical
        # ground-truth \boxed{} after </think>, so traces carry reasoning only.
        del answer
        if cat == "numeral":
            m = re.search(r"write the number\s+(\d+)", prompt, flags=re.I)
            if m:
                n = int(m.group(1))
                return f"The examples use standard Roman numeral composition. {n} becomes {_roman(n)}."
        if cat == "gravity":
            pairs = [(float(t), float(d)) for t, d in re.findall(r"For t = ([0-9.]+)s, distance = ([0-9.]+) m", prompt)]
            target = _last_float(r"falling distance for t = ([0-9.]+)s", prompt)
            if pairs and target is not None:
                gs = [2.0 * d / (t * t) for t, d in pairs if t]
                g = sum(gs) / max(1, len(gs))
                pred = 0.5 * g * target * target
                return (
                    f"Use d = 0.5*g*t^2, so g = 2d/t^2. The examples give g ≈ "
                    f"{g:.4f}; for t={target:g}, d = 0.5*{g:.4f}*{target:g}^2 ≈ {pred:.2f}."
                )
        if cat == "unit_conversion":
            pairs = [(float(x), float(y)) for x, y in re.findall(r"([0-9.]+) m becomes ([0-9.]+)", prompt)]
            target = _last_float(r"following measurement:\s*([0-9.]+) m", prompt)
            if pairs and target is not None:
                rs = [y / x for x, y in pairs if x]
                r_ = sum(rs) / max(1, len(rs))
                return (
                    f"The conversion is a constant multiplier. Example ratio ≈ "
                    f"{r_:.5f}; {target:g} * {r_:.5f} ≈ {target * r_:.2f}."
                )
        if cat == "cipher":
            mp = {}
            for enc, plain in re.findall(r"^([^\n>-][^\n]*?)\s*->\s*([^\n]+)$", prompt, flags=re.M):
                ew, pw = enc.strip().split(), plain.strip().split()
                if len(ew) == len(pw):
                    mp.update(zip(ew, pw))
            tm = re.search(r"Now, decrypt the following text:\s*([^\n\"]+)", prompt, flags=re.I)
            if mp and tm:
                tw = tm.group(1).strip().split()
                decoded = " ".join(mp.get(w, "?") for w in tw)
                return (
                    f"Build a word-level substitution table from the example pairs; "
                    f"it decodes the target as: {decoded}."
                )
        if cat == "bit_manipulation":
            return (
                "Compare each 8-bit example bitwise to infer the consistent "
                "shift/rotation/boolean pattern, then apply it to the target byte."
            )
        if cat == "equation":
            return (
                "Identify which operator rule the examples demonstrate, including "
                "character order, then apply the same rule to the target expression."
            )
        return "Infer the hidden rule from the demonstrations and apply it to the target."

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
    def _encode(prompt, answer, cot):
        full, prompt_only = build_pair(prompt, answer, cot)
        ids = tokenizer(full, truncation=True, max_length=MAX_LEN)["input_ids"]
        plen = len(tokenizer(prompt_only, truncation=True, max_length=MAX_LEN)["input_ids"])
        plen = min(plen, len(ids))
        return {"input_ids": ids, "labels": [-100] * plen + ids[plen:]}

    examples = []
    for r in df.iter_rows(named=True):
        cot = r.get("generated_cot")
        if cot is None or str(cot) == "nan" or len(str(cot).strip()) < 5:
            continue
        examples.append(_encode(r["prompt"], str(r["answer"]), cot))
    n_long = len(examples)

    # v10 data change: mix in N_RULE deterministic rule traces from train.csv.
    _train_csv = glob.glob("/kaggle/input/competitions/*/train.csv") or glob.glob(
        "/kaggle/input/**/train.csv", recursive=True
    )
    if not _train_csv:
        raise FileNotFoundError("competition train.csv not found under /kaggle/input")
    _tdf = pl.read_csv(_train_csv[0])
    _cat_count = {}
    n_rule = 0
    for r in _tdf.iter_rows(named=True):
        if n_rule >= N_RULE:
            break
        cat = _classify(str(r["prompt"]))
        _cat_count[cat] = _cat_count.get(cat, 0) + 1
        trace = _rule_trace(str(r["prompt"]), str(r["answer"]), cat)
        examples.append(_encode(str(r["prompt"]), str(r["answer"]), trace))
        n_rule += 1
    print(f"examples: {n_long} long-CoT + {n_rule} rule-CoT | categories: {_cat_count}")

    import random as _random

    _random.Random(42).shuffle(examples)
    if not examples:
        raise ValueError("no CoT training examples built")

    ds = datasets.Dataset.from_list(examples)

    from transformers import (
        DataCollatorForSeq2Seq,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    class _TimeBudget(TrainerCallback):
        # Stop training once the wall-clock budget is hit, regardless of max_steps,
        # so eval + save + zip always fit under Kaggle's 12h hard limit.
        def on_step_end(self, args, state, control, **kw):
            if _time.time() - T0 > TRAIN_BUDGET_SEC:
                control.should_training_stop = True
            return control

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
                max_new_tokens=EVAL_MAX_NEW,
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
    _out = Trainer(
        model=model,
        args=args,
        train_dataset=ds,
        data_collator=collator,
        callbacks=[_TimeBudget()],
    ).train()
    TRAIN_OK = True
    print(f"training stopped at step {_out.global_step}, elapsed {_time.time() - T0:.0f}s")

    # Held-out boxed accuracy (overfitting signal) — ISOLATED in its own try so a
    # failure here can never flip the trained status or waste the trained adapter.
    _val_acc = None
    _n = 0
    try:
        if _time.time() - T0 > EVAL_SKIP_AFTER_SEC:
            raise RuntimeError("skipping held-out eval — low on time budget")
        model.config.use_cache = True
        model.eval()
        _correct = 0
        _eval_t0 = _time.time()
        for vr in val_df.iter_rows(named=True):
            if vr.get("answer") is None:
                continue
            # T13: cap the whole eval loop by wall clock — at 7680 new tokens a
            # single greedy generation can take minutes; report partial n instead
            # of blowing the session budget.
            if _time.time() - _eval_t0 > EVAL_TIME_CAP_SEC:
                print(f"eval time cap hit after {_n} examples")
                break
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
