"""GPU/model layer for the TTT solver (rung-1: Qwen2.5-0.5B + per-task LoRA TTT).

Implements the `DecodeFn` that `run.solve_task` injects: for each task we attach a fresh
LoRA, fine-tune it on the task's leave-one-out augmented demos (test-time training), then
greedily decode the augmented test prompts. De-augmentation + PoE/vote selection happen in
the model-agnostic core (`selection.py`).

torch / transformers / peft are imported lazily inside methods so this module (and the rest
of `solver/`) still imports on a CPU box without those deps installed.

Reset between tasks: the LoRA is created once; its freshly-initialised weights (A=kaiming,
B=0 -> identity) are snapshotted and reloaded before each task so every task starts from the
same pretrained base with a blank adapter.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from .run import solve_task
from .ttt_data import build_ttt_examples

Grid = list

_DIGIT_LINE = re.compile(r"^[0-9]+$")


def parse_generated_grid(text: str) -> Grid:
    """Extract the leading block of all-digit rows from generated text (lenient).

    Stops at the first non-digit / blank line so trailing model chatter is ignored. Ragged
    rows (the model miscounts a width by a cell or two) are NORMALISED to the modal row width
    by padding with 0 / truncating, rather than discarded — a best-effort rectangular grid
    still feeds voting/PoE and can match, whereas an empty decode never can.
    Returns [] only if no digit rows were produced at all.
    """
    lines = text.lstrip("\n").splitlines()
    rows = []
    for ln in lines:
        s = ln.strip()
        if _DIGIT_LINE.match(s):
            rows.append([int(c) for c in s])
        else:
            break
    if not rows:
        return []
    widths = [len(r) for r in rows]
    if len(set(widths)) == 1:
        return rows
    # ragged -> normalise to the modal width (ties -> the largest of the tied widths)
    from collections import Counter

    counts = Counter(widths)
    top = max(counts.values())
    w = max(width for width, c in counts.items() if c == top)
    return [(r + [0] * w)[:w] for r in rows]


@dataclass
class TTTConfig:
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    lora_rank: int = 32
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    ttt_steps: int = 48
    ttt_lr: float = 1e-4
    ttt_batch_size: int = 1  # recipe default; long packed grids -> keep memory bounded
    n_augmentations: int = 16
    max_seq_len: int = 2048  # examples longer than this are skipped (target tail must stay intact)
    max_new_tokens: int = 1024
    seed: int = 0
    dtype: str = "bfloat16"
    pretrained_adapter: str | None = None  # dir of an offline-pretrained LoRA to init TTT from


class TTTSolver:
    """Loads the base model once; `solve(task)` does per-task TTT + decode."""

    def __init__(self, cfg: TTTConfig | None = None, device: str = "cuda"):
        self.cfg = cfg or TTTConfig()
        self.device = device
        self._load()

    def _load(self):
        import torch
        from peft import LoraConfig, PeftModel, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer

        cfg = self.cfg
        self.tok = AutoTokenizer.from_pretrained(cfg.model_name)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        dtype = getattr(torch, cfg.dtype)
        try:  # transformers >=5 uses `dtype`; older uses `torch_dtype`
            base = AutoModelForCausalLM.from_pretrained(cfg.model_name, dtype=dtype)
        except TypeError:
            base = AutoModelForCausalLM.from_pretrained(cfg.model_name, torch_dtype=dtype)
        if cfg.pretrained_adapter:
            # start every task's TTT from the offline-pretrained adapter (the ARC prior)
            self.model = PeftModel.from_pretrained(base, cfg.pretrained_adapter, is_trainable=True).to(self.device)
        else:
            lora = LoraConfig(
                r=cfg.lora_rank,
                lora_alpha=cfg.lora_alpha,
                lora_dropout=cfg.lora_dropout,
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                task_type="CAUSAL_LM",
            )
            self.model = get_peft_model(base, lora).to(self.device)
        # gradient checkpointing keeps the long-sequence training forward within 24GB.
        # enable_input_require_grads is required for checkpointing with a frozen base + LoRA.
        self.model.gradient_checkpointing_enable()
        self.model.enable_input_require_grads()
        # snapshot the blank adapter so we can reset before every task
        self._init_adapter = copy.deepcopy(self._adapter_state())

    def _adapter_state(self):
        return {k: v.detach().clone() for k, v in self.model.named_parameters() if "lora_" in k}

    def _reset_adapter(self):
        with_no_grad = self.model.named_parameters()
        state = self._init_adapter
        for k, v in with_no_grad:
            if k in state:
                v.data.copy_(state[k].data)

    # --- TTT -----------------------------------------------------------------
    def _train_on_task(self, train_pairs: list[dict]):
        import torch
        from torch.optim import AdamW

        from .augment import build_augmentations

        cfg = self.cfg
        augs = build_augmentations(n=cfg.n_augmentations, seed=cfg.seed)
        examples = build_ttt_examples(train_pairs, augs, seed=cfg.seed)
        # tokenise once + drop examples that exceed max_seq_len (truncating would cut the
        # supervised output tail and corrupt the target).
        tok_examples = []
        for ex in examples:
            p_ids = self.tok(ex.prompt, add_special_tokens=False)["input_ids"]
            t_ids = self.tok(ex.target, add_special_tokens=False)["input_ids"] + [self.tok.eos_token_id]
            if len(p_ids) + len(t_ids) <= cfg.max_seq_len:
                tok_examples.append((p_ids, t_ids))
        self.n_ttt_examples = len(tok_examples)
        if not tok_examples:
            return  # <2 demos or all examples too long: fall back to the base model
        self.model.config.use_cache = False  # required with gradient checkpointing
        self.model.train()
        opt = AdamW([p for p in self.model.parameters() if p.requires_grad], lr=cfg.ttt_lr)
        rng = torch.Generator().manual_seed(cfg.seed)
        n = len(tok_examples)
        for _step in range(cfg.ttt_steps):
            idx = torch.randint(0, n, (cfg.ttt_batch_size,), generator=rng).tolist()
            batch = [tok_examples[i] for i in idx]
            loss = self._batch_loss(batch)
            loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)

    def _batch_loss(self, batch):
        import torch

        input_ids, labels = [], []
        maxlen = 0
        rows = []
        for p_ids, t_ids in batch:  # already tokenised + length-filtered
            ids = p_ids + t_ids
            lab = [-100] * len(p_ids) + t_ids
            rows.append((ids, lab))
            maxlen = max(maxlen, len(ids))
        pad = self.tok.pad_token_id
        for ids, lab in rows:
            d = maxlen - len(ids)
            input_ids.append(ids + [pad] * d)
            labels.append(lab + [-100] * d)
        ii = torch.tensor(input_ids, device=self.device)
        ll = torch.tensor(labels, device=self.device)
        attn = (ii != pad).long()
        out = self.model(input_ids=ii, attention_mask=attn, labels=ll)
        return out.loss

    # --- decode --------------------------------------------------------------
    def _make_decode_fn(self):
        import torch

        def decode_fn(prompt: str):
            self.model.eval()
            self.model.config.use_cache = True  # fast KV-cached greedy decode
            ids = self.tok(prompt, add_special_tokens=False, return_tensors="pt").to(self.device)
            with torch.no_grad():
                out = self.model.generate(
                    **ids,
                    max_new_tokens=self.cfg.max_new_tokens,
                    do_sample=False,
                    num_beams=1,
                    output_scores=True,
                    return_dict_in_generate=True,
                    pad_token_id=self.tok.pad_token_id,
                )
            gen = out.sequences[0][ids["input_ids"].shape[1] :]
            text = self.tok.decode(gen, skip_special_tokens=True)
            grid = parse_generated_grid(text)
            # sequence log-prob = sum of greedy-token log-softmax over generated steps
            logprob = 0.0
            if out.scores:
                for t, score in zip(gen.tolist(), out.scores):
                    logprob += torch.log_softmax(score[0], dim=-1)[t].item()
            return grid, (logprob if grid else None)

        return decode_fn

    # --- public --------------------------------------------------------------
    def solve(self, train_pairs: list[dict], test_inputs: list[Grid]) -> list[dict]:
        import torch

        self._reset_adapter()
        self._train_on_task(train_pairs)
        decode_fn = self._make_decode_fn()
        result = solve_task(
            train_pairs,
            test_inputs,
            decode_fn,
            n_augmentations=self.cfg.n_augmentations,
            seed=self.cfg.seed,
        )
        torch.cuda.empty_cache()
        return result
