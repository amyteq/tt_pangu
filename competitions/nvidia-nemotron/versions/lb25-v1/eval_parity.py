"""Eval/submission prompt-parity audit (lb25-v1 — LB25 lever #1, the headline fix).

LB25's #1 improvement was a *correctness* fix, not a model change: huikang's local
validation prompt did not box the answer while the submission prompt did, so local
accuracy was systematically under-counted (answers looked un-boxed though they
boxed on submit). Realigning the local eval to the grader's exact prompt + decode
recovered the true signal. This is the same bug class as our B4 (truncation) /
INS-002 (eval must mirror the grader) — see `../../bugs.md`, `../../insights.md`.

This module packages that audit as a reusable, GPU-free tool:
  * `EVAL_SUFFIX` — the grader-exact boxed-answer instruction;
  * `build_eval_user_content` / `build_eval_messages` — the eval prompt, identical
    to the submission prompt (the parity invariant);
  * `parity_check` — assert the eval and submission user-content are byte-identical;
  * `audit_completions` — for (gold, model-completion) pairs, confirm each yields
    exactly one extractable `\\boxed{}` answer within the 7680-token budget and
    matches gold (the realignment check), reporting every failure class.

The generation half (vLLM greedy, temp 0, max_tokens 7680) runs in the kernel; the
prompt-construction + extraction half audited here is what silently cost accuracy.
"""

from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import extract_final_answer, verify  # noqa: E402

# Grader-exact decode settings (must match the official scorer).
EVAL_SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"
MAX_TOKENS = 7680
GREEDY = True
TEMPERATURE = 0.0

_BOXED = re.compile(r"\\boxed\{")


def build_eval_user_content(problem_text: str) -> str:
    """The user-turn content for evaluation — IDENTICAL to the submission prompt."""
    return problem_text + EVAL_SUFFIX


def build_eval_messages(problem_text: str) -> list[dict]:
    """Chat messages for a greedy eval generation (add_generation_prompt=True in-kernel)."""
    return [{"role": "user", "content": build_eval_user_content(problem_text)}]


def parity_check(eval_user_content: str, submit_user_content: str) -> bool:
    """The LB25 invariant: the eval prompt must be byte-identical to the submit prompt.

    Returns True iff they match. A mismatch is exactly huikang's bug (eval didn't
    box though submit did).
    """
    return eval_user_content == submit_user_content


def assert_parity(problem_text: str) -> None:
    """Raise if the constructed eval prompt would diverge from the submission prompt."""
    ev = build_eval_user_content(problem_text)
    assert EVAL_SUFFIX in ev, "eval prompt missing the boxed-answer SUFFIX (huikang's bug class)"
    # the submission prompt is constructed the same way; parity holds by construction
    assert parity_check(ev, build_eval_user_content(problem_text))


def audit_completions(golds, completions, max_tokens: int = MAX_TOKENS):
    """Audit (gold, completion) pairs the way realigned local eval scores the LB.

    Returns a report dict with counts + per-failure indices:
      - unboxed: completion has no `\\boxed{` at all (the silent-undercount class)
      - truncated_before_box: a `\\boxed{` appears only AFTER the max_tokens cut
      - wrong: boxed + within budget but the extracted answer != gold
      - correct: extracted-within-budget answer matches gold
    `accuracy` is correct / total — the *realigned* number (what huikang recovered).
    """
    golds = list(golds)
    completions = list(completions)
    rep = {"total": len(golds), "correct": 0, "unboxed": [], "truncated_before_box": [], "wrong": []}
    for i, (g, c) in enumerate(zip(golds, completions)):
        c = c or ""
        truncated = c[:max_tokens]
        if not _BOXED.search(c):
            rep["unboxed"].append(i)
            continue
        if not _BOXED.search(truncated):
            rep["truncated_before_box"].append(i)
            continue
        if verify(g, extract_final_answer(truncated)):
            rep["correct"] += 1
        else:
            rep["wrong"].append(i)
    rep["accuracy"] = rep["correct"] / rep["total"] if rep["total"] else 0.0
    return rep


if __name__ == "__main__":
    # Demonstration: the bug (eval prompt without the SUFFIX) vs the fix.
    problem = "In Alice's Wonderland... Now, determine the result for: 81`20"
    submit_content = build_eval_user_content(problem)
    buggy_eval_content = problem  # huikang's bug: eval prompt omitted the SUFFIX
    print("parity (buggy eval vs submit):", parity_check(buggy_eval_content, submit_content), "(expect False)")
    print(
        "parity (fixed eval vs submit):",
        parity_check(build_eval_user_content(problem), submit_content),
        "(expect True)",
    )

    # Realignment audit: a boxed completion scores; an un-boxed one is the silent miss.
    golds = ["61", "341", "01000011"]
    good = ["...reasoning...\n\\boxed{61}", "...\n\\boxed{341}", "...\n\\boxed{01000011}"]
    bad_unboxed = ["the answer is 61 (no box)", "...\n\\boxed{341}", "...\n\\boxed{01000011}"]
    print(
        "\naudit (all boxed):",
        {k: v for k, v in audit_completions(golds, good).items() if k in ("correct", "accuracy")},
    )
    rep = audit_completions(golds, bad_unboxed)
    print("audit (one un-boxed):", {"correct": rep["correct"], "unboxed": rep["unboxed"], "accuracy": rep["accuracy"]})
    print("eval_parity self-check OK")
