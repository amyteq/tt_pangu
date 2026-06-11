#!/usr/bin/env python3
"""
Version 2: category-aware CoT + answer SFT for the Kaggle NVIDIA Nemotron
Model Reasoning Challenge.

Compared with v1, this script creates a small deterministic reasoning trace for
most training rows before the final \boxed{answer}. It is designed to teach the
required answer format and to give the model short, category-specific solution
patterns without requiring any external LLM calls.

The synthetic traces are intentionally conservative. They are not used as a
solver at inference time; they only shape the LoRA adapter during SFT.
"""

from __future__ import annotations

import os
import random
import re
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
import torch
from torch.utils.data import Dataset

try:
    import site

    CUTLASS_PATH = "/kaggle/usr/lib/notebooks/ryanholbrook/nvidia-utility-script/nvidia_cutlass_dsl/python_packages/"
    if os.path.isdir(CUTLASS_PATH):
        site.addsitedir(CUTLASS_PATH)
except Exception:
    pass

try:
    import kagglehub
except Exception:
    kagglehub = None

from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments


@dataclass
class CFG:
    train_csv: str = os.getenv("TRAIN_CSV", "")
    base_model: str = os.getenv(
        "BASE_MODEL", "metric/nemotron-3-nano-30b-a3b-bf16/transformers/default"
    )
    output_dir: str = os.getenv("OUTPUT_DIR", "/kaggle/working/adapter_v2_cot_rule_augmented")
    zip_path: str = os.getenv("ZIP_PATH", "/kaggle/working/submission.zip")

    seed: int = int(os.getenv("SEED", "2026"))
    max_train_rows: int = int(os.getenv("MAX_TRAIN_ROWS", "0"))
    max_length: int = int(os.getenv("MAX_LENGTH", "1536"))

    lora_rank: int = int(os.getenv("LORA_RANK", "32"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_dropout: float = float(os.getenv("LORA_DROPOUT", "0.05"))
    target_modules: str = os.getenv(
        "TARGET_MODULES", r".*\.(in_proj|out_proj|up_proj|down_proj|x_proj|dt_proj)$"
    )

    lr: float = float(os.getenv("LR", "3e-5"))
    epochs: float = float(os.getenv("EPOCHS", "1"))
    per_device_batch: int = int(os.getenv("PER_DEVICE_BATCH", "1"))
    grad_accum: int = int(os.getenv("GRAD_ACCUM", "16"))
    warmup_ratio: float = float(os.getenv("WARMUP_RATIO", "0.03"))

    # Add an additional answer-only example for hard categories.
    hard_repeat: int = int(os.getenv("HARD_CATEGORY_REPEAT", "1"))


PROMPT_SUFFIX = "\nPlease put your final answer inside `\\boxed{}`. For example: `\\boxed{your answer}`"
HARD_CATEGORIES = {"bit_manipulation", "equation", "cipher"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def find_train_csv() -> str:
    candidates = [
        CFG.train_csv,
        "/kaggle/input/nvidia-nemotron-model-reasoning-challenge/train.csv",
        "/kaggle/input/train.csv",
        "/kaggle/working/data/train.csv",
        "/mnt/data/train.csv",
        "data/train.csv",
        "train.csv",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return str(Path(path))
    raise FileNotFoundError("Could not find train.csv. Set TRAIN_CSV=/path/to/train.csv")


def resolve_model_path(model_id_or_path: str) -> str:
    path = Path(model_id_or_path)
    if path.exists():
        return str(path)
    if kagglehub is None:
        raise RuntimeError("kagglehub is unavailable; set BASE_MODEL to a local model directory")
    return kagglehub.model_download(model_id_or_path)


def classify_prompt(prompt: str) -> str:
    p = prompt.lower()
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
    return "unknown"


def roman(n: int) -> str:
    table = [
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
    ]
    out = []
    for value, sym in table:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def parse_last_float(pattern: str, text: str) -> Optional[float]:
    matches = re.findall(pattern, text, flags=re.I | re.S)
    if not matches:
        return None
    value = matches[-1]
    if isinstance(value, tuple):
        value = value[-1]
    try:
        return float(value)
    except ValueError:
        return None


def make_reasoning(prompt: str, answer: str, category: str) -> str:
    """Return a short deterministic trace plus boxed answer."""
    ans = str(answer).strip()

    if category == "numeral":
        m = re.search(r"write the number\s+(\d+)", prompt, flags=re.I)
        if m:
            n = int(m.group(1))
            calc = roman(n)
            return f"The examples use standard Roman numeral composition. {n} becomes {calc}.\\boxed{{{ans}}}"
        return f"Convert the target number using the numeral pattern in the examples.\\boxed{{{ans}}}"

    if category == "gravity":
        pairs = [(float(t), float(d)) for t, d in re.findall(r"For t = ([0-9.]+)s, distance = ([0-9.]+) m", prompt)]
        target = parse_last_float(r"falling distance for t = ([0-9.]+)s", prompt)
        if pairs and target is not None:
            # d = 0.5*g*t^2 => g = 2d/t^2. Round examples make small noise; average is robust.
            gs = [2.0 * d / (t * t) for t, d in pairs if t != 0]
            g = sum(gs) / max(1, len(gs))
            pred = 0.5 * g * target * target
            return (
                f"Use d = 0.5*g*t^2. Estimating g from the examples gives about {g:.4f}; "
                f"for t={target:g}, d is about {pred:.2f}.\\boxed{{{ans}}}"
            )
        return f"Estimate the changed gravitational constant from the examples and apply d = 0.5*g*t^2.\\boxed{{{ans}}}"

    if category == "unit_conversion":
        pairs = [(float(x), float(y)) for x, y in re.findall(r"([0-9.]+) m becomes ([0-9.]+)", prompt)]
        target = parse_last_float(r"following measurement:\s*([0-9.]+) m", prompt)
        if pairs and target is not None:
            ratios = [y / x for x, y in pairs if x != 0]
            ratio = sum(ratios) / max(1, len(ratios))
            pred = target * ratio
            return (
                f"The conversion is a near-constant multiplier. The example ratio is about {ratio:.5f}; "
                f"{target:g} maps to about {pred:.2f}.\\boxed{{{ans}}}"
            )
        return f"Infer the linear unit multiplier from the examples and apply it to the target.\\boxed{{{ans}}}"

    if category == "cipher":
        mappings: Dict[str, str] = {}
        for enc, plain in re.findall(r"^([^\n>-][^\n]*?)\s*->\s*([^\n]+)$", prompt, flags=re.M):
            enc_words = enc.strip().split()
            plain_words = plain.strip().split()
            if len(enc_words) == len(plain_words):
                for e, p in zip(enc_words, plain_words):
                    mappings[e] = p
        target_match = re.search(r"Now, decrypt the following text:\s*([^\n\"]+)", prompt, flags=re.I)
        if mappings and target_match:
            target_words = target_match.group(1).strip().split()
            decoded = " ".join(mappings.get(w, "?") for w in target_words)
            known = sum(1 for w in target_words if w in mappings)
            return (
                f"Build a word-level substitution table from the examples. "
                f"It decodes {known}/{len(target_words)} target tokens directly as: {decoded}.\\boxed{{{ans}}}"
            )
        return f"Use the example plaintext pairs as a substitution table, then decode the target phrase.\\boxed{{{ans}}}"

    if category == "bit_manipulation":
        return (
            "Compare each 8-bit input-output example bitwise, infer the consistent shift/rotation/boolean pattern, "
            f"then apply it to the target byte.\\boxed{{{ans}}}"
        )

    if category == "equation":
        return (
            "Identify which operator rule is demonstrated by the examples, including digit/string formatting, "
            f"then apply the same rule to the target expression.\\boxed{{{ans}}}"
        )

    return f"Infer the hidden rule from the demonstrations and apply it to the target.\\boxed{{{ans}}}"


def apply_chat(tokenizer, user_text: str) -> str:
    messages = [{"role": "user", "content": user_text}]
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True,
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        return f"User: {user_text}\nAssistant:"


def eos_text(tokenizer) -> str:
    return tokenizer.eos_token or ""


def build_training_records(df: pd.DataFrame) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        prompt = str(row["prompt"])
        answer = str(row["answer"]).strip()
        category = classify_prompt(prompt)

        # CoT-formatted example.
        records.append(
            {
                "prompt": prompt,
                "completion": make_reasoning(prompt, answer, category),
                "category": category,
                "kind": "cot",
            }
        )

        # Answer-only target prevents the model from over-producing verbose traces.
        if category in HARD_CATEGORIES:
            repeat = max(1, CFG.hard_repeat)
        else:
            repeat = 1
        for _ in range(repeat):
            records.append(
                {
                    "prompt": prompt,
                    "completion": f"\\boxed{{{answer}}}",
                    "category": category,
                    "kind": "answer_only",
                }
            )
    random.Random(CFG.seed).shuffle(records)
    return records


class CompletionDataset(Dataset):
    def __init__(self, records: Sequence[Dict[str, str]], tokenizer, max_length: int):
        self.records = list(records)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Dict[str, List[int]]:
        row = self.records[idx]
        prompt_text = apply_chat(self.tokenizer, row["prompt"] + PROMPT_SUFFIX)
        completion = row["completion"] + eos_text(self.tokenizer)
        prompt_ids = self.tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        comp_ids = self.tokenizer(completion, add_special_tokens=False)["input_ids"]
        ids = prompt_ids + comp_ids
        labels = [-100] * len(prompt_ids) + comp_ids[:]

        if len(ids) > self.max_length:
            overflow = len(ids) - self.max_length
            ids = ids[overflow:]
            labels = labels[overflow:]
            if all(v == -100 for v in labels):
                ids = comp_ids[-self.max_length :]
                labels = ids[:]
        return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)}


class DataCollator:
    def __init__(self, tokenizer, pad_to_multiple_of: int = 8):
        self.pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, features: Sequence[Dict[str, List[int]]]) -> Dict[str, torch.Tensor]:
        max_len = max(len(f["input_ids"]) for f in features)
        if self.pad_to_multiple_of:
            max_len = ((max_len + self.pad_to_multiple_of - 1) // self.pad_to_multiple_of) * self.pad_to_multiple_of
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for f in features:
            pad = max_len - len(f["input_ids"])
            batch["input_ids"].append(f["input_ids"] + [self.pad_id] * pad)
            batch["attention_mask"].append(f["attention_mask"] + [0] * pad)
            batch["labels"].append(f["labels"] + [-100] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}


def make_submission_zip(adapter_dir: str, zip_path: str) -> None:
    zp = Path(zip_path)
    zp.parent.mkdir(parents=True, exist_ok=True)
    if zp.exists():
        zp.unlink()
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(adapter_dir):
            for name in files:
                full = Path(root) / name
                zf.write(full, str(full.relative_to(adapter_dir)))
    print(f"Created {zp}")


def main() -> None:
    set_seed(CFG.seed)
    train_csv = find_train_csv()
    df = pd.read_csv(train_csv)
    if CFG.max_train_rows and CFG.max_train_rows > 0:
        df = df.sample(n=min(CFG.max_train_rows, len(df)), random_state=CFG.seed)
    for col in ["prompt", "answer"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    cats = Counter(classify_prompt(str(p)) for p in df["prompt"])
    print("Rows by category:", dict(cats))
    records = build_training_records(df)
    print("Training records:", len(records), "kinds:", dict(Counter(r["kind"] for r in records)))

    model_path = resolve_model_path(CFG.base_model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    try:
        model.gradient_checkpointing_enable()
    except Exception:
        pass

    if CFG.lora_rank > 32:
        raise ValueError("Competition adapter rank must be <=32")
    model = get_peft_model(
        model,
        LoraConfig(
            r=CFG.lora_rank,
            lora_alpha=CFG.lora_alpha,
            target_modules=CFG.target_modules,
            lora_dropout=CFG.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        ),
    )
    model.print_trainable_parameters()

    ds = CompletionDataset(records, tokenizer, CFG.max_length)
    args = TrainingArguments(
        output_dir=CFG.output_dir,
        num_train_epochs=CFG.epochs,
        per_device_train_batch_size=CFG.per_device_batch,
        gradient_accumulation_steps=CFG.grad_accum,
        learning_rate=CFG.lr,
        warmup_ratio=CFG.warmup_ratio,
        lr_scheduler_type="cosine",
        weight_decay=0.0,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        bf16=torch.cuda.is_available(),
        fp16=False,
        optim="adamw_torch",
        dataloader_num_workers=2,
        gradient_checkpointing=True,
    )
    trainer = Trainer(model=model, args=args, train_dataset=ds, data_collator=DataCollator(tokenizer))
    trainer.train()

    out = Path(CFG.output_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    make_submission_zip(str(out), CFG.zip_path)


if __name__ == "__main__":
    main()
