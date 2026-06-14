# M3 / MVP-3 Loop Prompts

_Python-first competition worker v0._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M1 and M2 exit criteria are confirmed met (see `docs/milestones/m2/final-review.md`)._

---

## M3 at a glance

M3 wires the control plane (Supabase/DB from M2) to a live Python agent worker that can:
1. Accept a job from the DB queue (or CLI).
2. Create an isolated git worktree workspace.
3. Run a controlled Claude Agent loop inside that workspace.
4. Call `kca` tools, run tests, record artifacts.
5. Pause on remote/submission actions and wait for human approval.
6. Record every turn, tool call, cost, and result to the DB.

**Worker runtime:** `litellm.completion()` in a manual agentic tool loop (ADR-0004). Provider-agnostic: Claude, GPT-4o, or local Ollama all work through the same interface. Tool schemas are in OpenAI format. Model, temperature, top_p, and min_p come from `JobPolicy`.

**Approval gates:** configurable per project/competition (ADR-0006). Default is **allow** for kaggle_submit, kernel_push, git_push. No `KCA_ALLOW_REMOTE` gate required by default in M3+.

---

## M3 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M3-T000 | Hotfix: rename `tools/kca/kaggle.py` → `tools/kca/kg.py` | Prompt 0 |
| M3-T001 | Migration 0003: agent job events schema; db.py job methods | Prompt 1 |
| M3-T002 | `kca workspace init/clean`; git worktree isolation | Prompt 2 |
| M3-T003 | Worker tool definitions; `src/worker/` scaffold | Prompt 3 |
| M3-T004 | `AgentWorker` core loop + budget enforcement | Prompt 4 |
| M3-T005 | Approval-gate pause/resume in worker + `kca decisions` CLI | Prompt 5 |
| M3-T006 | `scripts/run_job.py` local job runner | Prompt 6 |
| M3-T007 | Worker smoke tests (mock client, no real API calls) | Prompt 7 |
| M3-T008 | M3 exit criteria validation | Prompt 8 |

---

## Loop Prompt 0 — Context + hotfix M3-T000

```
Read the following files before doing anything else:
1. docs/milestones/README.md  (M3 section)
2. docs/milestones/m2/final-review.md  (risks section — note kaggle.py import shadow)
3. docs/tasks/m3/M3-T000-hotfix-kaggle-rename.md
4. tools/kca/kca.py  (find where kaggle.py is imported)

Hotfix: rename tools/kca/kaggle.py → tools/kca/kg.py to prevent shadowing the PyPI `kaggle` package.

Steps:
1. Move tools/kca/kaggle.py to tools/kca/kg.py.
2. Update every import of `kaggle` that refers to our local module:
   - In tools/kca/kca.py: change `from . import kaggle` → `from . import kg` and any `kaggle.` references.
   - In tools/kca/COMMANDS.md: update the module name column.
   - In tests/test_kca_smoke.py and tests/test_kca_db_smoke.py: update any `from tools.kca import kaggle` → `kg`.
3. Run:
     python tools/kca/kca.py kaggle --help
     python -m pytest tests/test_kca_smoke.py -v -k "kaggle or submit"
   All must pass.
4. Verify no remaining file in tools/kca/ imports `import kaggle` at module scope
   (use grep: `grep -r "^import kaggle\|^from kaggle" tools/kca/`).
5. Confirm `from . import kaggle` no longer appears anywhere in tools/kca/.

After the rename, also create the skeleton task spec file
docs/tasks/m3/M3-T001-migration-0003-job-events.md (just the header + goal placeholder).

Do NOT git add or commit. Report: files changed, test result.
```

---

## Loop Prompt 1 — Migration 0003 + DB job methods (M3-T001)

```
Read:
1. docs/tasks/m3/M3-T001-migration-0003-job-events.md
2. supabase/migrations/0001_init.sql  (agent_jobs table, job_status enum)
3. supabase/migrations/0002_kca_run_alignment.sql  (migration pattern)
4. tools/kca/db.py  (current public API)
5. docs/milestones/m2/final-review.md  (M3 follow-up list)

Goal: write migration 0003 and extend db.py with job-lifecycle methods.

--- Part A: supabase/migrations/0003_m3_worker.sql ---

Changes needed (forward-only, idempotent):

1. Add enum value 'paused' to job_status if it doesn't exist:
   ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'paused' AFTER 'running';

2. Add columns to agent_jobs (all with IF NOT EXISTS defaults):
   - workspace_path text
   - prompt        text          (extracted from payload for queryability)
   - model         text          not null default 'claude-sonnet-4-6'
   - turns_used    int           not null default 0
   - cost_usd      numeric(10,4) not null default 0
   - policy        jsonb         not null default '{}'
     (policy shape: {"max_turns":30,"max_cost_usd":5.0,"max_runtime_s":3600,
                     "allowed_tool_patterns":["kca *","pytest *"],
                     "max_side_effect":"LOCAL_WRITE"})

3. Create table agent_job_events if not exists:
   CREATE TABLE IF NOT EXISTS agent_job_events (
     id              bigserial primary key,
     job_id          uuid not null references agent_jobs(id) on delete cascade,
     event_type      text not null,
     -- values: turn_start | tool_call | tool_result | approval_pause
     --         approval_resume | budget_stop | done | error
     turn_number     int,
     input_tokens    int,
     output_tokens   int,
     cost_usd        numeric(10,4),
     event_data      jsonb not null default '{}',
     created_at      timestamptz not null default now()
   );
   CREATE INDEX IF NOT EXISTS idx_job_events_job_turn
     ON agent_job_events(job_id, turn_number);

4. Add job_id FK to human_decisions (so approval requests link back to the job):
   ALTER TABLE human_decisions
     ADD COLUMN IF NOT EXISTS job_id uuid references agent_jobs(id) on delete set null;
   CREATE INDEX IF NOT EXISTS idx_human_decisions_job
     ON human_decisions(job_id) WHERE job_id IS NOT NULL;

--- Part B: tools/kca/db.py additions ---

Add these functions to db.py's __all__:

  create_job(project_id, prompt, policy, model='claude-sonnet-4-6',
             competition_slug=None, session_id=None) → str  (job_id uuid as str)
  get_job(job_id) → dict
  lease_job(job_id, worker_id, lease_seconds=300) → bool  (True if successfully leased)
  update_job(job_id, *, status=None, workspace_path=None, turns_used=None,
             cost_usd=None, error=None, finished_at=None) → None
  append_job_event(job_id, event_type, turn_number=None, input_tokens=None,
                   output_tokens=None, cost_usd=None, event_data=None) → int  (event id)
  list_jobs(status=None, limit=20) → list[dict]
  list_pending_decisions(job_id=None) → list[dict]
  resolve_decision(decision_id, resolution, notes=None) → None
    (sets human_decisions.status = resolution, adds notes, records decided_at)

Implementation rules:
- No async. Parameterized SQL only (no f-string interpolation).
- Importable without a live DB (lazy connection).
- RemoteOperationBlocked exception for KCA_DB_TARGET=remote without KCA_ALLOW_REMOTE=1.

--- Validation ---

After implementing:
1. Apply migration to local Supabase:
     make supabase-up  (or: cat .../0003... | psql ...)
     supabase db reset  (if make target exists)
2. Run existing tests to confirm no regression:
     python -m pytest tests/ -v
3. Quick smoke:
     python -c "from tools.kca import db; print([f for f in db.__all__ if 'job' in f])"
   Must list the new job functions.

Do NOT git add or commit. Report: files changed, migration applied OK (y/n), tests result.
```

---

## Loop Prompt 2 — Workspace management (M3-T002)

```
Read:
1. docs/tasks/m3/M3-T002-workspace-management.md
2. tools/kca/kca.py  (existing subcommand groups for pattern)
3. tools/kca/_util.py  (run_cmd, emit_json patterns)
4. tools/kca/COMMANDS.md

Goal: implement `kca workspace` subcommand group.

Commands:

1. kca workspace init --job-id <id> [--branch <branch>] [--root .workspaces] [--json]
   Side effect: LOCAL_WRITE
   Logic:
   - workspace_dir = Path(root) / job_id
   - if workspace_dir.exists(): emit error {"ok": false, "error": "workspace already exists"}; exit 1
   - run: git worktree add <workspace_dir> <branch>
     (branch defaults to the current branch: `git rev-parse --abbrev-ref HEAD`)
   - create runs/ directory inside the workspace
   - update DB: update_job(job_id, workspace_path=str(workspace_dir))
     (skip DB update gracefully if SUPABASE_DB_URL not set)
   - emit {"ok": true, "workspace_path": "...", "job_id": "...", "branch": "..."}
   - exit 0

2. kca workspace clean --job-id <id> [--root .workspaces] [--force] [--json]
   Side effect: LOCAL_WRITE
   Logic:
   - workspace_dir = Path(root) / job_id
   - if not workspace_dir.exists(): emit {"ok": false, "error": "not found"}; exit 1
   - run: git worktree remove <workspace_dir> [--force if --force flag]
   - update DB: update_job(job_id, status='succeeded' or 'cancelled' per --force)
     (skip DB update gracefully if no env)
   - emit {"ok": true, "removed": "..."}; exit 0

3. kca workspace list [--json]
   Side effect: READ_ONLY
   Logic:
   - run: git worktree list --porcelain
   - parse output to list {path, branch, commit} dicts
   - filter to only .workspaces/ paths
   - emit {"ok": true, "workspaces": [...]}

Module: create tools/kca/workspace.py; register subcommand in kca.py.

Add .workspaces/ to .gitignore.

After implementing, smoke test:
  # Create a test job_id
  TEST_JOB_ID="test-$(date +%s)"
  python tools/kca/kca.py workspace init --job-id $TEST_JOB_ID --json
  ls .workspaces/$TEST_JOB_ID/
  python tools/kca/kca.py workspace list --json
  python tools/kca/kca.py workspace clean --job-id $TEST_JOB_ID --json
  git worktree list  # confirm worktree is gone

All four commands must exit 0 and emit valid JSON.

Add LOCAL_WRITE entries to tools/kca/COMMANDS.md workspace section.
Do NOT git add or commit.
```

---

## Loop Prompt 3 — Worker scaffold + tool definitions (M3-T003)

```
Read:
1. docs/tasks/m3/M3-T003-worker-scaffold.md
2. docs/milestones/README.md  (M3 "Runtime agent" section)
3. CLAUDE.md  (Operating principles — tool trust, side-effect rules)
4. tools/kca/_util.py  (SideEffect enum for reference)

Goal: scaffold src/worker/ and define the tool schema the worker exposes to the LLM.
Read docs/adr/0004-litellm-provider-layer.md and docs/tasks/m3/M3-T003-worker-scaffold.md first.

Directory structure to create:
  src/
    __init__.py
  src/worker/
    __init__.py
    tools.py     ← tool definitions and execution dispatch
    budget.py    ← budget tracker (tokens, cost, turns, runtime)
    worker.py    ← AgentWorker class (stub in this prompt)
    _types.py    ← WorkerResult, JobPolicy, ToolCall, ToolResult dataclasses

--- src/worker/tools.py ---

Define TOOL_SCHEMAS: list[dict] — in OpenAI tool schema format (ADR-0004).
LiteLLM accepts this format for all providers.

Required tools (5 minimum for M3):

1. read_file — READ_ONLY
   {"type": "function", "function": {
     "name": "read_file",
     "description": "Read a file relative to the workspace root.",
     "parameters": {"type": "object",
       "properties": {"path": {"type": "string"}},
       "required": ["path"]}}}

2. write_file — LOCAL_WRITE
   write_file(path: str, content: str) → "ok" | error string
   Safety: path traversal guard (resolved path must stay within workspace).

3. edit_file — LOCAL_WRITE
   edit_file(path: str, old_string: str, new_string: str) → "ok" | error string
   Replace first occurrence of old_string. Same path-traversal guard.

4. run_bash — side effect depends on command
   run_bash(command: str, timeout_s: int = 60)
   → JSON string: {"stdout": "...", "stderr": "...", "exit_code": N}
   Allowlist: policy.allowed_tool_patterns (e.g. ["kca *", "pytest *"])
   Hard deny: sudo, rm -rf, git push, kaggle submit (regardless of policy)
   If denied: exit_code=126, stderr="command not in allowed_tool_patterns"

5. grep_workspace — READ_ONLY
   grep_workspace(pattern: str, path: str = ".")
   → JSON string: list of {file, line_number, line}

Class ToolExecutor:
  __init__(workspace: Path, policy: JobPolicy)
  execute(tool_name: str, tool_input: dict) -> str
  Before executing: check policy.approval_gates for SUBMISSION/REMOTE_WRITE operations.
  If gate is True: raise ApprovalRequired(tool_name, tool_input, side_effect_level).

--- src/worker/_types.py ---

@dataclass class JobPolicy:
  # Budget — defaults generous; narrow per job type if needed (ADR-0004)
  max_turns: int = 60
  max_cost_usd: float = 20.0
  max_runtime_s: int = 7200
  allowed_tool_patterns: list[str] = field(
      default_factory=lambda: ["kca *", "python -m pytest *", "pytest *"])
  # LiteLLM model string (ADR-0004)
  model: str = "claude-sonnet-4-6"
  # Sampling params — see ADR-0004 table for per-job-type values
  temperature: float = 0.2   # coding default; use 0.8 for research jobs
  top_p: float = 0.90
  min_p: float | None = None
  # Approval gates (ADR-0006) — default allow for all routine ops
  approval_gates: dict = field(default_factory=lambda: {
      "kaggle_submit":  False,
      "kernel_push":    False,
      "git_push":       False,
      "dataset_upload": True,
      "git_force_push": True,
  })

@dataclass class WorkerResult:
  status: str          # done | failed | paused | budget_stop
  turns_used: int
  cost_usd: float
  duration_s: float
  final_message: str
  stop_reason: str

--- src/worker/worker.py (stub only in this prompt) ---

class AgentWorker:
  """Stub — implementation in Prompt 4."""
  def __init__(self, job_id: str, prompt: str, policy: JobPolicy,
               workspace: Path, db_url: str | None = None,
               dry_run: bool = False): ...
  def run(self) -> WorkerResult: raise NotImplementedError

Smoke check after this prompt:
  python -c "from src.worker.tools import TOOL_SCHEMAS, ToolExecutor; print(len(TOOL_SCHEMAS), 'tools defined')"
  python -c "from src.worker._types import JobPolicy, WorkerResult; p=JobPolicy(); assert p.max_turns==60; print('types ok')"

Both must succeed. Do NOT call any external API.
Do NOT git add or commit.
```

---

## Loop Prompt 4 — AgentWorker core loop + budget (M3-T004 + M3-T005a)

```
Read:
1. docs/tasks/m3/M3-T004-agent-worker-core.md
2. src/worker/worker.py  (current stub)
3. src/worker/tools.py   (ToolExecutor, TOOL_SCHEMAS)
4. src/worker/_types.py  (JobPolicy, WorkerResult)
5. tools/kca/db.py       (append_job_event, update_job signatures)

Goal: implement AgentWorker.run() using litellm.completion() in an agentic tool loop.
This is the core of M3. The worker must work in dry-run mode (no real API key) for tests.
Read docs/adr/0004-litellm-provider-layer.md for LiteLLM usage and response format.

--- src/worker/budget.py ---

class BudgetTracker:
  def __init__(self, policy: JobPolicy, started_at: float | None = None):
    self.policy = policy
    self.started_at = started_at or time.monotonic()
    self.turns = 0
    self.cost_usd = 0.0

  def record_turn(self, response) -> None:
    # litellm.completion_cost(response) handles per-provider pricing automatically.
    # Works for Claude, GPT-4o, Gemini, local Ollama (returns 0.0 for unknown models).
    self.turns += 1
    self.cost_usd += litellm.completion_cost(completion_response=response)

  def check_limits(self) -> str | None:
    # Returns None if within budget, or a string reason if exceeded:
    # 'max_turns' | 'max_cost_usd' | 'max_runtime_s'
    ...

--- src/worker/worker.py (full implementation) ---

import litellm

class AgentWorker:
  def __init__(self, job_id, prompt, policy: JobPolicy, workspace: Path,
               db_url=None, dry_run=False):
    ...
    self.dry_run = dry_run  # if True, use MockLiteLLMClient

  def run(self) -> WorkerResult:
    client = MockLiteLLMClient() if self.dry_run else None
    call_fn = client.completion if client else litellm.completion
    budget = BudgetTracker(self.policy)
    messages = [{"role": "user", "content": self.prompt}]
    executor = ToolExecutor(self.workspace, self.policy)

    while True:
      # 1. Check budget before API call
      stop_reason = budget.check_limits()
      if stop_reason:
        self._update_db(status='failed', reason=stop_reason, budget=budget)
        return WorkerResult(status='budget_stop', ...)

      # 2. Call LLM via LiteLLM (OpenAI-compatible interface; works for all providers)
      extra = {"min_p": self.policy.min_p} if self.policy.min_p is not None else {}
      response = call_fn(
        model=self.policy.model,
        max_tokens=8192,
        tools=TOOL_SCHEMAS,
        messages=messages,
        temperature=self.policy.temperature,
        top_p=self.policy.top_p,
        **extra,
      )

      # 3. Record turn cost (litellm.completion_cost handles provider-specific rates)
      budget.record_turn(response)
      msg = response.choices[0].message
      finish_reason = response.choices[0].finish_reason  # 'stop' | 'tool_calls'
      self._append_event('turn_start', budget.turns,
        cost_usd=budget.cost_usd,
        event_data={'finish_reason': finish_reason})

      # 4. Handle stop (job done)
      if finish_reason == 'stop':
        final_text = msg.content or ''
        self._update_db(status='succeeded', budget=budget)
        return WorkerResult(status='done', turns_used=budget.turns,
          cost_usd=budget.cost_usd, final_message=final_text, ...)

      # 5. Handle tool_calls (OpenAI format: msg.tool_calls is a list)
      if finish_reason == 'tool_calls':
        import json
        # Append assistant turn with tool_calls (OpenAI message format)
        messages.append({
          "role": "assistant",
          "content": msg.content,
          "tool_calls": [{"id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (msg.tool_calls or [])],
        })
        for tc in (msg.tool_calls or []):
          tool_input = json.loads(tc.function.arguments)
          self._append_event('tool_call', budget.turns,
            event_data={'tool': tc.function.name, 'input': tool_input})
          result_content = executor.execute(tc.function.name, tool_input)
          self._append_event('tool_result', budget.turns,
            event_data={'tool': tc.function.name, 'result_preview': result_content[:200]})
          # Tool results use role="tool" in OpenAI format
          messages.append({"role": "tool",
            "tool_call_id": tc.id, "content": result_content})

--- MockLiteLLMClient (in src/worker/worker.py or tests/conftest.py) ---

Used for dry_run=True. Returns a scripted sequence of responses:
  Turn 1: calls read_file("README.md")
  Turn 2: end_turn with message "dry run complete"

Usage.input_tokens and output_tokens are set to small non-zero values for budget tracking.

--- Smoke test (dry run, no API key needed) ---

import tempfile, pathlib
from src.worker._types import JobPolicy
from src.worker.worker import AgentWorker

workspace = pathlib.Path(tempfile.mkdtemp())
(workspace / "README.md").write_text("hello world")
worker = AgentWorker(
  job_id="test-001",
  prompt="Read README.md and tell me what it says.",
  policy=JobPolicy(max_turns=5),
  workspace=workspace,
  dry_run=True
)
result = worker.run()
print(result.status, result.turns_used, result.cost_usd)
assert result.status == 'done'
assert result.turns_used == 2

Run this script directly:
  python -c "<above inline>"
Must pass. Do NOT make real API calls.
Do NOT git add or commit.
```

---

## Loop Prompt 5 — Approval gate pause/resume + `kca decisions` CLI (M3-T005)

```
Read:
1. docs/tasks/m3/M3-T005-approval-gate-worker.md
2. src/worker/tools.py   (ToolExecutor.execute — where side effects are checked)
3. src/worker/worker.py  (AgentWorker.run loop)
4. tools/kca/db.py       (insert_approval_request, resolve_decision, list_pending_decisions)
5. tools/kca/kca.py      (subcommand registration pattern)

Goal: wire approval gates into the worker loop and add `kca decisions` CLI.

--- Part A: Approval gate in ToolExecutor.execute ---

When a tool call's side_effect level exceeds policy.max_side_effect:
  raise ApprovalRequired(tool_name, tool_input, side_effect_level)

ApprovalRequired is a new exception in src/worker/tools.py.

In AgentWorker.run(), catch ApprovalRequired:
  1. Insert a human_decisions row:
       decision_id = db.insert_approval_request(
         session_id=None,  # no session in M3 yet
         decision_type='tool_approval',
         prompt=f"Worker job {self.job_id} wants to call {exc.tool_name}",
         options={"approve": "allow this tool call", "deny": "block and stop job"},
         job_id=self.job_id
       )
  2. Update job status to 'paused', record 'approval_pause' event.
  3. Return WorkerResult(status='paused', turns_used=..., stop_reason='approval_required',
                         final_message=f"Waiting for approval: decision_id={decision_id}")
  4. Log to stderr: "JOB PAUSED — run `kca decisions approve --id {decision_id}` to resume"

NOTE: resume logic is M4+ scope. For M3, paused = job ends (manual restart with grant).

--- Part B: kca decisions CLI ---

New file: tools/kca/decisions.py
Register as: kca decisions list | approve | deny

1. kca decisions list [--pending] [--job-id <id>] [--json]
   Side effect: READ_ONLY
   → calls db.list_pending_decisions(job_id=...)
   → emits {"ok": true, "decisions": [{id, decision_type, status, prompt, created_at, job_id}, ...]}

2. kca decisions approve --id <decision_id> [--notes <text>] [--json]
   Side effect: LOCAL_WRITE  (just updates DB)
   → calls db.resolve_decision(decision_id, 'approved', notes=notes)
   → emits {"ok": true, "decision_id": "...", "resolution": "approved"}

3. kca decisions deny --id <decision_id> [--notes <text>] [--json]
   Side effect: LOCAL_WRITE
   → calls db.resolve_decision(decision_id, 'rejected', notes=notes)
   → emits {"ok": true, ...}

Add to tools/kca/COMMANDS.md decisions section.

--- Smoke test ---

# 1. Trigger approval gate via dry-run worker with SUBMISSION-level tool
# Add a test tool "kaggle_submit_mock" to TOOL_SCHEMAS in dry run mode
# that has side_effect=SUBMISSION. Worker should pause and emit decision_id.

# 2. With DB up:
python tools/kca/kca.py decisions list --pending --json
# Should list the paused decision.

python tools/kca/kca.py decisions approve --id <id-from-above> --notes "test approval" --json
# Should emit ok=true.

python tools/kca/kca.py decisions list --pending --json
# Should be empty.

Do NOT git add or commit.
```

---

## Loop Prompt 6 — Local job runner script (M3-T006)

```
Read:
1. docs/tasks/m3/M3-T006-local-job-runner.md
2. src/worker/worker.py  (AgentWorker interface)
3. tools/kca/db.py       (create_job, lease_job, update_job, list_jobs)
4. tools/kca/workspace.py  (init/clean via subprocess or import)

Goal: create scripts/run_job.py — the CLI to launch a local M3 worker job.

Usage:
  # Run a new job from CLI prompt:
  python scripts/run_job.py \
    --prompt "Read the README and summarize it" \
    --competition titanic \
    --max-turns 10 \
    --max-cost-usd 0.50 \
    --allowed-tools "kca *" "pytest *" \
    [--dry-run]   ← no real API calls; uses MockLiteLLMClient

  # Run an existing queued job from DB:
  python scripts/run_job.py --job-id <uuid> [--dry-run]

Lifecycle implemented by the script:
  1. Create (or load) the job in agent_jobs.
  2. Lease the job (status → running).
  3. Call kca workspace init --job-id <id> (subprocess or direct import).
  4. Instantiate AgentWorker(job_id, prompt, policy, workspace, dry_run=...).
  5. Call worker.run().
  6. Update job status in DB (succeeded/failed/paused).
  7. Call kca workspace clean --job-id <id> on success/failure
     (skip clean if paused, so workspace persists for debugging).
  8. Print final WorkerResult as JSON.

Exit codes:
  0 = job succeeded
  1 = job failed (budget, error, or tool error)
  2 = job paused (awaiting approval — not an error, but not done)

Flags:
  --dry-run      Use MockLiteLLMClient. Skip workspace init/clean (use /tmp).
  --no-cleanup   Keep workspace even on success (for debugging).
  --json         Emit final result as JSON to stdout.

After implementing, run these two validations:

Test 1 (dry run, no DB):
  python scripts/run_job.py \
    --prompt "Summarize the project" \
    --max-turns 5 \
    --dry-run --json
  → exit 0, output contains {"status": "done", "turns_used": 2}

Test 2 (dry run, with DB if available):
  KCA_DB_TARGET=local SUPABASE_DB_URL=... python scripts/run_job.py \
    --prompt "Test DB integration" --max-turns 2 --dry-run --json
  → exit 0, check DB: SELECT status FROM agent_jobs ORDER BY created_at DESC LIMIT 1;
  → should be 'succeeded'

Do NOT git add or commit.
```

---

## Loop Prompt 7 — Worker smoke tests (M3-T007)

```
Read:
1. docs/tasks/m3/M3-T007-worker-smoke-tests.md
2. tests/conftest.py  (existing fixtures: unique_competition, db_url, requires_db)
3. src/worker/worker.py  (AgentWorker, MockLiteLLMClient)
4. src/worker/_types.py  (JobPolicy, WorkerResult)
5. src/worker/tools.py   (ToolExecutor, ApprovalRequired)

Goal: create tests/test_worker_smoke.py with 6 pytest cases.
All tests must pass without a real API key and without a live Kaggle connection.
DB-dependent tests are skipped unless SUPABASE_DB_URL is set (use @requires_db decorator).

Test cases:

1. test_budget_tracker_max_turns
   - Create BudgetTracker(JobPolicy(max_turns=2))
   - Call record_turn(100, 50); record_turn(100, 50)
   - Assert check_limits() == 'max_turns'

2. test_budget_tracker_max_cost
   - Create BudgetTracker(JobPolicy(max_cost_usd=0.00001))  ← very low
   - Call record_turn(100, 100)
   - Assert check_limits() == 'max_cost_usd'

3. test_tool_executor_path_traversal_rejected
   - Create ToolExecutor(workspace=Path('/tmp/ws'), policy=JobPolicy())
   - Call execute('write_file', {'path': '../../../etc/passwd', 'content': 'bad'})
   - Assert result contains 'path traversal' or similar error message (no actual write)

4. test_tool_executor_bash_allowlist
   - Create ToolExecutor(workspace=tmp_path, policy=JobPolicy(allowed_tool_patterns=['kca *']))
   - Call execute('run_bash', {'command': 'rm -rf /'})
   - Assert result contains 'not in allowed_tool_patterns'

5. test_agent_worker_dry_run_succeeds
   - workspace = tmp_path; (workspace / "README.md").write_text("hello")
   - worker = AgentWorker("test-dry", "Read README.md", JobPolicy(max_turns=5), workspace, dry_run=True)
   - result = worker.run()
   - Assert result.status == 'done'
   - Assert result.turns_used == 2
   - Assert result.cost_usd > 0

6. test_agent_worker_budget_stop
   - worker = AgentWorker("test-budget", "loop", JobPolicy(max_turns=1), tmp_path, dry_run=True)
   - Set MockLiteLLMClient to always return tool_use (never end_turn), so budget fires.
   - result = worker.run()
   - Assert result.status == 'budget_stop'
   - Assert result.turns_used == 1

Run after writing:
  python -m pytest tests/test_worker_smoke.py -v

All 6 must pass. Fix failures before finishing.
Do NOT git add or commit.
```

---

## Loop Prompt 8 — M3 exit criteria validation

```
Goal: verify ALL M3 exit criteria. This is the gate before M3 is declared complete.

Run each check and report PASS/FAIL:

--- Schema + DB ---
1. Migration 0003 applied cleanly to local Supabase:
   cat supabase/migrations/0003_m3_worker.sql | psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1
   → PASS/FAIL

2. agent_job_events table exists:
   psql "$SUPABASE_DB_URL" -c "\d agent_job_events"
   → PASS/FAIL

3. agent_jobs has new columns (workspace_path, turns_used, cost_usd, policy):
   psql "$SUPABASE_DB_URL" -c "\d agent_jobs" | grep -E "workspace_path|turns_used|cost_usd|policy"
   → PASS/FAIL (4 lines expected)

--- Worker ---
4. Worker dry-run: job runs without API key:
   python scripts/run_job.py --prompt "test" --max-turns 5 --dry-run --json
   Exit 0, status=done in JSON
   → PASS/FAIL

5. Worker budget stop at max_turns=1:
   python -c "
   import pathlib, tempfile
   from src.worker.worker import AgentWorker
   from src.worker._types import JobPolicy
   ws = pathlib.Path(tempfile.mkdtemp())
   w = AgentWorker('t','loop',JobPolicy(max_turns=1),ws,dry_run=True)
   r = w.run()
   assert r.status == 'budget_stop', r.status
   print('PASS')
   "
   → PASS/FAIL

6. Workspace lifecycle:
   JOB_ID="m3-exit-$(date +%s)"
   python tools/kca/kca.py workspace init --job-id $JOB_ID --json
   ls .workspaces/$JOB_ID/ | grep runs
   python tools/kca/kca.py workspace clean --job-id $JOB_ID --json
   git worktree list | grep -v $JOB_ID  ← should not appear
   → PASS/FAIL

--- Approval gate ---
7. kca decisions list --pending exits 0 and emits valid JSON:
   python tools/kca/kca.py decisions list --pending --json
   → PASS/FAIL

8. Approval gate defaults to allow for kaggle_submit (ADR-0006):
   # Default policy has approval_gates["kaggle_submit"] = False → command proceeds (or fails on missing creds, not policy)
   python -c "
   from src.worker._types import JobPolicy
   p = JobPolicy()
   assert p.approval_gates.get('kaggle_submit') == False, 'kaggle_submit should default to allow'
   assert p.approval_gates.get('dataset_upload') == True, 'dataset_upload should require approval'
   print('PASS')
   "
   → PASS/FAIL

--- Import rename ---
9. No `from . import kaggle` (old module name) in tools/kca/:
   grep -r "from \. import kaggle\|import tools.kca.kaggle" tools/kca/ tests/
   → should be empty, PASS/FAIL

--- Tests ---
10. Full test suite:
    python -m pytest tests/ -v
    → report counts: X passed, Y skipped, Z failed
    → PASS if 0 failed (skipped DB tests are acceptable)

--- Milestone criterion (from docs/milestones/README.md M3) ---
11. Manual end-to-end: job runs from prompt → tool call → recorded result
    python scripts/run_job.py \
      --prompt "Read tools/kca/COMMANDS.md and summarize the side-effect levels" \
      --max-turns 5 --dry-run --json
    → result.status == 'done', result.turns_used >= 1
    → PASS/FAIL

Output summary table:
| Check | Result | Notes |
|-------|--------|-------|
| 1. Migration 0003 | ... | ... |
...

If all PASS: output "M3 EXIT CRITERIA MET".
List all files created or modified (for human git review).
Do NOT git add or commit.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
pip install litellm psycopg[binary] nbformat pyyaml pytest

# Verify worker scaffold
python -c "from src.worker._types import JobPolicy; print('ok')"
```

### Settings additions for autonomous M3 loop

Add to `.claude/settings.json` allow-list:

```json
"Bash(python scripts/run_job.py*)",
"Bash(python -c*)",
"Bash(python tools/kca/kca.py workspace*)",
"Bash(python tools/kca/kca.py decisions*)",
"Bash(git worktree*)",
"Bash(psql*)",
"Bash(grep -r*)"
```

### Full autonomous run

```bash
claude "
Execute M3 Loop Prompts 0 through 8 from docs/milestones/m3/loop-prompts.md in sequence.
Each prompt's acceptance checks must pass before moving to the next.
On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push.
Do not call the real Anthropic API (use dry_run=True for all worker tests).
Report PASS/FAIL for each prompt's verification step.
"
```

### Closeout
Q1:
- supabase 本地容器已经启动, 请使用 postgres/s3cr3t 连接并验证 DB schema 更改
- 本次milestone (M3) 任务为何生成了很多空文件, 如 `.bashrc`, `.bash_profile`, `.gitconfig` 等等, 这些文件是预留做什么用的?
- 如果这些空文件没用的话，请删除，否则保留，并 commit/push 这次的修改

Q2: 几个M3收尾任务:
- 请将我们的讨论问答放到meeting notes 中，以后的讨论都要记录
- 将上面的任务列表再列一下，让我review
- 按照docs/milestones/m3/loop-prompts.md 生成M4 的prompts文件，我会开启一个新的 agent 来运行
- commit/push 所有的修改
