"""ARC-AGI-2 data + submission I/O.

Supports both on-disk layouts:

1. GitHub layout (github.com/arcprize/ARC-AGI-2):
   one JSON file per task under data/{training,evaluation}/<task_id>.json,
   each file = {"train": [...], "test": [{"input": .., "output": ..}, ...]}.

2. Kaggle layout (competition files):
   arc-agi_{split}_challenges.json  -> {task_id: {"train": [...], "test": [{"input": ..}, ...]}}
   arc-agi_{split}_solutions.json   -> {task_id: [output_grid_per_test_input, ...]}
   (challenges hold no test outputs; solutions hold them separately.)

A `Task` is normalised to: train pairs + test inputs + (optional) test outputs.

No third-party dependencies — grids are plain `list[list[int]]`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

Grid = list  # list[list[int]]

# Default data root: <comp>/data/ARC-AGI-2/data  (the cloned GitHub repo).
_HERE = Path(__file__).resolve().parent
DEFAULT_GITHUB_ROOT = _HERE.parent / "data" / "ARC-AGI-2" / "data"
DEFAULT_KAGGLE_ROOT = _HERE.parent / "data"


@dataclass
class Task:
    task_id: str
    train: list = field(default_factory=list)  # [{"input": Grid, "output": Grid}, ...]
    test_inputs: list = field(default_factory=list)  # [Grid, ...]
    test_outputs: list | None = None  # [Grid, ...] or None if hidden

    @property
    def n_test(self) -> int:
        return len(self.test_inputs)


def _load_json(path: str | os.PathLike) -> dict:
    with open(path) as f:
        return json.load(f)


def load_tasks_dir(root: str | os.PathLike) -> dict[str, Task]:
    """Load every ARC-format task JSON (`{"train":[...],"test":[...]}`) in a directory.

    Used for the GitHub split dirs and for any generated corpus (e.g. RE-ARC synthetic tasks
    written by solver/gen_rearc.py). Task ids are the filename stems.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"{root} not found.")
    tasks: dict[str, Task] = {}
    for fp in sorted(root.glob("*.json")):
        d = _load_json(fp)
        tid = fp.stem
        tasks[tid] = Task(
            task_id=tid,
            train=d["train"],
            test_inputs=[t["input"] for t in d["test"]],
            test_outputs=([t["output"] for t in d["test"]] if all("output" in t for t in d["test"]) else None),
        )
    return tasks


def load_github_split(split: str, root: str | os.PathLike | None = None) -> dict[str, Task]:
    """Load a split from the per-file GitHub layout. split in {"training","evaluation"}."""
    root = Path(root) if root else DEFAULT_GITHUB_ROOT
    split_dir = root / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"{split_dir} not found. Run eval/fetch_data.py to clone the public data.")
    return load_tasks_dir(split_dir)


def load_kaggle_split(split: str, root: str | os.PathLike | None = None) -> dict[str, Task]:
    """Load a split from the Kaggle challenges(+solutions) layout.

    split in {"training","evaluation","test"}. Solutions are loaded if the file exists
    (absent for the hidden `test` split during the live competition).
    """
    root = Path(root) if root else DEFAULT_KAGGLE_ROOT
    challenges = _load_json(root / f"arc-agi_{split}_challenges.json")
    sol_path = root / f"arc-agi_{split}_solutions.json"
    solutions = _load_json(sol_path) if sol_path.exists() else {}
    tasks: dict[str, Task] = {}
    for tid, d in challenges.items():
        tasks[tid] = Task(
            task_id=tid,
            train=d["train"],
            test_inputs=[t["input"] for t in d["test"]],
            test_outputs=solutions.get(tid),
        )
    return tasks


def load_solutions(tasks: dict[str, Task]) -> dict[str, list]:
    """Extract {task_id: [output_grid_per_test_input]} from tasks that carry outputs."""
    out: dict[str, list] = {}
    for tid, t in tasks.items():
        if t.test_outputs is not None:
            out[tid] = t.test_outputs
    return out


def load_submission(path: str | os.PathLike) -> dict[str, list]:
    """Load a submission.json: {task_id: [{"attempt_1": Grid, "attempt_2": Grid}, ...]}."""
    return _load_json(path)


def write_submission(submission: dict[str, list], path: str | os.PathLike) -> None:
    with open(path, "w") as f:
        json.dump(submission, f)
