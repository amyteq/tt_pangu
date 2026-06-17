"""Tests for the local port of the competition metric (T12)."""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "competitions" / "nvidia-nemotron" / "eval"),
)

import official_metric as om  # noqa: E402


def test_extract_last_boxed():
    assert om.extract_final_answer(r"think... \boxed{01000011}") == "01000011"
    # multiple boxed -> last non-empty
    assert om.extract_final_answer(r"\boxed{1} then \boxed{42}") == "42"


def test_extract_fallbacks():
    assert om.extract_final_answer("The final answer is: 3.14") == "3.14"
    assert om.extract_final_answer("blah 100 in text") == "100"
    assert om.extract_final_answer(None) == "NOT_FOUND"


def test_verify_numeric_tolerance():
    assert om.verify("78.40", "78.4")
    assert om.verify("100", "100.5")  # within 1e-2 rel
    assert not om.verify("100", "120")


def test_verify_string_case_insensitive():
    assert om.verify("cat dog", "CAT DOG")
    assert not om.verify("cat", "dog")


def test_verify_binary_leading_zero_is_string():
    # binary answers must keep leading zeros; treated as string, not float
    assert not om.verify("01000011", "1000011")
    assert om.verify("01000011", "01000011")


def test_accuracy():
    golds = ["01000011", "XLIX", "15.0"]
    raw = [r"\boxed{01000011}", r"\boxed{XLIX}", r"\boxed{15.00}"]
    assert om.accuracy(golds, raw) == 1.0
    assert om.accuracy([], []) == 0.0
