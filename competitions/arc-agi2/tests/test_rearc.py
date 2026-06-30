"""Unit tests for the RE-ARC pipeline (solver/rearc.py) using fake generators/verifiers,
so they run without the cloned re-arc repo. Run:  python -m pytest tests/test_rearc.py -q
"""

import json
import sys
from pathlib import Path

_COMP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_COMP))
sys.path.insert(0, str(_COMP / "eval"))

from arc_io import load_tasks_dir  # noqa: E402

from solver.rearc import _valid, build_tasks_for_key, generate_examples  # noqa: E402


def vflip(g):
    return tuple(reversed(g))


def _make_gen(seq):
    it = iter(seq)

    def gen(diff_lb, diff_ub):
        return next(it)  # StopIteration when exhausted -> caught as a failed attempt

    return gen


def test_valid_grid_checks():
    assert _valid([[0, 1], [2, 3]])
    assert not _valid([[0, 1], [2]])  # ragged
    assert not _valid([[0, 10]])  # out of 0-9
    assert not _valid([])


def test_generate_examples_filters_and_dedups():
    G1, G2, G3 = ((1, 2), (3, 4)), ((5, 6), (7, 8)), ((1, 1), (2, 3))
    seq = [
        {"input": G1, "output": vflip(G1)},  # valid
        {"input": G1, "output": vflip(G1)},  # duplicate input -> dropped
        {"input": G2, "output": ((9, 9), (9, 9))},  # verifier mismatch -> dropped
        {"input": ((0, 0), (0, 0)), "output": ((0, 0), (0, 0))},  # degenerate i==o -> dropped
        {"input": G3, "output": vflip(G3)},  # valid
        {"input": G2, "output": vflip(G2)},  # valid
    ]
    ex = generate_examples(_make_gen(seq), vflip, n=3, diff_lb=0, diff_ub=1, max_attempts=100)
    assert len(ex) == 3
    # converted to lists, in acceptance order G1, G3, G2
    assert ex[0]["input"] == [[1, 2], [3, 4]] and ex[0]["output"] == [[3, 4], [1, 2]]
    assert all(isinstance(e["input"], list) and isinstance(e["input"][0], list) for e in ex)
    # every kept example is verifier-consistent and non-degenerate
    for e in ex:
        assert e["input"] != e["output"]


def test_generate_examples_respects_max_attempts():
    # a generator that always fails verification -> 0 kept, bounded by max_attempts
    bad = _make_gen([{"input": ((1, 2),), "output": ((9, 9),)}] * 1000)
    ex = generate_examples(bad, vflip, n=5, diff_lb=0, diff_ub=1, max_attempts=20)
    assert ex == []


def test_build_tasks_for_key_chunks_into_arc_tasks():
    grids = [((i, i + 1), (i + 2, i + 3)) for i in range(0, 9)]  # 9 distinct grids (values 0-9 safe via mod)
    grids = [tuple(tuple(c % 10 for c in row) for row in g) for g in grids]
    seq = [{"input": g, "output": vflip(g)} for g in grids]
    tasks = build_tasks_for_key(_make_gen(seq), vflip, n_tasks=2, demos=2, diff_lb=0, diff_ub=1, max_attempts=200)
    assert len(tasks) == 2
    for t in tasks:
        assert len(t["train"]) == 2 and len(t["test"]) == 1
        assert "input" in t["test"][0] and "output" in t["test"][0]


def test_corpus_roundtrips_through_load_tasks_dir(tmp_path):
    grids = [tuple(tuple((i + j) % 10 for j in range(3)) for i in range(2)) for i in range(6)]
    # ensure distinct + non-degenerate under vflip
    seq = [{"input": g, "output": vflip(g)} for g in grids]
    tasks = build_tasks_for_key(_make_gen(seq), vflip, n_tasks=2, demos=2, diff_lb=0, diff_ub=1, max_attempts=200)
    for ti, t in enumerate(tasks):
        (tmp_path / f"fake_{ti:03d}.json").write_text(json.dumps(t))
    loaded = load_tasks_dir(tmp_path)
    assert len(loaded) == len(tasks)
    for _tid, task in loaded.items():
        assert len(task.train) == 2
        assert task.test_outputs is not None and len(task.test_outputs) == 1
        assert _valid(task.test_inputs[0]) and _valid(task.test_outputs[0])
