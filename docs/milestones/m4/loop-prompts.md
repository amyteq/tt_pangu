# M4 / MVP-4 Loop Prompts

_Kaggle competition workflow v0._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M3 exit criteria confirmed met (see `docs/milestones/m3/final-review.md`)._

---

## M4 at a glance

M4 wires the M3 worker skeleton (DB + workspace + agent loop) to a real Kaggle
competition repo, implementing the full ADR-0009 competition repo strategy:

1. Each registered Kaggle competition gets its own GitHub repo (`kaggle-<slug>`).
2. Experiment branches (`exp/<hypothesis>`) track one hypothesis per branch.
3. Agent jobs get git worktrees *inside* the competition repo for per-job isolation.
4. `kca` is pip-installable from the platform repo and accessible in competition repos.
5. Approval gates are fully configurable per project/competition/job (ADR-0006).
6. TC-1 Titanic validates the full loop end-to-end (no live Kaggle API calls required).

---

## M4 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M4-T000 | `pyproject.toml` — pip-installable kca console entry point | Prompt 0 |
| M4-T001 | Migration 0004: competition repo cols + experiments/runs/submissions tables | Prompt 1 |
| M4-T002 | DB layer: competition/experiment/run/submission CRUD functions | Prompt 2 |
| M4-T003 | `kca competition register/clone/list` subcommands | Prompt 3 |
| M4-T004 | `kca workspace init --repo` flag + `kca run init/record-metric/list` | Prompt 4 |
| M4-T005 | `scripts/run_job.py` competition repo lifecycle | Prompt 5 |
| M4-T006 | Approval gate policy resolution (ADR-0006 full implementation) | Prompt 6 |
| M4-T007 | Wire real `kaggle` CLI into `kca kaggle` commands | Prompt 7 |
| M4-T008 | TC-1 Titanic end-to-end dry-run loop | Prompt 8 |
| M4-T009 | M4 smoke tests (no API/DB/credentials) | Prompt 9 |
| M4-T010 | M4 exit criteria validation | Prompt 10 |

---

## Loop Prompt 0 — Context + pyproject.toml (M4-T000)

```
Read the following files before doing anything else:
1. docs/milestones/README.md  (M4 section and task table)
2. docs/milestones/m3/final-review.md  (M3 follow-ups that are M4 scope)
3. docs/adr/0009-competition-repo-strategy.md  (how platform tools reach competition repo)
4. docs/tasks/m4/M4-T000-pyproject-kca-entry-point.md
5. pyproject.toml  (current state — already has [tool.pytest.ini_options])

Goal: make `kca` pip-installable from the platform repo via pyproject.toml.

Steps:
1. Add a [build-system] block (setuptools>=68).
2. Add a [project] block: name="tt-pangu", version="0.1.0", requires-python=">=3.11",
   dependencies = ["psycopg[binary]>=3.1", "python-dotenv>=1.0"].
3. Add [project.optional-dependencies]: llm=["litellm>=1.40"], dev=["pytest>=8", "ruff>=0.4"].
4. Add [project.scripts]: kca = "tools.kca.kca:main"
5. Add [tool.setuptools.packages.find]: where=["."], include=["tools*", "src*"]
6. Confirm tools/kca/kca.py exposes a top-level main() function (not only inside __name__==__main__).
7. Keep the existing [tool.pytest.ini_options] section unchanged.

Verification:
  pip install -e .
  kca --help
  kca nb to-py --help
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: pyproject.toml diff, kca --help output, test result.
```

---

## Loop Prompt 1 — Migration 0004 (M4-T001)

```
Read:
1. docs/tasks/m4/M4-T001-migration-0004-competition-repo.md
2. supabase/migrations/0001_init.sql  (competitions table, existing columns)
3. supabase/migrations/0003_m3_worker.sql  (migration style: idempotent, IF NOT EXISTS)
4. docs/adr/0005-job-taxonomy.md  (definitions of experiment, run, submission)
5. docs/adr/0009-competition-repo-strategy.md  (DB schema changes section)

Goal: write supabase/migrations/0004_m4_competition_repo.sql.

Part A — extend competitions table:
  ALTER TABLE competitions
    ADD COLUMN IF NOT EXISTS repo_url          text,
    ADD COLUMN IF NOT EXISTS default_branch    text NOT NULL DEFAULT 'main',
    ADD COLUMN IF NOT EXISTS local_clone_path  text,
    ADD COLUMN IF NOT EXISTS competition_policy jsonb NOT NULL DEFAULT '{}';

Part B — create experiments table:
  CREATE TABLE IF NOT EXISTS experiments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id  uuid NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
    hypothesis      text NOT NULL,
    branch          text,
    config          jsonb NOT NULL DEFAULT '{}',
    status          text NOT NULL DEFAULT 'active',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
  );
  + indexes on competition_id, job_id
  + ENABLE ROW LEVEL SECURITY

Part C — create experiment_runs table:
  CREATE TABLE IF NOT EXISTS experiment_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
    run_dir         text,
    command         text,
    status          text NOT NULL DEFAULT 'running',
    metrics         jsonb NOT NULL DEFAULT '{}',
    artifact_paths  jsonb NOT NULL DEFAULT '[]',
    analysis        text,
    started_at      timestamptz,
    finished_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
  );
  + indexes on experiment_id, job_id
  + ENABLE ROW LEVEL SECURITY

Part D — create submissions table:
  CREATE TABLE IF NOT EXISTS submissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id  uuid NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
    job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
    file_path       text NOT NULL,
    public_lb_score numeric(10,6),
    cv_score        numeric(10,6),
    note            text,
    status          text NOT NULL DEFAULT 'prepared',
    submitted_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
  );
  + index on competition_id
  + ENABLE ROW LEVEL SECURITY

Verification:
  # Apply migration (if SUPABASE_DB_URL is set):
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 < supabase/migrations/0004_m4_competition_repo.sql
  # Idempotency check — apply a second time, must produce no error:
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 < supabase/migrations/0004_m4_competition_repo.sql
  # Verify:
  psql "$SUPABASE_DB_URL" -c "\d competitions" | grep -E "repo_url|default_branch|local_clone_path"
  psql "$SUPABASE_DB_URL" -c "\dt" | grep -E "experiments|experiment_runs|submissions"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: migration file created, apply result, verification result.
```

---

## Loop Prompt 2 — DB layer additions (M4-T002)

```
Read:
1. docs/tasks/m4/M4-T002-db-layer-competition-experiment.md
2. tools/kca/db.py  (existing __all__, _with_conn, parameterised SQL patterns)
3. supabase/migrations/0004_m4_competition_repo.sql  (schema from Prompt 1)
4. docs/adr/0005-job-taxonomy.md  (object hierarchy, experiment/run/submission definitions)

Goal: extend tools/kca/db.py with M4 DB functions.

Add to __all__ and implement (follow existing db.py patterns exactly):

Competition functions:
  get_competition_by_slug(slug: str) -> dict
    -- SELECT * FROM competitions WHERE slug=$1
    -- Raises KeyError if not found

  update_competition(competition_id, *, repo_url=None, default_branch=None,
                     local_clone_path=None, competition_policy=None) -> None
    -- Partial UPDATE, only non-None kwargs

  list_competitions(limit: int = 50) -> list[dict]
    -- SELECT * FROM competitions ORDER BY created_at DESC LIMIT $1

Experiment functions:
  create_experiment(competition_id, hypothesis, *, job_id=None,
                    branch=None, config=None) -> str  (experiment_id)
  get_experiment(experiment_id) -> dict
  list_experiments(competition_id, status=None) -> list[dict]

Run functions:
  create_run(experiment_id, *, job_id=None, run_dir=None, command=None) -> str  (run_id)
  update_run(run_id, *, status=None, metrics=None, artifact_paths=None,
             analysis=None, finished_at=None) -> None
  record_metric(run_id: str, key: str, value: float) -> None
    -- Single parameterised UPDATE with jsonb merge:
    -- UPDATE experiment_runs SET metrics = metrics || jsonb_build_object($1::text, $2::float)
    --   WHERE id = $3::uuid
  list_runs(experiment_id=None, competition_id=None, limit=20) -> list[dict]

Submission functions:
  create_submission(competition_id, file_path, *, run_id=None, job_id=None,
                    cv_score=None, note=None) -> str  (submission_id)
  update_submission(submission_id, *, public_lb_score=None, status=None,
                    submitted_at=None) -> None

Design rules:
- No async. Parameterised SQL only (no f-string user data interpolation).
- Importable without a live DB (lazy connection via _with_conn).
- record_metric must use a single jsonb merge UPDATE — no Python read-modify-write.

Verification:
  python -c "
  from tools.kca import db
  new = [f for f in dir(db) if any(k in f for k in ['competition','experiment','run','submission'])]
  print(new)
  "
  # With live DB:
  python -c "
  import os; os.environ['SUPABASE_DB_URL'] = os.environ.get('SUPABASE_DB_URL','')
  from tools.kca import db
  # get a competition slug from DB or use a pre-existing one
  comps = db.list_competitions()
  if comps:
      c = comps[0]
      eid = db.create_experiment(c['id'], 'test hypothesis', branch='exp/test')
      rid = db.create_run(eid, command='python test.py')
      db.record_metric(rid, 'cv_accuracy', 0.82)
      run = db.update_run(rid, status='succeeded')
      print('OK')
  "
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: symbols added to __all__, live DB smoke result (if available).
```

---

## Loop Prompt 3 — `kca competition` subcommands (M4-T003)

```
Read:
1. docs/tasks/m4/M4-T003-kca-competition-commands.md
2. tools/kca/kca.py  (build_parser, how submodules are imported and registered)
3. tools/kca/decisions.py  (pattern for a new subcommand module)
4. tools/kca/db.py  (get_competition_by_slug, update_competition, list_competitions)
5. docs/adr/0009-competition-repo-strategy.md  (naming convention, directory layout)

Goal: implement tools/kca/competition.py with register, clone, list, info commands.

New file: tools/kca/competition.py

1. cmd_register — kca competition register --slug <slug> --repo-url <url>
                    [--branch main] [--clone-path <dir>] [--json]
   - Look up competition by slug via db.get_competition_by_slug(slug).
   - Call db.update_competition(id, repo_url=..., default_branch=..., local_clone_path=...).
   - If --clone-path not given, default to ~/competitions/kaggle-<slug>.
   - Side effect: LOCAL_WRITE. Exit 0 on success.
   - Emit: {"ok": true, "slug": "...", "repo_url": "...", "local_clone_path": "..."}

2. cmd_clone — kca competition clone --slug <slug> [--path <override>] [--json]
   - Fetch competition from DB, get repo_url and local_clone_path.
   - If local_clone_path exists: emit {"ok": true, "cloned": false, "path": "..."} and exit 0.
   - Otherwise: subprocess.run(["git", "clone", repo_url, local_clone_path], check=True).
   - Emit: {"ok": true, "cloned": true, "path": "..."}. Side effect: LOCAL_WRITE.
   - On error: emit {"ok": false, "error": "..."}, exit 1.

3. cmd_list — kca competition list [--json]
   - Call db.list_competitions() or return empty list if DB unavailable.
   - Exit 0 always. Side effect: READ_ONLY.
   - Emit: {"ok": true, "competitions": [{slug, platform, repo_url, ...}, ...]}

4. cmd_info — kca competition info --slug <slug> [--json]
   - Call db.get_competition_by_slug(slug). Side effect: READ_ONLY.
   - Emit full row including repo_url, local_clone_path, default_branch.

Register in kca.py build_parser():
  import competition as competition_mod
  competition_mod.add_parsers(sub)

Verification:
  python tools/kca/kca.py competition --help
  python tools/kca/kca.py competition list --json
  # → {"ok": true, "competitions": [...]}  (empty list OK without DB)
  # With DB and a registered competition:
  python tools/kca/kca.py competition register \
    --slug titanic --repo-url https://github.com/test/kaggle-titanic --json
  python tools/kca/kca.py competition info --slug titanic --json
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: commands verified, DB test result.
```

---

## Loop Prompt 4 — `kca workspace --repo` + `kca run` commands (M4-T004)

```
Read:
1. docs/tasks/m4/M4-T004-workspace-repo-flag-and-kca-run.md
2. tools/kca/workspace.py  (existing cmd_init, cmd_clean, cmd_list)
3. docs/adr/0009-competition-repo-strategy.md  (worktree path: <repo>/jobs/<job_id>)
4. docs/testing/competition-test-cases.md  (kca run init / record-metric usage)
5. tools/kca/db.py  (create_run, record_metric — from Prompt 2)

Goal: two changes.

--- Part A: kca workspace init --repo <path> flag ---

Add --repo argument to workspace init parser.
In cmd_init:
  if args.repo:
    repo_root = Path(args.repo).resolve()
    workspace_dir = repo_root / "jobs" / job_id
    git_cmd = ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(workspace_dir)]
    if args.branch:
      # Ensure branch exists in competition repo first:
      subprocess.run(["git", "-C", str(repo_root), "checkout", "-b", args.branch],
                     capture_output=True)  # ignore error if branch already exists
      git_cmd.append(args.branch)
  else:
    # fallback: existing platform-repo behaviour (.workspaces/<job_id>)

Emit: {"ok": true, "workspace_path": "<repo_root>/jobs/<job_id>", ...}

--- Part B: kca run subcommands (confirm or implement) ---

Check if kca run init, record-metric, list are already implemented from M2.
If not, implement them in tools/kca/run.py (or the existing run module).

kca run init --competition <slug> --hypothesis "<text>" [--experiment-id <uuid>] [--json]
  - Create runs/<slug>/<run_id>/ directory (relative to cwd).
  - Write meta.json: {"run_id":"...", "competition":"...", "hypothesis":"...", "started_at":"..."}
  - If DB available: db.create_run(experiment_id, run_dir=...).
  - Emit: {"ok": true, "run_dir": "runs/<slug>/<run_id>", "run_id": "..."}
  - Side effect: LOCAL_WRITE.

kca run record-metric --run-dir <path> --key <name> --value <float> [--json]
  - Read meta.json from run_dir to get run_id.
  - Merge {key: value} into runs/<run_dir>/metrics.json (read-modify-write in Python OK for file).
  - If DB available: db.record_metric(run_id, key, value).
  - Emit: {"ok": true, "key": "...", "value": ...}
  - Side effect: LOCAL_WRITE.

kca run list [--competition <slug>] [--json]
  - Glob runs/<slug>/*/meta.json; load each. Exit 0 even with no runs/.
  - Side effect: READ_ONLY.

Verification:
  # Test workspace --repo with a local bare git repo:
  mkdir /tmp/test-comp-repo && git -C /tmp/test-comp-repo init
  git -C /tmp/test-comp-repo commit --allow-empty -m "init"
  python tools/kca/kca.py workspace init \
    --job-id test-m4-repo-1 --repo /tmp/test-comp-repo --json
  # → {"ok": true, "workspace_path": "/tmp/test-comp-repo/jobs/test-m4-repo-1"}
  ls /tmp/test-comp-repo/jobs/test-m4-repo-1/
  python tools/kca/kca.py workspace clean --job-id test-m4-repo-1 --repo /tmp/test-comp-repo --json

  # Test kca run:
  mkdir -p /tmp/run-test && cd /tmp/run-test
  python <repo>/tools/kca/kca.py run init --competition titanic --hypothesis "baseline" --json
  # → saves run_dir
  python <repo>/tools/kca/kca.py run record-metric \
    --run-dir runs/titanic/<run_id> --key cv_accuracy --value 0.82 --json
  cat runs/titanic/<run_id>/metrics.json
  # → {"cv_accuracy": 0.82}
  python <repo>/tools/kca/kca.py run list --competition titanic --json

  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: workspace --repo test result, kca run test result.
```

---

## Loop Prompt 5 — `scripts/run_job.py` competition lifecycle (M4-T005)

```
Read:
1. docs/tasks/m4/M4-T005-run-job-competition-lifecycle.md
2. docs/adr/0009-competition-repo-strategy.md  (Worker lifecycle with Approach B section)
3. scripts/run_job.py  (current lifecycle, Steps 1–10)
4. tools/kca/db.py  (get_competition_by_slug, update_competition — from Prompt 2)
5. tools/kca/workspace.py  (cmd_init with --repo, cmd_clean — from Prompt 4)

Goal: update scripts/run_job.py to implement the ADR-0009 worker lifecycle.

New CLI flags to add:
  --competition-slug <slug>   # used to look up competition in DB
  --branch <branch>           # experiment branch (can be auto-derived)
  --hypothesis "<text>"       # short slug for auto-generating branch name as exp/<slugified>

New helpers to add to run_job.py:

def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")[:50]

def _resolve_competition_repo(slug: str, _db) -> tuple[str | None, str]:
    """Returns (local_clone_path, default_branch). Clones repo if needed.
    Returns (None, 'main') if DB unavailable or competition has no repo_url."""
    try:
        comp = _db.get_competition_by_slug(slug)
    except Exception:
        return None, "main"
    clone_path = comp.get("local_clone_path")
    repo_url = comp.get("repo_url")
    default_branch = comp.get("default_branch") or "main"
    if clone_path and not Path(clone_path).exists() and repo_url:
        import subprocess
        subprocess.run(["git", "clone", repo_url, clone_path], check=True)
    return clone_path, default_branch

def _resolve_branch(args, job_row: dict | None) -> str | None:
    if getattr(args, "branch", None):
        return args.branch
    payload = (job_row or {}).get("payload") or {}
    if payload.get("branch"):
        return payload["branch"]
    hypothesis = getattr(args, "hypothesis", None) or payload.get("hypothesis") or ""
    if hypothesis:
        return "exp/" + _slugify(hypothesis)
    return None

def _ensure_branch(repo_path: str, branch: str) -> None:
    """Create branch in competition repo if it doesn't exist."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", repo_path, "checkout", "-b", branch],
        capture_output=True
    )
    # Ignore 'already exists' error.

Updated Step 4 (workspace init) in main():
  if args.dry_run:
    workspace = Path(tempfile.mkdtemp())
    (workspace / "README.md").write_text("M3/M4 dry-run workspace")
  elif competition_repo_path:
    if branch:
        _ensure_branch(competition_repo_path, branch)
    ws_path = _workspace_init_repo(job_id, competition_repo_path, branch)
    if ws_path is None:
        return 1
    workspace = Path(ws_path)
    workspace_was_created = True
  else:
    ws_path = _workspace_init(job_id)   # existing M3 path
    ...

def _workspace_init_repo(job_id: str, repo: str, branch: str | None) -> str | None:
    """kca workspace init --job-id <id> --repo <repo> [--branch <branch>]"""
    cmd = [sys.executable, str(REPO_ROOT / "tools/kca/kca.py"),
           "workspace", "init", "--job-id", job_id, "--repo", repo, "--json"]
    if branch:
        cmd += ["--branch", branch]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            return data["workspace_path"]
    except Exception:
        pass
    print(json.dumps({"ok": False, "error": result.stderr or result.stdout}))
    return None

Updated Step 7b (commit on success):
  if competition_repo_path and result.status == "done" and not args.dry_run:
      import subprocess
      subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=False)
      subprocess.run(["git", "-C", str(workspace), "commit", "-m",
                      f"job/{job_id[:8]}: agent changes"], check=False)

Verification:
  # Dry-run still works (no competition slug):
  python scripts/run_job.py --prompt "test" --dry-run --json
  # → exit 0, status=done

  # Dry-run with competition slug (skips DB/git ops):
  python scripts/run_job.py --prompt "test" --competition-slug titanic \
    --hypothesis "logistic-regression" --dry-run --json
  # → exit 0, status=done

  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: both dry-run tests, test suite result.
```

---

## Loop Prompt 6 — Approval gate policy resolution (M4-T006)

```
Read:
1. docs/tasks/m4/M4-T006-approval-gate-policy-resolution.md
2. docs/adr/0006-configurable-approval-gates.md  (policy schema, resolution order, defaults)
3. tools/kca/kg.py  (current _gate() function)
4. src/worker/tools.py  (ToolExecutor, ApprovalRequired)
5. src/worker/_types.py  (JobPolicy — current approval_gates field)

Goal: replace the KCA_ALLOW_REMOTE env-var hard gate with a configurable policy dict.

--- Part A: src/worker/_types.py ---

Confirm or add approval_gates to JobPolicy with ADR-0006 defaults:
  approval_gates: dict = field(default_factory=lambda: {
      "kaggle_submit":    False,   # default: allow
      "kernel_push":      False,   # default: allow
      "dataset_upload":   True,    # default: require approval
      "git_push":         False,   # default: allow
      "git_force_push":   True,    # default: require approval
      "supabase_migrate": True,    # default: require approval
      "delete_artifact":  True,    # default: require approval
  })

--- Part B: tools/kca/kg.py ---

Replace _gate() with _check_approval_gate(operation, policy):

OPERATION_DEFAULTS = {
    "kaggle_submit":    False,
    "kernel_push":      False,
    "dataset_upload":   True,
    "git_push":         False,
    "git_force_push":   True,
    "supabase_migrate": True,
    "delete_artifact":  True,
}

def _check_approval_gate(operation: str, policy: dict) -> None:
    gates = policy.get("approval_gates", {})
    requires = gates.get(operation, OPERATION_DEFAULTS.get(operation, True))
    # KCA_ALLOW_REMOTE=1 remains as emergency CI override.
    if requires and not os.environ.get("KCA_ALLOW_REMOTE"):
        raise ApprovalRequired(operation, policy)

Define ApprovalRequired locally in kg.py (or import from src.worker._types if available):
class ApprovalRequired(Exception):
    def __init__(self, operation, policy):
        self.operation = operation
        self.policy = policy
        super().__init__(f"ApprovalRequired: {operation}")

Update all kca kaggle command functions to call _check_approval_gate before executing.

--- Part C: scripts/run_job.py ---

Add _resolve_policy() that merges project/competition/job gates:

def _resolve_policy(args, project_row=None, competition_row=None) -> JobPolicy:
    base = JobPolicy()
    if project_row:
        for k, v in (project_row.get("approval_gates") or {}).items():
            base.approval_gates[k] = v
    if competition_row:
        for k, v in (competition_row.get("competition_policy") or {}).get("approval_gates", {}).items():
            if v:   # competition can only tighten (set True), not loosen
                base.approval_gates[k] = True
    if getattr(args, "require_approval", None):
        for op in args.require_approval:
            base.approval_gates[op] = True
    base.max_turns = args.max_turns
    base.max_cost_usd = args.max_cost_usd
    base.model = args.model
    return base

Add --require-approval nargs='+' flag to argparser.

Verification:
  python -c "
  from src.worker._types import JobPolicy
  p = JobPolicy()
  assert p.approval_gates['kaggle_submit'] == False, 'should be allow by default'
  assert p.approval_gates['dataset_upload'] == True, 'should require approval'
  print('PASS: default gates correct')
  "

  python -c "
  from tools.kca.kg import _check_approval_gate
  # Default policy: kaggle_submit=False → should NOT raise
  try:
      _check_approval_gate('kaggle_submit', {'approval_gates': {'kaggle_submit': False}})
      print('PASS: kaggle_submit allowed by default')
  except Exception as e:
      print('FAIL:', e)
  # Tightened policy: kaggle_submit=True → should raise
  try:
      _check_approval_gate('kaggle_submit', {'approval_gates': {'kaggle_submit': True}})
      print('FAIL: should have raised')
  except Exception as e:
      print('PASS: kaggle_submit blocked by policy:', type(e).__name__)
  "

  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: gate check results, test suite result.
```

---

## Loop Prompt 7 — Wire real kaggle CLI (M4-T007)

```
Read:
1. docs/tasks/m4/M4-T007-real-kaggle-cli-wiring.md
2. tools/kca/kg.py  (existing stubs, _check_approval_gate from Prompt 6)
3. docs/tooling/env-configuration.md  (KAGGLE_USERNAME, KAGGLE_KEY variables)
4. docs/testing/competition-test-cases.md  (TC-3 kernel push --dry-run requirement)

Goal: wire real kaggle CLI subprocess calls into kca kaggle commands.
Do NOT make real Kaggle API calls. All verifications use --dry-run or mock subprocess.

--- cmd_submit (kca kaggle submit) ---
  1. Check KAGGLE_USERNAME and KAGGLE_KEY are set → emit error and exit 1 if missing.
  2. Call _check_approval_gate("kaggle_submit", policy) → raises ApprovalRequired if gated.
  3. subprocess.run(["kaggle", "competitions", "submit", "-c", slug,
                     "-f", file_path, "-m", message or "kca agent submission"],
                    capture_output=True, text=True)
  4. Emit: {"ok": True if rc==0 else False, "competition": slug, "file": file_path,
            "side_effect": "SUBMISSION", "stdout": ..., "stderr": ...}

--- cmd_push (kca kaggle push) ---
  1. Call _check_approval_gate("kernel_push", policy).
  2. If --dry-run:
       Validate kernel-metadata.json exists in kernel_dir.
       Emit {"ok": true, "dry_run": true, "kernel_dir": kernel_dir}
       Exit 0.
  3. Otherwise: subprocess.run(["kaggle", "kernels", "push", "-p", kernel_dir], ...)
  4. Emit: {"ok": ..., "kernel_dir": ..., "side_effect": "REMOTE_WRITE"}

--- cmd_download (kca kaggle download) ---
  1. No approval gate (READ_ONLY for rules; LOCAL_WRITE for files — not gated by default).
  2. subprocess.run(["kaggle", "competitions", "download", "-c", slug, "-p", path], ...)
  3. Emit: {"ok": ..., "competition": slug, "path": path, "side_effect": "LOCAL_WRITE"}

--- cmd_watch (kca kaggle watch) ---
  1. No approval gate (READ_ONLY polling).
  2. Loop: subprocess.run(["kaggle", "kernels", "status", kernel_ref], ...)
     Parse output for "complete" or "error".
     Sleep poll_seconds between iterations.
  3. Emit: {"ok": true/false, "status": "complete|error", "kernel": kernel_ref}

Create tests/fixtures/sample_kernel/ with a minimal kernel-metadata.json:
  {"id": "testuser/sample-kernel", "title": "Sample Kernel", "code_file": "test.py",
   "language": "python", "kernel_type": "script", "is_private": true}

Verification:
  # dry-run push (no credentials needed):
  python tools/kca/kca.py kaggle push \
    --kernel-dir tests/fixtures/sample_kernel --dry-run --json
  # → {"ok": true, "dry_run": true, "kernel_dir": "..."}

  # submit without credentials:
  KAGGLE_USERNAME= KAGGLE_KEY= python tools/kca/kca.py kaggle submit \
    --competition titanic --file /dev/null --json
  # → {"ok": false, "error": "KAGGLE_USERNAME not set ..."}

  # policy gate:
  python -c "
  import os; os.environ.pop('KCA_ALLOW_REMOTE', None)
  from tools.kca.kg import _check_approval_gate
  try:
      _check_approval_gate('kernel_push', {'approval_gates': {'kernel_push': True}})
      print('FAIL')
  except Exception as e:
      print('PASS: blocked:', e)
  "

  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: all three verification results, test suite result.
```

---

## Loop Prompt 8 — TC-1 Titanic end-to-end dry-run (M4-T008)

```
Read:
1. docs/tasks/m4/M4-T008-tc1-titanic-end-to-end.md
2. docs/testing/competition-test-cases.md  (TC-1 scope, validation checklist)
3. docs/adr/0009-competition-repo-strategy.md  (directory layout inside competition repo)
4. scripts/run_job.py  (--competition-slug, --hypothesis, --dry-run)

Goal: run the TC-1 Titanic loop and validate all 7 checks pass.
No real Kaggle API calls. No real LLM API calls (--dry-run for all worker jobs).

--- Setup: create a local Titanic competition repo ---

mkdir -p /tmp/kaggle-titanic/{src/titanic,notebooks,kernels,docs/research,runs,artifacts,data}
cd /tmp/kaggle-titanic
git init
cat > .gitignore <<'IGNORE'
data/
runs/
artifacts/
__pycache__/
*.pyc
IGNORE
echo "# Titanic" > README.md
git add . && git commit -m "init: titanic competition repo"

--- Job 2 (implement): create baseline.py manually for dry-run ---

Create /tmp/kaggle-titanic/src/titanic/baseline.py using sklearn and seaborn's built-in
Titanic dataset (no data/ files needed). The script should:
  1. Load titanic data from seaborn: df = seaborn.load_dataset("titanic")
  2. Prepare features: Pclass, Sex (encoded), Age (filled), SibSp, Parch.
  3. Train LogisticRegression with 5-fold CV.
  4. Print metric JSON to stdout: {"metric": "cv_accuracy", "value": <float>, "fold_scores": [...]}
  5. Generate submission.csv (simulate 418 rows with PassengerId 892-1309, Survived 0 or 1).

--- Job 3 (experiment): run the script directly ---

cd /tmp/kaggle-titanic
pip install scikit-learn seaborn -q
python src/titanic/baseline.py
# → prints metric JSON

# Init a run:
kca run init --competition titanic --hypothesis "logistic-regression-baseline" --json
# → saves run_dir

# Record metric (use value from script output):
kca run record-metric --run-dir <run_dir> --key cv_accuracy --value <value> --json

# Write analysis:
echo "Logistic regression 5-fold CV accuracy approximately 0.79. Next: try random forest." \
  > <run_dir>/analysis.md

--- Validation checklist ---

Run all 7 checks and report PASS/FAIL:

1. runs/titanic/<run_id>/meta.json exists:
   ls <run_dir>/meta.json → PASS/FAIL

2. runs/titanic/<run_id>/metrics.json has cv_accuracy:
   cat <run_dir>/metrics.json | python -c "import sys,json; d=json.load(sys.stdin); assert 'cv_accuracy' in d; print('PASS')"

3. submission.csv has 419 lines (header + 418 rows):
   wc -l /tmp/kaggle-titanic/submission.csv → PASS if 419

4. submission.csv columns = PassengerId, Survived:
   head -1 /tmp/kaggle-titanic/submission.csv → PASS if "PassengerId,Survived"

5. Survived values ∈ {0, 1}:
   awk -F, 'NR>1 {print $2}' /tmp/kaggle-titanic/submission.csv | sort -u
   → PASS if only "0" and "1" appear

6. analysis.md exists and is non-empty:
   cat <run_dir>/analysis.md | wc -c → PASS if > 0

7. No pending unapproved decisions:
   python tools/kca/kca.py decisions list --json | python -c "
   import sys, json; d=json.load(sys.stdin)
   pending = [x for x in d.get('decisions',[]) if x.get('status')=='pending']
   print('PASS' if not pending else f'FAIL: {len(pending)} pending')
   "

8. CV accuracy >= 0.70 (sanity floor):
   python -c "
   import json; m=json.load(open('<run_dir>/metrics.json'))
   v = m.get('cv_accuracy',0)
   print('PASS' if v>=0.70 else f'FAIL: cv_accuracy={v}')
   "

Report all check results. Output "TC-1 TITANIC PASS" if all pass.

Create docs/testing/job-prompts/ directory with three template files:
  research-titanic.txt   — research job prompt (from competition-test-cases.md template)
  implement-titanic-baseline.txt   — implement job prompt
  prepare-submission-titanic.txt   — prepare_submission prompt

python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: all 8 check results, test suite result.
```

---

## Loop Prompt 9 — M4 smoke tests (M4-T009)

```
Read:
1. docs/tasks/m4/M4-T009-m4-smoke-tests.md
2. tests/test_worker_smoke.py  (M3 style: no API, no DB, tempdir)
3. tools/kca/competition.py  (M4-T003)
4. tools/kca/workspace.py  (--repo flag, M4-T004)
5. tools/kca/kg.py  (dry-run and gate checks, M4-T007)

Goal: create tests/test_m4_smoke.py with 8–12 pytest test cases.
All tests pass without ANTHROPIC_API_KEY, SUPABASE_DB_URL, or KAGGLE_KEY.

Required test cases:

1. test_competition_list_no_db()
   Run: kca competition list --json (with SUPABASE_DB_URL unset)
   Assert: exit 0, JSON with "competitions" key.

2. test_workspace_init_with_repo(tmp_path)
   Setup: git init + empty commit in tmp_path/repo
   Run: kca workspace init --job-id test-m4-ws-1 --repo <tmp_path/repo> --json
   Assert: ok=True, workspace_path exists as a directory.
   Cleanup: kca workspace clean --job-id test-m4-ws-1 --repo <tmp_path/repo>

3. test_run_init_creates_meta(tmp_path, monkeypatch)
   monkeypatch.chdir(tmp_path)
   Run: kca run init --competition titanic --hypothesis "smoke test" --json
   Assert: ok=True, runs/titanic/<run_id>/meta.json exists with correct content.

4. test_run_record_metric(tmp_path, monkeypatch)
   monkeypatch.chdir(tmp_path)
   Init a run, then record a metric.
   Assert: metrics.json contains {"cv_accuracy": 0.83}.

5. test_run_list_no_runs(tmp_path, monkeypatch)
   monkeypatch.chdir(tmp_path)
   Run: kca run list --competition titanic --json
   Assert: exit 0, competitions or runs key present (empty OK).

6. test_kaggle_push_dry_run(tmp_path)
   Create tmp_path/kernel-metadata.json with minimal content.
   Run: kca kaggle push --kernel-dir <tmp_path> --dry-run --json
   Assert: ok=True, dry_run=True.

7. test_kaggle_submit_no_credentials()
   Run: kca kaggle submit --competition titanic --file /dev/null --json
   with KAGGLE_USERNAME and KAGGLE_KEY unset in env.
   Assert: ok=False, "error" key present.

8. test_approval_gate_blocks_by_policy()
   from tools.kca.kg import _check_approval_gate
   with pytest.raises(Exception):
       _check_approval_gate("kaggle_submit", {"approval_gates": {"kaggle_submit": True}})

9. test_approval_gate_allows_by_default()
   _check_approval_gate("kaggle_submit", {"approval_gates": {"kaggle_submit": False}})
   # Should NOT raise.

10. test_run_job_competition_slug_dry_run()
    Run: python scripts/run_job.py --prompt "test" --competition-slug titanic
         --max-turns 2 --dry-run --json
    with SUPABASE_DB_URL unset.
    Assert: exit 0, status=done.

Run the suite:
  python -m pytest tests/test_m4_smoke.py -v

All 10 must pass. Fix failures before finishing.

Then run the full suite:
  python -m pytest tests/ -v
  → 0 failures (M3 suite also passes)

Do NOT git add or commit. Report: test count, pass/fail per test.
```

---

## Loop Prompt 10 — M4 exit criteria validation

```
Goal: verify ALL M4 exit criteria. Gate before M4 is declared complete.

Run each check and report PASS/FAIL/SKIP:

--- Schema + DB ---
1. Migration 0004 idempotent:
   psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 < supabase/migrations/0004_m4_competition_repo.sql
   (twice; second must produce no error)
   → PASS/FAIL/SKIP (SKIP if no SUPABASE_DB_URL)

2. competitions table has repo_url, default_branch, local_clone_path:
   psql "$SUPABASE_DB_URL" -c "\d competitions" | grep -E "repo_url|default_branch|local_clone_path"
   → PASS (3 lines) / FAIL / SKIP

3. experiments, experiment_runs, submissions tables exist:
   psql "$SUPABASE_DB_URL" -c "\dt" | grep -E "experiments|experiment_runs|submissions"
   → PASS (3 tables) / FAIL / SKIP

--- pip install ---
4. kca available on PATH after pip install -e .:
   pip install -e . && kca --help | grep -E "competition|workspace|run|nb|kaggle"
   → PASS / FAIL

--- Competition commands ---
5. kca competition list exits 0 without DB:
   SUPABASE_DB_URL= python tools/kca/kca.py competition list --json
   → PASS (exit 0, ok key present) / FAIL

--- Workspace --repo ---
6. kca workspace init --repo creates worktree in competition repo:
   (use a temp bare git repo as in Prompt 4)
   → PASS / FAIL

--- kca run ---
7. kca run init creates meta.json:
   kca run init --competition titanic --hypothesis "exit-check" --json
   → PASS (file exists) / FAIL

8. kca run record-metric writes to metrics.json:
   kca run record-metric --run-dir <run_dir> --key cv_accuracy --value 0.80 --json
   cat <run_dir>/metrics.json | python -c "import sys,json; d=json.load(sys.stdin); assert d.get('cv_accuracy')==0.80; print('PASS')"
   → PASS / FAIL

--- Approval gate ---
9. Default policy allows kaggle_submit:
   python -c "
   from src.worker._types import JobPolicy
   p = JobPolicy()
   assert p.approval_gates.get('kaggle_submit') == False
   print('PASS')
   "
   → PASS / FAIL

10. Policy gate blocks when set to True:
    python -c "
    from tools.kca.kg import _check_approval_gate
    try:
        _check_approval_gate('kaggle_submit', {'approval_gates': {'kaggle_submit': True}})
        print('FAIL')
    except Exception as e:
        print('PASS:', type(e).__name__)
    "
    → PASS / FAIL

--- Kaggle CLI ---
11. kca kaggle push --dry-run works without credentials:
    kca kaggle push --kernel-dir tests/fixtures/sample_kernel --dry-run --json
    → PASS (ok=true, dry_run=true) / FAIL

--- TC-1 Titanic ---
12. TC-1 all 7 validation checks pass:
    (re-run or reference results from Prompt 8)
    → PASS / FAIL

--- Test suite ---
13. Full test suite:
    python -m pytest tests/ -v
    → report X passed, Y skipped, Z failed
    → PASS if 0 failed

--- M4 exit criteria (from milestones.md) ---
14. Each competition runs in its own repo with experiment branches:
    Demonstrate worktree at <competition_repo>/jobs/<job_id> (from check 6)
    → PASS / FAIL

15. TC-1 submission.csv validated locally, no unapproved Kaggle call:
    submission.csv exists (418 rows), decisions list shows no pending items
    → PASS / FAIL

--- Output ---

Print validation matrix:
| # | Check | Result | Notes |
|---|---|---|---|
...

If all non-SKIP checks are PASS: output "M4 EXIT CRITERIA MET".
Create docs/milestones/m4/final-review.md following the template in docs/milestones/m3/final-review.md.

Include M5 follow-ups section:
1. Browser/research loop: Playwright MCP for reading competition pages.
2. Kaggle data auto-download: kca kaggle download wired + checksum validation.
3. CI GitHub Actions: DB smoke + worker smoke + M4 smoke on every PR.
4. Resume paused jobs: re-run after kca decisions approve.
5. Model routing: Sonnet for implement/experiment, Opus for eval/analysis.
6. TC-2 House Prices: feature engineering iteration loop.

Do NOT git add or commit. Report: full validation matrix, final status.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
pip install litellm psycopg[binary] nbformat pyyaml pytest seaborn scikit-learn
pip install -e .   # after Prompt 0 completes — makes kca available on PATH

# Verify M4 base
python -c "from src.worker._types import JobPolicy; p=JobPolicy(); print(p.approval_gates)"
kca --help
```

### Settings additions for autonomous M4 loop

Add to `.claude/settings.json` allow-list (extend the M3 list):

```json
"Bash(pip install -e .)",
"Bash(kca competition*)",
"Bash(kca run*)",
"Bash(kca kaggle push --dry-run*)",
"Bash(kca kaggle download*)",
"Bash(python scripts/run_job.py --competition-slug*)",
"Bash(mkdir -p /tmp/kaggle-titanic*)",
"Bash(git -C /tmp/kaggle-titanic*)",
"Bash(python /tmp/kaggle-titanic/src/titanic/baseline.py)"
```

### Full autonomous run

```bash
claude "
Execute M4 Loop Prompts 0 through 10 from docs/milestones/m4/loop-prompts.md in sequence.
Each prompt's acceptance checks must pass before moving to the next.
On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push.
Do not call the real Anthropic API or Kaggle API.
Use --dry-run for all worker tests.
Report PASS/FAIL for each prompt's verification step inline.
"
```
