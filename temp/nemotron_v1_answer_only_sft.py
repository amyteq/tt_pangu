#!/usr/bin/env python3
"""
Version 1: answer-only SFT baseline for the Kaggle NVIDIA Nemotron Model
Reasoning Challenge.

Goal
----
Train a rank-32 LoRA adapter that teaches the model to emit only the final
answer inside \boxed{...}. This is intentionally simple and robust: no external
LLM, no synthetic data, no reliance on public pre-trained adapters.

Expected Kaggle usage
---------------------
Run as a Kaggle notebook/script with train.csv available from the competition
input. The script writes /kaggle/working/submission.zip containing the LoRA
adapter files at the zip root.

Environment variables you may tune
----------------------------------
TRAIN_CSV, BASE_MODEL, OUTPUT_DIR, ZIP_PATH, MAX_TRAIN_ROWS, MAX_LENGTH,
LORA_RANK, LORA_ALPHA, LR, EPOCHS, PER_DEVICE_BATCH, GRAD_ACCUM.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

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
except Exception:  # local dry runs may not have kagglehub
    kagglehub = None

from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments


@dataclass
class CFG:
    train_csv: str = os.getenv("TRAIN_CSV", "")
    base_model: str = os.getenv(
        "BASE_MODEL", "metric/nemotron-3-nano-30b-a3b-bf16/transformers/default"
    )
    output_dir: str = os.getenv("OUTPUT_DIR", "/kaggle/working/adapter_v1_answer_only")
    zip_path: str = os.getenv("ZIP_PATH", "/kaggle/working/submission.zip")

    seed: int = int(os.getenv("SEED", "2026"))
    max_train_rows: int = int(os.getenv("MAX_TRAIN_ROWS", "0"))  # 0 = all rows
    max_length: int = int(os.getenv("MAX_LENGTH", "1024"))

    lora_rank: int = int(os.getenv("LORA_RANK", "32"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_dropout: float = float(os.getenv("LORA_DROPOUT", "0.05"))

    lr: float = float(os.getenv("LR", "5e-5"))
    epochs: float = float(os.getenv("EPOCHS", "1"))
    per_device_batch: int = int(os.getenv("PER_DEVICE_BATCH", "1"))
    grad_accum: int = int(os.getenv("GRAD_ACCUM", "16"))
    warmup_ratio: float = float(os.getenv("WARMUP_RATIO", "0.03"))

    # Nemotron-3-Nano hybrid/MoE modules. Regex target works for PEFT on this model.
    target_modules: str = os.getenv(
        "TARGET_MODULES", r".*\.(in_proj|out_proj|up_proj|down_proj|x_proj|dt_proj)$"
    )


PROMPT_SUFFIX = "\nPlease put your final answer inside `\\boxed{}`. For example: `\\boxed{your answer}`"


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
        raise RuntimeError(
            "BASE_MODEL is not a local path and kagglehub is unavailable. "
            "Set BASE_MODEL to a local model directory."
        )
    return kagglehub.model_download(model_id_or_path)


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


def completion_text(answer: str, tokenizer) -> str:
    # Kaggle's metric extracts boxed answers, so make the supervised target match that.
    eos = tokenizer.eos_token or ""
    return f"\\boxed{{{str(answer).strip()}}}{eos}"


class PromptCompletionDataset(Dataset):
    def __init__(self, rows: Sequence[Dict[str, str]], tokenizer, max_length: int):
        self.rows = list(rows)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> Dict[str, List[int]]:
        row = self.rows[idx]
        prompt_text = apply_chat(self.tokenizer, row["prompt"] + PROMPT_SUFFIX)
        answer_text = completion_text(row["answer"], self.tokenizer)

        prompt_ids = self.tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        answer_ids = self.tokenizer(answer_text, add_special_tokens=False)["input_ids"]

        ids = prompt_ids + answer_ids
        labels = [-100] * len(prompt_ids) + answer_ids[:]

        if len(ids) > self.max_length:
            # Keep the answer and the end of the prompt. These prompts are short, but this
            # makes the script safe if you add longer synthetic CoT examples later.
            overflow = len(ids) - self.max_length
            ids = ids[overflow:]
            labels = labels[overflow:]
            if all(x == -100 for x in labels):
                ids = answer_ids[-self.max_length :]
                labels = ids[:]

        return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)}


class DataCollator:
    def __init__(self, tokenizer, pad_to_multiple_of: int = 8):
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of
        self.pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    def __call__(self, features: Sequence[Dict[str, List[int]]]) -> Dict[str, torch.Tensor]:
        max_len = max(len(f["input_ids"]) for f in features)
        if self.pad_to_multiple_of:
            max_len = ((max_len + self.pad_to_multiple_of - 1) // self.pad_to_multiple_of) * self.pad_to_multiple_of

        batch = {"input_ids": [], "labels": [], "attention_mask": []}
        for f in features:
            pad = max_len - len(f["input_ids"])
            batch["input_ids"].append(f["input_ids"] + [self.pad_id] * pad)
            batch["labels"].append(f["labels"] + [-100] * pad)
            batch["attention_mask"].append(f["attention_mask"] + [0] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}


def load_rows(path: str) -> List[Dict[str, str]]:
    df = pd.read_csv(path)
    required = {"prompt", "answer"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"train.csv missing columns: {missing}")
    if CFG.max_train_rows and CFG.max_train_rows > 0:
        df = df.sample(n=min(CFG.max_train_rows, len(df)), random_state=CFG.seed)
    rows = df[["prompt", "answer"]].astype(str).to_dict("records")
    random.Random(CFG.seed).shuffle(rows)
    return rows


def make_submission_zip(adapter_dir: str, zip_path: str) -> None:
    zip_file = Path(zip_path)
    zip_file.parent.mkdir(parents=True, exist_ok=True)
    if zip_file.exists():
        zip_file.unlink()
    with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(adapter_dir):
            for name in files:
                full = Path(root) / name
                rel = full.relative_to(adapter_dir)
                zf.write(full, str(rel))
    print(f"Created {zip_file} with LoRA adapter files at zip root.")


def main() -> None:
    set_seed(CFG.seed)
    train_csv = find_train_csv()
    print(f"Using train csv: {train_csv}")

    model_path = resolve_model_path(CFG.base_model)
    print(f"Using base model: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    rows = load_rows(train_csv)
    print(f"Training rows: {len(rows)}")

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
        raise ValueError("Competition adapter rank must be <= 32")

    lora_config = LoraConfig(
        r=CFG.lora_rank,
        lora_alpha=CFG.lora_alpha,
        target_modules=CFG.target_modules,
        lora_dropout=CFG.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    ds = PromptCompletionDataset(rows, tokenizer, CFG.max_length)
    collator = DataCollator(tokenizer)

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

    trainer = Trainer(model=model, args=args, train_dataset=ds, data_collator=collator)
    trainer.train()

    out = Path(CFG.output_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    make_submission_zip(str(out), CFG.zip_path)


if __name__ == "__main__":
    main()
