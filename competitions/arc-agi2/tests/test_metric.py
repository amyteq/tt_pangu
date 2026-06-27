"""Unit tests for the ARC-AGI-2 pass@2 metric.

Run:  python -m pytest competitions/arc-agi2/tests/ -q
"""

import sys
from pathlib import Path

import pytest

# make eval/ importable without packaging
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from metric import grids_equal, output_solved, score_submission  # noqa: E402


def test_grids_equal_basic():
    assert grids_equal([[1, 2], [3, 4]], [[1, 2], [3, 4]])
    assert not grids_equal([[1, 2]], [[1, 2], [3, 4]])  # different #rows
    assert not grids_equal([[1, 2, 3]], [[1, 2]])  # different row len
    assert not grids_equal([[1, 2]], [[1, 9]])  # different cell
    assert not grids_equal(None, [[1]])


def test_grids_equal_tuple_vs_list():
    # a prediction may arrive as tuples; equality must be value-based
    assert grids_equal(((1, 2), (3, 4)), [[1, 2], [3, 4]])


def test_output_solved_either_attempt():
    sol = [[1, 1], [1, 1]]
    assert output_solved({"attempt_1": sol, "attempt_2": [[0]]}, sol)  # first hits
    assert output_solved({"attempt_1": [[0]], "attempt_2": sol}, sol)  # second hits
    assert not output_solved({"attempt_1": [[0]], "attempt_2": [[9]]}, sol)  # neither


def test_score_all_correct():
    sol = {"t1": [[[1]]], "t2": [[[2]]]}
    sub = {
        "t1": [{"attempt_1": [[1]], "attempt_2": [[0]]}],
        "t2": [{"attempt_1": [[9]], "attempt_2": [[2]]}],
    }
    r = score_submission(sub, sol)
    assert r.score == 1.0
    assert r.flat_per_output == 1.0
    assert r.n_tasks == 2 and r.n_outputs == 2 and r.n_outputs_solved == 2


def test_score_half():
    sol = {"t1": [[[1]]], "t2": [[[2]]]}
    sub = {
        "t1": [{"attempt_1": [[1]], "attempt_2": [[0]]}],
        "t2": [{"attempt_1": [[0]], "attempt_2": [[0]]}],
    }
    r = score_submission(sub, sol)
    assert r.score == 0.5


def test_missing_task_scores_zero():
    sol = {"t1": [[[1]]], "t2": [[[2]]]}
    sub = {"t1": [{"attempt_1": [[1]], "attempt_2": [[1]]}]}  # t2 missing entirely
    r = score_submission(sub, sol)
    assert r.score == 0.5
    assert r.missing_tasks == ["t2"]


def test_multitest_per_task_vs_flat_differ():
    # one task with 2 test outputs (1 solved), one task with 1 test output (solved)
    sol = {"multi": [[[1]], [[2]]], "single": [[[3]]]}
    sub = {
        "multi": [
            {"attempt_1": [[1]], "attempt_2": [[0]]},  # solved
            {"attempt_1": [[0]], "attempt_2": [[0]]},  # not solved
        ],
        "single": [{"attempt_1": [[3]], "attempt_2": [[0]]}],  # solved
    }
    r = score_submission(sub, sol)
    # per-task: multi=0.5, single=1.0 -> mean 0.75
    assert r.score == pytest.approx(0.75)
    # flat: 2 of 3 outputs solved -> 0.6667
    assert r.flat_per_output == pytest.approx(2 / 3)


def test_strict_rejects_unknown_task():
    sol = {"t1": [[[1]]]}
    sub = {"t1": [{"attempt_1": [[1]], "attempt_2": [[1]]}], "ghost": [{"attempt_1": [[0]]}]}
    with pytest.raises(ValueError):
        score_submission(sub, sol, strict=True)
