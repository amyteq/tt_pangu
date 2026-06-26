"""Trivial zero-cost baselines — used to validate the eval harness end-to-end and to
establish an absolute floor. None of these "reason"; they exist so a real solver has a
known reference and so the metric is exercised on real data.

Each baseline maps a Task -> list (one entry per test input) of {"attempt_1", "attempt_2"}.
"""

from __future__ import annotations

from collections import Counter

from arc_io import Task


def _as_tuple(grid):
    return tuple(tuple(int(c) for c in row) for row in grid)


def _to_grid(t):
    return [list(row) for row in t]


def identity(task: Task) -> list:
    """attempt_1 = the test input unchanged; attempt_2 = same. (Solves tasks where out==in.)"""
    out = []
    for inp in task.test_inputs:
        out.append({"attempt_1": [row[:] for row in inp], "attempt_2": [row[:] for row in inp]})
    return out


def most_common_train_output(task: Task) -> list:
    """attempt_1 = the most frequent train OUTPUT grid; attempt_2 = the test input.

    Catches "constant output" tasks; pairs with identity as a cheap second guess.
    """
    counts = Counter(_as_tuple(p["output"]) for p in task.train)
    common = _to_grid(counts.most_common(1)[0][0]) if counts else [[0]]
    out = []
    for inp in task.test_inputs:
        out.append({"attempt_1": common, "attempt_2": [row[:] for row in inp]})
    return out


def output_shape_zeros(task: Task) -> list:
    """attempt_1 = zeros in the modal train-output shape; attempt_2 = the test input.

    A structural floor for tasks whose output is a fixed canvas size.
    """
    shapes = Counter((len(p["output"]), len(p["output"][0])) for p in task.train if p["output"])
    if shapes:
        h, w = shapes.most_common(1)[0][0]
    else:
        h, w = 1, 1
    canvas = [[0] * w for _ in range(h)]
    out = []
    for inp in task.test_inputs:
        out.append({"attempt_1": canvas, "attempt_2": [row[:] for row in inp]})
    return out


REGISTRY = {
    "identity": identity,
    "most_common_train_output": most_common_train_output,
    "output_shape_zeros": output_shape_zeros,
}


def build_submission(tasks: dict[str, Task], name: str) -> dict:
    """Run a named baseline over all tasks -> a submission dict."""
    if name not in REGISTRY:
        raise KeyError(f"unknown baseline '{name}'. options: {sorted(REGISTRY)}")
    fn = REGISTRY[name]
    return {tid: fn(t) for tid, t in tasks.items()}
