# Local pass@2 evaluation harness — ARC-AGI-2

Zero-dependency (stdlib-only) harness to score ARC-AGI-2 submissions **offline** against the
public splits that ship ground-truth solutions, so we can iterate without spending Kaggle
submits. Validated end-to-end (oracle → 100%, corruption → <100%, baselines → 0%, 8/8 unit tests).

## Files
| File | Role |
|---|---|
| `fetch_data.py` | clone public data (1000 train + 120 eval) from GitHub; `--kaggle` also pulls competition files |
| `arc_io.py` | load tasks (GitHub per-file *or* Kaggle challenges/solutions layout) + submissions |
| `metric.py` | official-style **pass@2** scorer (exact grid match; per-task mean = arcprize official) |
| `baselines.py` | trivial floor solvers (identity / most-common-output / output-shape-zeros) |
| `evaluate.py` | CLI: score a submission or a baseline against a split |
| `viewer.py` | render a task's grids in the terminal (ANSI color or digits) |
| `../tests/test_metric.py` | unit tests for the metric (run via pytest) |

## Quickstart
```sh
cd competitions/arc-agi2

# 1) fetch data (gitignored under data/ARC-AGI-2)
python eval/fetch_data.py            # add --kaggle for sample_submission + Kaggle-layout files

# 2) sanity-check the harness with a baseline on the public eval split (120 tasks)
python eval/evaluate.py --baseline identity --split evaluation        # expect ~0%

# 3) score a real submission.json
python eval/evaluate.py --submission path/to/submission.json --split evaluation

# 4) eyeball a task
python eval/viewer.py 0934a4d8 --split evaluation
```

## Metric notes (read before trusting a number)
- **pass@2**: a test output is solved if `attempt_1` OR `attempt_2` matches the solution
  exactly (shape + every cell). Per-task score = fraction of its test outputs solved.
- **Primary `score`** = mean of per-task scores (matches arcprize.org official scoring).
- **`flat_per_output`** = every test output weighted equally; identical to `score` when each
  task has 1 test input. On public eval, **45/120 tasks have >1 test output** (167 outputs
  total: 75×1 + 43×2 + 2×3), so the two diverge slightly there. ⚠ If a multi-test task ever
  drives a decision, confirm which convention the live Kaggle metric uses.
- Submission schema: `{task_id: [{"attempt_1": grid, "attempt_2": grid}, ... one per test input]}`
  (confirmed from the competition `sample_submission.json`).

## Running the tests
Standard pytest. If pytest isn't in the active interpreter (sandbox can't write site-packages):
```sh
python -m pip install --target "$TMPDIR/pe" pytest && PYTHONPATH="$TMPDIR/pe" python -m pytest tests/ -q
```
