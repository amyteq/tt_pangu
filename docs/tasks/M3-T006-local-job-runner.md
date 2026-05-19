# M3-T006: Local job runner — `scripts/run_job.py`

## Milestone
M3: Python-first competition worker v0.

## Goal
Provide a single CLI entry point that orchestrates the full M3 job lifecycle:
create → lease → workspace-init → run-worker → update-status → workspace-clean.
Must work in `--dry-run` mode (no API key, no DB) for local testing.

## Read first
1. `src/worker/worker.py` — `AgentWorker` interface
2. `src/worker/_types.py` — `JobPolicy`, `WorkerResult`
3. `tools/kca/db.py` — `create_job`, `lease_job`, `update_job`, `list_jobs`
4. `tools/kca/workspace.py` — `cmd_init`, `cmd_clean` (or invoke via subprocess)
5. `scripts/README.md` — conventions

## CLI interface

```
python scripts/run_job.py [options]

Options (new job from prompt):
  --prompt TEXT          Agent prompt (required unless --job-id)
  --competition SLUG     Competition slug (optional, recorded in DB)
  --max-turns N          Default: 30
  --max-cost-usd F       Default: 5.0
  --max-runtime-s N      Default: 3600
  --allowed-tools PAT    Repeatable; default: "kca *" "pytest *"
  --model MODEL          Default: claude-sonnet-4-6

Options (existing queued job):
  --job-id UUID          Load job from DB instead of creating a new one

Behaviour flags:
  --dry-run              No real API calls; uses MockAnthropicClient
  --no-cleanup           Keep workspace dir after job (default: clean on success/failure)
  --json                 Print WorkerResult as JSON to stdout
  -v / --verbose         Print turn events to stderr
```

## Lifecycle steps

```
1. Parse args, build JobPolicy.
2. Create or load job:
     if --job-id: job = db.get_job(job_id)
     else:        job_id = db.create_job(...)  (skip if no DB in --dry-run)
3. Lease job in DB:  db.lease_job(job_id, worker_id=socket.gethostname())
   Skip in --dry-run.
4. Resolve workspace:
     if --dry-run: workspace = Path(tempfile.mkdtemp())
     else:         call kca workspace init --job-id <id> → workspace_path from JSON
5. Instantiate AgentWorker(job_id, prompt, policy, workspace, dry_run=...).
6. Call worker.run() → WorkerResult.
7. Update job status in DB (succeeded / failed / paused). Skip in --dry-run.
8. Cleanup:
     if not --no-cleanup and status != 'paused':
       if --dry-run: shutil.rmtree(workspace, ignore_errors=True)
       else: call kca workspace clean --job-id <id>
9. Print result (--json → JSON; else human-readable summary).
10. Exit: 0=done, 1=failed, 2=paused.
```

## Error handling

- If DB unavailable and not `--dry-run`: print warning and continue without DB
  (offline degraded mode). Worker runs, workspace created/cleaned, result printed.
  Never abort the job just because Postgres is unreachable.
- If `kca workspace init` fails: abort with exit 1, print error JSON.
- If API key missing and not `--dry-run`:
  print "ANTHROPIC_API_KEY not set — use --dry-run for testing"; exit 1.

## Acceptance criteria

### Test 1 — dry-run, no DB, no API key
```bash
python scripts/run_job.py \
  --prompt "Read README.md and summarize it" \
  --max-turns 5 \
  --dry-run --json
```
→ exit 0  
→ stdout JSON contains `{"status": "done", "turns_used": 2, ...}`

### Test 2 — dry-run, with DB
```bash
KCA_DB_TARGET=local SUPABASE_DB_URL="postgres://..." \
python scripts/run_job.py \
  --prompt "DB integration test" \
  --competition titanic \
  --max-turns 2 \
  --dry-run --json
```
→ exit 0  
→ `SELECT status FROM agent_jobs ORDER BY created_at DESC LIMIT 1;` → `succeeded`

### Test 3 — budget stop (max-turns=1, infinite_tool scenario)
Manual inline test or add to smoke suite:
→ exit 1, result.status = 'budget_stop'

### Test 4 — exit codes
- Paused job (approval gate hit) → exit 2
- Successful job → exit 0
- Budget/tool error → exit 1

## Stop condition
Stop after 40 turns. If workspace init fails due to git worktree limitations in the
test environment, use `--dry-run` path exclusively and document the constraint.
