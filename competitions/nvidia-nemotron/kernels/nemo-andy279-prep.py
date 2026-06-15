# ruff: noqa: E402  (Kaggle kernel: imports follow the in-kernel pip install)
# Nemo andy279 prep — fetch the public solver-guided teacher-CoT subset (internet ON).
# Downloads andy279/nemotron-reasoning-challenge (correct-only SFT traces from external
# teachers: DeepSeek V3.2 / Nemotron-Super-120B / GPT-5.4), classifies each by prompt,
# and saves ONLY the hard categories (bit / equation / cipher) as a JSONL the offline
# training kernel attaches. Human-authorized 2026-06-15 (external-teacher CoT; rules
# permit synthetic/external data — verify the official rules page before final submit).
import json
import re
import subprocess
import sys

import os

subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "datasets", "huggingface_hub"],
    check=True,
)
from datasets import load_dataset
from huggingface_hub import login

# andy279 is a GATED HF dataset → authenticate. Token resolution order:
#   1) Kaggle Secret HF_TOKEN, 2) env HF_TOKEN, 3) the embedded constant below.
# This repo copy keeps _HF_TOKEN EMPTY (never commit a credential); the value is
# injected only into the private copy pushed to Kaggle (read from .vscode/.env).
_HF_TOKEN = ""  # noqa: S105  (injected at push time; empty in source control)
_tok = os.environ.get("HF_TOKEN") or _HF_TOKEN
try:
    from kaggle_secrets import UserSecretsClient

    if not _tok:
        _tok = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:  # noqa: BLE001
    pass
assert _tok, "no HF token (set Kaggle Secret HF_TOKEN, env HF_TOKEN, or inject _HF_TOKEN)"
login(token=_tok)
print("HF login: ok")


def classify(p):
    pl = (p or "").lower()
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


_BOXED = re.compile(r"\\boxed\{([^}]*)(?:\}|$)")
KEEP_CATS = {"bit", "equation", "cipher"}

ds = load_dataset("andy279/nemotron-reasoning-challenge", split="train", token=_tok)
print("andy279 train rows:", len(ds))
print("example keys:", list(ds[0].keys()))

kept = []
by_cat = {}
for ex in ds:
    msgs = ex.get("messages")
    if not msgs or len(msgs) < 2:
        continue
    user = next((m.get("content") for m in msgs if m.get("role") == "user"), None)
    asst = next((m.get("content") for m in msgs if m.get("role") == "assistant"), None)
    if not user or not asst:
        continue
    if not _BOXED.search(asst):  # require a \boxed{} answer in the response
        continue
    cat = classify(user)
    if cat not in KEEP_CATS:
        continue
    kept.append({"category": cat, "prompt": user, "response": asst})
    by_cat[cat] = by_cat.get(cat, 0) + 1

out_path = "/kaggle/working/andy279_hardcat.jsonl"
with open(out_path, "w", encoding="utf-8") as f:
    for rec in kept:
        f.write(json.dumps(rec) + "\n")
print(f"kept {len(kept)} hard-cat teacher CoTs by category: {by_cat}")
print("wrote", out_path)
