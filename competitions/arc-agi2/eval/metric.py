"""Official-style pass@2 scoring for ARC-AGI-2.

Submission shape (Kaggle):
    {task_id: [ {"attempt_1": Grid, "attempt_2": Grid}, ... one dict per test input ... ]}
Solutions shape:
    {task_id: [ output_grid_per_test_input, ... ]}

Scoring rules (ARC-AGI convention):
  * A test output is SOLVED if either attempt_1 OR attempt_2 equals the ground-truth grid
    EXACTLY (same shape and every cell value).
  * Per-task score = (# solved test outputs) / (# test outputs in the task).
  * Final score = mean of per-task scores over all scored tasks  -> matches arcprize.org
    official scoring and equals the flat per-output mean when every task has 1 test input
    (true for 75/120 public-eval tasks; 45 have >1).

We also report `flat_per_output` (every test output weighted equally, ignoring task
grouping) because some Kaggle metric variants average that way. For single-test tasks the
two are identical. ⚠ Confirm which convention the live competition uses if multi-test tasks
ever drive a decision; until then `score` (per-task mean) is the primary number.

No third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

Grid = list  # list[list[int]]


def grids_equal(a, b) -> bool:
    """Exact match: same number of rows, same row lengths, identical integer cells."""
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        if list(ra) != list(rb):
            return False
    return True


def output_solved(attempts: dict, solution: Grid) -> bool:
    """True if any of attempt_1 / attempt_2 (or attempt_N) matches the solution exactly."""
    for key, pred in attempts.items():
        if not key.startswith("attempt_"):
            continue
        if grids_equal(pred, solution):
            return True
    return False


@dataclass
class ScoreReport:
    score: float  # primary: mean of per-task scores (arcprize official)
    flat_per_output: float  # every test output weighted equally
    n_tasks: int  # tasks scored (present in both submission and solutions)
    n_outputs: int  # total test outputs scored
    n_outputs_solved: int
    missing_tasks: list  # in solutions but absent/empty in submission
    per_task: dict  # {task_id: per-task score}

    def __str__(self) -> str:
        return (
            f"pass@2 score = {self.score:.4f}  ({self.score * 100:.2f}%)  "
            f"[flat_per_output = {self.flat_per_output:.4f}]\n"
            f"tasks scored = {self.n_tasks}, outputs solved = "
            f"{self.n_outputs_solved}/{self.n_outputs}, missing tasks = {len(self.missing_tasks)}"
        )


def score_submission(submission: dict, solutions: dict, *, strict: bool = False) -> ScoreReport:
    """Score a submission against solutions.

    A task present in `solutions` but missing from `submission` (or with too few attempt
    dicts) scores 0 for its missing outputs and is recorded in `missing_tasks`.
    If `strict`, raise on any submission task absent from solutions (typo guard).
    """
    if strict:
        extra = set(submission) - set(solutions)
        if extra:
            raise ValueError(f"submission has {len(extra)} task(s) not in solutions: {sorted(extra)[:5]}")

    per_task: dict[str, float] = {}
    missing: list[str] = []
    n_outputs = 0
    n_solved = 0

    for tid, sols in solutions.items():
        attempts_list = submission.get(tid)
        n_t = len(sols)
        n_outputs += n_t
        if not attempts_list:
            missing.append(tid)
            per_task[tid] = 0.0
            continue
        solved_here = 0
        for i, sol in enumerate(sols):
            attempts = attempts_list[i] if i < len(attempts_list) else {}
            if isinstance(attempts, dict) and output_solved(attempts, sol):
                solved_here += 1
        n_solved += solved_here
        per_task[tid] = solved_here / n_t if n_t else 0.0

    n_tasks = len(solutions)
    score = sum(per_task.values()) / n_tasks if n_tasks else 0.0
    flat = n_solved / n_outputs if n_outputs else 0.0
    return ScoreReport(
        score=score,
        flat_per_output=flat,
        n_tasks=n_tasks,
        n_outputs=n_outputs,
        n_outputs_solved=n_solved,
        missing_tasks=missing,
        per_task=per_task,
    )
