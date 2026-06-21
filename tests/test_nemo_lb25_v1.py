"""Tests for the lb25-v1 Nemotron post-LB25 (huikang Progress-Prize) pipeline.

Covers the LB25-specific levers (no GPU, no network):
  * eval/submission prompt parity audit (lever #1) — the boxed-prompt fix;
  * reorganized bit CoT + grader-faithful verify (lever #5);
  * easy-category + cipher-prefix synth round-trips (levers #3/#4);
  * equation reversal symmetry (lever #2) — runs only when the gitignored
    competition train.csv is present locally, else skipped (keeps CI green).
"""

import os
import sys

import pytest

_VDIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "competitions",
    "nvidia-nemotron",
    "versions",
    "lb25-v1",
)
sys.path.insert(0, _VDIR)
sys.path.insert(0, os.path.join(os.path.dirname(_VDIR), "..", "eval"))
sys.path.insert(0, os.path.join(os.path.dirname(_VDIR), "..", "lib"))

import eval_parity  # noqa: E402
import bit_cot  # noqa: E402
import easy_cat_synth  # noqa: E402
from official_metric import extract_final_answer, verify  # noqa: E402

TRAIN = os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")


def test_eval_parity_detects_boxed_prompt_bug():
    problem = "Now, determine the result for: 81`20"
    submit = eval_parity.build_eval_user_content(problem)
    # huikang's bug: eval prompt omitted the SUFFIX -> not byte-identical to submit
    assert not eval_parity.parity_check(problem, submit)
    # the fix: eval prompt built the same way -> parity holds
    assert eval_parity.parity_check(eval_parity.build_eval_user_content(problem), submit)
    assert eval_parity.EVAL_SUFFIX in submit


def test_eval_parity_audit_counts_failure_classes():
    golds = ["61", "341", "01000011"]
    good = ["x\n\\boxed{61}", "y\n\\boxed{341}", "z\n\\boxed{01000011}"]
    rep = eval_parity.audit_completions(golds, good)
    assert rep["correct"] == 3 and rep["accuracy"] == 1.0
    # an un-boxed completion is the silent-undercount class huikang fixed
    rep2 = eval_parity.audit_completions(golds, ["the answer is 61", good[1], good[2]])
    assert rep2["unboxed"] == [0] and rep2["correct"] == 2
    # a box only after the token budget -> truncated_before_box
    rep3 = eval_parity.audit_completions(["61"], ["A" * 7700 + "\\boxed{61}"], max_tokens=7680)
    assert rep3["truncated_before_box"] == [0]


def test_bit_cot_solves_and_verifies():
    ins = [0b00010101, 0b11000101, 0b10100010, 0b00111111, 0b01110101]
    prompt = (
        "8-bit binary. Here are some examples of input -> output:\n"
        + "\n".join(f"{i:08b} -> {(~i) & 0xFF:08b}" for i in ins)
        + "\nNow, determine the output for: 01101001"
    )
    out = bit_cot.bit_solve(prompt)
    assert out is not None
    ans, cot = out
    assert ans == f"{(~0b01101001) & 0xFF:08b}"
    assert "\\boxed{" in cot and verify(ans, extract_final_answer(cot))


def test_bit_verify_leading_zero_exact():
    assert bit_cot.bit_verify("01000011", "01000011")
    assert not bit_cot.bit_verify("1000011", "01000011")  # binary leading-zero is significant
    assert bit_cot.bit_verify("42", "42.0")  # numeric tolerance for non-leading-zero


def test_easy_cat_synth_roundtrips():
    recs = easy_cat_synth.build_easy_corpus(n_per_cat=15, seed=3)
    assert len(recs) > 0
    cats = {r["category"] for r in recs}
    assert cats <= {"cipher", "numeral", "unit", "gravity"}
    for r in recs:
        assert verify(r["answer"], extract_final_answer(r["cot"]))


@pytest.mark.skipif(not os.path.exists(TRAIN), reason="competition train.csv not present (gitignored)")
def test_eq_reversal_symmetry_high():
    import eq_reversal

    stats, rules_full, rules_sym = eq_reversal.run(TRAIN)
    assert stats["deduce"] > 0
    # the reversal symmetry (a single feasible mode) should hold for the large majority
    frac = stats["single_mode"] / stats["deduce"]
    assert frac >= 0.80, f"single-mode (reversal symmetry) only {frac:.2f}"
    assert rules_sym < rules_full  # the symmetry strictly reduces the search
