# ADR-0009: Separate GitHub repo per competition

Status: accepted  
Date: 2026-05-19  
Decided in: `docs/meeting-notes/2026-05-19-r2.md`

---

## Context

During M3 design, two workspace strategies were considered:

**Option A — Platform repo worktrees:** competition code lives inside the platform repo (`src/<competition>/`); each job gets a `git worktree` inside that repo.

**Option B — Separate repo per competition:** each registered Kaggle competition gets its own GitHub repo; branches track experiments; jobs get worktrees *within* the competition repo.

The platform repo and the competition repo solve different problems and should not be conflated.

## Decision

**Each registered Kaggle competition gets its own dedicated GitHub repository.**

Branches within that repo track experiments. Agent jobs get git worktrees within the competition repo for per-job isolation.

```
Platform repo (tt_pangu)          ← platform code, kca tools, skills, config
Competition repo (kaggle-<slug>)  ← all competition code, notebooks, results
  branch: main                    ← clean, human-reviewed baseline
  branch: exp/<hypothesis-slug>   ← one branch per experiment hypothesis
  git worktree: jobs/<job_id>     ← per-job isolation during execution
```

### Repository naming convention

```
<github-user>/kaggle-<slug>[-YYYY]
```

Examples:
- `harry/kaggle-titanic`
- `harry/kaggle-flower-tpu-2026`
- `harry/kaggle-house-prices`

The year suffix is optional; add it when the user enters the same competition across years.

### Branch naming convention

```
main                    ← baseline that has been manually reviewed
exp/<short-slug>        ← experiment branch (agent-created)
fix/<short-slug>        ← bug fix branch
submit/<n>              ← submission candidate (cherry-picked from exp)
```

Examples:
- `exp/efficientnetb0-baseline`
- `exp/b3-mixup-labelsmooth`
- `submit/2`

### Directory layout inside a competition repo

```
<competition-repo>/
  src/                  ← Python source files (percent-format, editable truth)
  notebooks/            ← derived .ipynb files (kca nb to-ipynb output)
  kernels/              ← Kaggle kernel metadata directories
  data/                 ← gitignored; competition data mount
  runs/                 ← gitignored; kca run artifact directories
  artifacts/            ← gitignored; model weights, submission files, logs
  docs/                 ← research brief, analysis notes
  requirements.txt      ← competition-specific deps (tf, xgboost, etc.)
  .gitignore            ← data/, runs/, artifacts/, __pycache__/
  README.md             ← competition summary, best scores, next steps
```

### How platform tools reach the competition repo

The platform kca CLI must be accessible from within the competition repo workspace. Three options (choose based on what's available at job runtime):

1. **PYTHONPATH** (simplest for local dev):
   ```
   PYTHONPATH=/path/to/tt_pangu python tools/kca/kca.py nb to-ipynb ...
   ```
2. **pip editable install** (recommended for CI/worker):
   ```
   pip install -e /path/to/tt_pangu  # requires pyproject.toml in platform repo
   ```
3. **PATH** (if kca has a console script entry point):
   ```
   kca nb to-ipynb ...
   ```

M3 uses option 1 (PYTHONPATH). M4 adds pyproject.toml and switches to option 2.

### DB schema changes

`competitions` table additions (migration 0004):

```sql
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS repo_url          text,
  ADD COLUMN IF NOT EXISTS default_branch    text NOT NULL DEFAULT 'main',
  ADD COLUMN IF NOT EXISTS local_clone_path  text;
```

`agent_jobs` table: `workspace_path` already stores the worktree path inside the competition repo clone.

### Worker lifecycle with Approach B

```
scripts/run_job.py receives job_id
  ↓
load job from DB → get competition_id
  ↓
load competition from DB → get repo_url, local_clone_path, default_branch
  ↓
if local_clone_path does not exist:
  git clone <repo_url> <local_clone_path>
  ↓
resolve experiment branch for this job:
  branch = job.payload.get('branch') or 'exp/' + slugify(job.payload['hypothesis'])
  git -C <local_clone_path> checkout -b <branch> (if not exists)
  ↓
kca workspace init --job-id <id> --repo <local_clone_path> --branch <branch>
  → creates git worktree at <local_clone_path>/jobs/<job_id>
  ↓
AgentWorker runs in workspace (all file ops relative to worktree)
  ↓
on success: git -C worktree add/commit (if changes)
on failure/paused: keep worktree for debugging
  ↓
kca workspace clean --job-id <id>
```

## Transition plan

### M3 (current milestone) — interim: platform repo worktree

M3 completes the worker skeleton using the platform repo. No competition repo management yet. `kca workspace init` creates `.workspaces/<job_id>/` inside the platform repo as a temporary worktree.

This is intentional: the worktree mechanism itself is identical in both approaches; only the root repo changes.

**M3 scope is unchanged.**

### M4 (Kaggle competition workflow v0) — full Approach B

M4 adds:
- `kca competition register --slug <slug> --repo-url <url>` command
- `kca competition clone --slug <slug>` — git clone to local_clone_path
- `kca workspace init` gains `--repo <path>` flag (creates worktree inside competition repo)
- `scripts/run_job.py` resolves competition repo from DB before workspace init
- Migration 0004 adds `repo_url`, `default_branch`, `local_clone_path` to competitions
- `pyproject.toml` in platform repo so kca is pip-installable

## Consequences

- **Positive:** Clean separation — platform code and competition code never mix.
- **Positive:** Branch-per-experiment makes git log a readable experiment history.
- **Positive:** Competition repos can be archived, made public, or shared independently.
- **Positive:** Kaggle kernel metadata naturally points to the competition repo.
- **Positive:** Data, runs/, artifacts/ are isolated per competition with no cross-contamination.
- **Negative:** One more repo to create per competition (mitigated: can be automated in M4).
- **Negative:** kca must be accessible from competition repo (mitigated: PYTHONPATH in M3, pip install in M4).
- **Negative:** Worker must clone the competition repo if not already local (network op; mitigated by caching local_clone_path).

## Does not affect

- How Supabase records run metrics (unchanged).
- How `kca nb to-ipynb` and `kca nb to-py` work (tool interface unchanged).
- The approval gate policy (ADR-0006, unchanged).
- The LiteLLM provider strategy (ADR-0004, unchanged).
