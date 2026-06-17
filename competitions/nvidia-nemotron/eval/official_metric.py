"""Local port of the competition's grading logic (T12).

Mirrors the official metric so local evaluation matches the leaderboard:
  - extract the LAST `\\boxed{...}`; if absent, fall back to "final answer is:" patterns,
    then to the last number in the text (the grader's documented fallbacks);
  - a prediction is correct if it matches the gold answer EXACTLY as a string
    (case-insensitive) OR numerically within a 1e-2 relative tolerance.

Pure functions only (no model / GPU). The generation half of the official `score()`
(vLLM greedy, `max_tokens=7680`, `temp=0`) runs inside the kernel; this module is the
extract+verify+accuracy half so a local held-out set can be scored the same way the LB
scores it. Source of the rules: competition evaluation page + the embedded scorer in the
public `lopure/amplify-...` notebook (see `references.md`).

Usage:
    from official_metric import extract_final_answer, verify, accuracy
    acc = accuracy(gold_list, raw_model_outputs)   # raw outputs -> extract -> verify
"""

from __future__ import annotations

import math
import re

_BOXED = re.compile(r"\\boxed\{([^}]*)(?:\}|$)")
_FALLBACK_PATTERNS = [
    r"final answer is:?\s*([^\n]+)",
    r"final answer\s*[:：]\s*([^\n]+)",
    r"answer is:?\s*([^\n]+)",
]
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def extract_final_answer(text: str | None) -> str:
    """Extract the final answer from raw model output, mirroring the official extractor."""
    if text is None:
        return "NOT_FOUND"
    matches = _BOXED.findall(text)
    if matches:
        non_empty = [m.strip() for m in matches if m.strip()]
        if non_empty:
            return non_empty[-1]
        return matches[-1].strip()
    for pat in _FALLBACK_PATTERNS:
        m = re.findall(pat, text, re.IGNORECASE)
        if m:
            return m[-1].strip()
    nums = _NUMBER.findall(text)
    if nums:
        return nums[-1]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else "NOT_FOUND"


_LEADING_ZERO_INT = re.compile(r"0\d+")  # e.g. binary "01000011" — leading zero is significant


def verify(gold: str, predicted: str) -> bool:
    """True if predicted matches gold.

    Numeric comparison (rel 1e-2) is used ONLY when neither side is a leading-zero
    integer; binary/leading-zero answers are string-matched so `01000011` != `1000011`
    (the official metric's fixed binary behaviour). Strings are case-insensitive.
    """
    gold = str(gold).strip()
    predicted = str(predicted).strip()
    if not _LEADING_ZERO_INT.fullmatch(gold) and not _LEADING_ZERO_INT.fullmatch(predicted):
        try:
            return math.isclose(float(predicted), float(gold), rel_tol=1e-2, abs_tol=1e-5)
        except (ValueError, TypeError):
            pass
    return predicted.lower() == gold.lower()


def accuracy(golds, raw_outputs) -> float:
    """Accuracy over raw model outputs: extract each then verify against gold."""
    golds = list(golds)
    raw_outputs = list(raw_outputs)
    if not golds:
        return 0.0
    correct = sum(verify(g, extract_final_answer(o)) for g, o in zip(golds, raw_outputs))
    return correct / len(golds)
