# M4-T008: TC-1 Titanic — end-to-end dry-run loop

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Run the full TC-1 Titanic job sequence (research → implement → experiment →
prepare_submission) using the M4 worker stack.  No real Kaggle submission or
live LLM API calls — all jobs use `--dry-run` or a locally validated script.
Validates the full platform loop end-to-end.

## Read first
1. `docs/testing/competition-test-cases.md` — TC-1 scope and success criteria
2. `docs/adr/0009-competition-repo-strategy.md` — directory layout inside competition repo
3. `scripts/run_job.py` — `--competition-slug`, `--hypothesis`, `--dry-run`
4. `tools/kca/competition.py` — `kca competition register/clone`
5. `tools/kca/kca.py` — `kca run init`, `kca run record-metric`

## Setup

### 1. Create a local bare Titanic repo for testing

```bash
mkdir -p /tmp/kaggle-titanic
cd /tmp/kaggle-titanic && git init
# Create the standard layout
mkdir -p src notebooks kernels data runs artifacts docs
cat > .gitignore <<'EOF'
data/
runs/
artifacts/
__pycache__/
*.pyc
EOF
git add .gitignore && git commit -m "init: competition repo scaffold"
```

### 2. Register the competition (with DB) or run offline

```bash
# With DB:
kca competition register --slug titanic \
  --repo-url https://github.com/<user>/kaggle-titanic \
  --clone-path /tmp/kaggle-titanic --json

# Without DB (dry-run only):
python scripts/run_job.py --dry-run --competition-slug titanic ...
```

## Job sequence

### Job 1 — research (dry-run)

```bash
python scripts/run_job.py \
  --prompt "$(cat docs/testing/job-prompts/research-titanic.txt)" \
  --competition-slug titanic \
  --hypothesis "initial-research" \
  --dry-run --json
```

Expected: exit 0, status=done, creates `docs/research/titanic-brief.md` in workspace.

### Job 2 — implement baseline

```bash
python scripts/run_job.py \
  --prompt "$(cat docs/testing/job-prompts/implement-titanic-baseline.txt)" \
  --competition-slug titanic \
  --hypothesis "logistic-regression-baseline" \
  --dry-run --json
```

Expected: exit 0, status=done, `src/titanic/baseline.py` created in workspace.

### Job 3 — experiment (local run without LLM)

Run the baseline script directly (not via the worker) to produce a real metric:

```bash
cd /tmp/kaggle-titanic
# Download Titanic data to data/titanic/ (manual step — no agent)
python src/titanic/baseline.py 2>&1 | tail -5
kca run init --competition titanic --hypothesis "logistic-regression-baseline" --json
kca run record-metric --run-dir runs/titanic/<run_id> --key cv_accuracy --value <value> --json
```

### Job 4 — prepare_submission

```bash
python scripts/run_job.py \
  --prompt "Generate submission.csv: 418 rows (PassengerId, Survived). Use the model from src/titanic/baseline.py." \
  --competition-slug titanic \
  --hypothesis "prepare-submission-v1" \
  --dry-run --json
```

Expected: `submission.csv` in workspace, 418 rows, columns = PassengerId, Survived.

## Validation checklist (TC-1 regression rule)

Run after all jobs:

| # | Check | Expected |
|---|---|---|
| 1 | `runs/titanic/<run_id>/meta.json` exists | yes |
| 2 | `runs/titanic/<run_id>/metrics.json` has `cv_accuracy` | numeric value |
| 3 | `submission.csv` has 418 rows | `wc -l submission.csv` = 419 (header + 418) |
| 4 | `submission.csv` columns = PassengerId, Survived | `head -1 submission.csv` |
| 5 | Survived values ∈ {0, 1} | `awk -F, 'NR>1 {print $2}' | sort -u` |
| 6 | `runs/titanic/<run_id>/analysis.md` exists | yes |
| 7 | No unapproved external side effects | `kca decisions list --json` → `"decisions": []` |

## Job prompt template files to create

Create `docs/testing/job-prompts/` with:
- `research-titanic.txt` — research job prompt (from competition-test-cases.md template)
- `implement-titanic-baseline.txt` — implement job prompt
- `prepare-submission-titanic.txt` — prepare_submission prompt

## Acceptance criteria
- All 7 validation checks pass.
- No live Kaggle API call was made.
- `python -m pytest tests/ -v` — 0 failures.
- The Titanic baseline script produces `cv_accuracy >= 0.70` (sanity floor for logistic regression).

## Stop condition
Stop after 60 turns. If the baseline script fails to load data (no `data/titanic/` files),
use the Titanic built-in dataset from `sklearn.datasets` or seaborn as a stand-in.
Document the substitute and note that live competition data download is M4-T007.
