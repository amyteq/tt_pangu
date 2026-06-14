# M5 / MVP-5 Loop Prompts

_Research and browser workflow + M4 follow-ups._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M4 exit criteria confirmed met (see `docs/milestones/m4/final-review.md`)._

---

## M5 at a glance

M5 adds research and browser-reading capabilities to the M4 worker, and
clears the M4 follow-ups (resume paused jobs, kaggle download checksums,
model routing, CI).

1. Web pages can be fetched with a lightweight HTTP path or an opt-in
   Playwright path; fetched content is treated as **untrusted data**.
2. `kca research add/fetch/list/show/cite` records citations with trust
   labels into `research_items` + `research_citations`.
3. `kca kaggle download` produces a sha256 manifest and supports `--resume`.
4. Paused jobs can be resumed via `scripts/run_job.py --job-id <uuid>`
   after `kca decisions approve`.
5. `JobPolicy.model` is routed per job type via `src/worker/routing.py`.
6. `.github/workflows/test.yml` runs the no-DB suite on every PR.
7. TC-2 House Prices exercises the multi-experiment regression loop.

DB validation can use the local Supabase stack via:
```bash
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@supabase-db:5432/postgres
```
(or the equivalent host-resolvable DSN — see `docs/tooling/local-supabase.md`.)

---

## M5 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M5-T000 | Migration 0005 — research_items extensions + research_citations | Prompt 0 |
| M5-T001 | DB layer — research / artifact / citation helpers | Prompt 1 |
| M5-T002 | Lightweight browser fetch tool (`research_fetch.py`) | Prompt 2 |
| M5-T003 | `kca research` CLI + `external_fetch` approval gate | Prompt 3 |
| M5-T004 | `kca kaggle download` checksum manifest + `verify` + `--resume` | Prompt 4 |
| M5-T005 | Resume paused jobs via `scripts/run_job.py --job-id` | Prompt 5 |
| M5-T006 | Model routing per job type (ADR-0010) | Prompt 6 |
| M5-T007 | `.github/workflows/test.yml` | Prompt 7 |
| M5-T008 | TC-2 House Prices end-to-end | Prompt 8 |
| M5-T009 | `tests/test_m5_smoke.py` (10–12 tests) | Prompt 9 |
| M5-T010 | M5 exit criteria + `docs/milestones/m5/final-review.md` | Prompt 10 |

---

## Loop Prompt 0 — Migration 0005 (M5-T000)

```
Read:
1. docs/tasks/m5/M5-T000-migration-0005-research-citations.md
2. supabase/migrations/0001_init.sql  (research_items, artifacts)
3. supabase/migrations/0004_m4_competition_repo.sql  (additive ALTER style)
4. docs/milestones/README.md  (M5 section)

Goal: write supabase/migrations/0005_m5_research_citations.sql.

Part A — extend research_items:
  ALTER TABLE research_items
    ADD COLUMN IF NOT EXISTS competition_id    uuid REFERENCES competitions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS source_kind       text,
    ADD COLUMN IF NOT EXISTS html_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS text_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS fetcher           text,
    ADD COLUMN IF NOT EXISTS content_hash      text,
    ADD COLUMN IF NOT EXISTS http_status       int,
    ADD COLUMN IF NOT EXISTS source_policy     jsonb NOT NULL DEFAULT '{}';
  + indexes on competition_id, content_hash

Part B — create research_citations:
  CREATE TABLE IF NOT EXISTS research_citations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_item_id uuid NOT NULL REFERENCES research_items(id) ON DELETE CASCADE,
    run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
    experiment_id   uuid REFERENCES experiments(id) ON DELETE SET NULL,
    job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
    quote           text,
    page_anchor     text,
    created_at      timestamptz NOT NULL DEFAULT now()
  );
  + indexes on research_item_id, run_id
  + ENABLE ROW LEVEL SECURITY

Verification:
  # With SUPABASE_DB_URL set:
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0005_m5_research_citations.sql
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0005_m5_research_citations.sql  # twice, idempotent
  psql "$SUPABASE_DB_URL" -c "\d research_items" | grep -E "html_artifact_id|text_artifact_id|content_hash|source_policy"
  psql "$SUPABASE_DB_URL" -c "\dt research_citations"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: migration created, idempotent re-apply, schema check.
```

---

## Loop Prompt 1 — DB layer (M5-T001)

```
Read:
1. docs/tasks/m5/M5-T001-db-layer-research.md
2. tools/kca/db.py  (__all__, _with_conn patterns)
3. supabase/migrations/0005_m5_research_citations.sql

Goal: extend tools/kca/db.py with research / artifact / citation helpers.

Add to __all__ and implement:
  create_research_item(*, url, title=None, source_kind=None, trust="unknown",
                       summary=None, competition_id=None, fetcher=None,
                       http_status=None, content_hash=None,
                       html_artifact_id=None, text_artifact_id=None,
                       source_policy=None) -> str
  get_research_item(item_id) -> dict
  list_research_items(competition_id=None, limit=50) -> list[dict]
  find_research_by_url(url) -> dict | None
  attach_artifact(kind, storage_path, *, content_hash=None,
                  byte_size=None, metadata=None) -> str
  cite_research(research_item_id, *, run_id=None, experiment_id=None,
                job_id=None, quote=None, page_anchor=None) -> str
  list_citations(run_id=None, experiment_id=None) -> list[dict]

Design rules:
- No async. Parameterised SQL only.
- find_research_by_url returns newest match.

Verification:
  python -c "
  from tools.kca import db
  symbols = sorted(s for s in dir(db) if 'research' in s or 'artifact' in s or 'citation' in s)
  print(symbols)
  "
  # With DB up:
  python -c "
  import sys; sys.path.insert(0, 'tools/kca')
  import db
  art = db.attach_artifact('research_html', '/tmp/x.html', content_hash='sha256:abc')
  r = db.create_research_item(url='https://example.com/x', title='X',
                              source_kind='page', trust='trusted_public',
                              html_artifact_id=art, content_hash='sha256:abc')
  found = db.find_research_by_url('https://example.com/x')
  assert found and found['id'] == r
  print('PASS')
  "
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: symbols added, live smoke result.
```

---

## Loop Prompt 2 — Browser fetch tool (M5-T002)

```
Read:
1. docs/tasks/m5/M5-T002-browser-fetch-tool.md
2. CLAUDE.md  (operating principles: untrusted data, side-effect levels)
3. tools/kca/_util.py  (REPO_ROOT, warn)

Goal: implement tools/kca/research_fetch.py with fetch_page(url, *, out_dir,
fetcher='http'|'playwright', timeout_s=20, user_agent=None) -> dict.

Lightweight path (default fetcher='http'):
  1. requests.get(url, timeout=timeout_s, headers=...).
  2. Save raw bytes to out_dir/raw.html.
  3. Extract main-content text (readability-lxml; fallback to BeautifulSoup
     + strip script/style/nav). Write out_dir/main.txt.
  4. content_hash = "sha256:" + sha256(raw_bytes).hexdigest().
  5. screenshot_path = None.

Playwright path (opt-in):
  1. Import playwright.sync_api lazily — clear error if not installed.
  2. chromium headless, goto(url, wait_until='domcontentloaded').
  3. Save page.content() + page.inner_text('body') + page.screenshot.

Safety (enforced in both paths):
  - Refuse localhost / 127.* / 10.* / 172.16-31.* / 192.168.* / 169.254.*
    and file://. Emit {"ok": false, "policy_warnings": ["private-net"]}.
  - Refuse URLs whose host isn't in KCA_RESEARCH_ALLOW_DOMAINS when set.
  - Abort if Content-Length or downloaded bytes > KCA_RESEARCH_MAX_BYTES
    (default 10 MB).

Verification:
  python -c "from tools.kca.research_fetch import fetch_page; print('import ok')"
  python -c "
  from pathlib import Path
  from tools.kca.research_fetch import fetch_page
  r = fetch_page('http://127.0.0.1:1/', out_dir=Path('/tmp/rf'))
  assert r['ok'] is False and 'private-net' in r.get('policy_warnings', [])
  print('PASS private-net guard')
  "
  # Local fixture HTTP server test in pytest (added in Prompt 9).
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: import ok, private-net guard works.
```

---

## Loop Prompt 3 — `kca research` CLI (M5-T003)

```
Read:
1. docs/tasks/m5/M5-T003-kca-research-cli.md
2. tools/kca/competition.py  (subcommand pattern)
3. tools/kca/kg.py  (_check_approval_gate + OPERATION_DEFAULTS)
4. src/worker/_types.py  (JobPolicy.approval_gates)
5. tools/kca/research_fetch.py  (from Prompt 2)
6. tools/kca/db.py  (from Prompt 1)

Goal: create tools/kca/research.py with fetch / add / list / show / cite
commands; add 'external_fetch' to the approval gate registry.

Commands (each --json):
  kca research fetch --url <url> [--competition <slug>]
                     [--fetcher http|playwright]
                     [--trust official|trusted_public|community|untrusted|unknown]
                     [--summary <text>]
  kca research add --url <url> [--title <t>] [--summary <s>] [--trust <l>]
                   [--competition <slug>]
  kca research list [--competition <slug>] [--limit 50]
  kca research show --id <item_id>
  kca research cite --id <item_id> [--run-id <r>] [--experiment-id <e>] [--quote <q>]

Behaviour:
  - fetch: call research_fetch.fetch_page → write raw.html + main.txt under
    artifacts/research/<hash[:12]>/. Insert artifacts rows via attach_artifact.
    Insert research_items row via create_research_item with html_artifact_id /
    text_artifact_id / content_hash. Default trust = "untrusted".
  - Domain not in KCA_RESEARCH_ALLOW_DOMAINS → call
    _check_approval_gate("external_fetch", policy). Default gate = False.
  - All commands degrade gracefully when SUPABASE_DB_URL is unset
    (emit db_warning, exit 0 for list/add).

Register in tools/kca/kca.py:
  import research as research_mod
  research_mod.add_parsers(sub)

Add to OPERATION_DEFAULTS in tools/kca/kg.py:
  "external_fetch": False,
And to JobPolicy.approval_gates default in src/worker/_types.py.

Verification:
  python tools/kca/kca.py research --help
  python tools/kca/kca.py research list --json
  python tools/kca/kca.py research fetch --url http://localhost/ --json
    → {"ok": false, "error": ".*private-net.*"}
  python -c "
  from src.worker._types import JobPolicy
  assert JobPolicy().approval_gates.get('external_fetch') is False
  print('PASS default')
  "
  python -c "
  import os; os.environ.pop('KCA_ALLOW_REMOTE', None)
  import sys; sys.path.insert(0, 'tools/kca')
  from kg import _check_approval_gate, ApprovalRequired
  try:
      _check_approval_gate('external_fetch', {'approval_gates': {'external_fetch': True}})
      print('FAIL')
  except ApprovalRequired:
      print('PASS gate blocks')
  "
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: each verification.
```

---

## Loop Prompt 4 — Kaggle download manifest + verify (M5-T004)

```
Read:
1. docs/tasks/m5/M5-T004-kaggle-download-checksum.md
2. tools/kca/kg.py  (current cmd_download)

Goal: upgrade kca kaggle download to write/verify a sha256 manifest, support
--resume, and add a sibling 'verify' subcommand.

Changes in tools/kca/kg.py:
  cmd_download(args):
    1. path = args.path or f"data/{args.competition}".
    2. manifest_path = Path(path)/"manifest.json".
    3. existing = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}.
    4. If --resume: skip files whose on-disk sha256 == manifest entry.
    5. Run `kaggle competitions download -c <slug> -p <path>` for the remainder
       (or all when --resume not set).
    6. Re-walk `path`, compute sha256/byte_size for each file, write manifest.json.
    7. Emit: {"ok": rc==0, "competition": slug, "path": path, "files": N,
              "skipped": K, "manifest": str(manifest_path),
              "side_effect": "LOCAL_WRITE"}.

  cmd_verify(args):
    1. Read manifest at args.path.
    2. For each entry: check exists + sha256 matches.
    3. Emit: {"ok": all_match, "ok_count": ok_n, "missing": [...],
              "mismatched": [...], "side_effect": "READ_ONLY"}.

Parsers:
  kca kaggle download --competition <slug> [--path <dir>] [--resume] [--json]
  kca kaggle verify --path <dir> [--json]

Verification:
  # Resume on non-existing manifest is the same as fresh download (KAGGLE creds
  # not required when --dry-run-equivalent: use a tmp path with seeded files
  # and no actual `kaggle` call):
  mkdir -p /tmp/kca-dl-test
  echo "hello" > /tmp/kca-dl-test/train.csv
  python -c "
  import hashlib, json, pathlib
  p = pathlib.Path('/tmp/kca-dl-test')
  h = hashlib.sha256(b'hello\n').hexdigest()
  (p / 'manifest.json').write_text(json.dumps({
      'competition': 'x', 'fetched_at': 'x',
      'files': [{'name': 'train.csv', 'sha256': h, 'bytes': 6}],
  }))
  print('seeded')
  "
  python tools/kca/kca.py kaggle verify --path /tmp/kca-dl-test --json
    → {"ok": true, "ok_count": 1, ...}
  echo "tampered" > /tmp/kca-dl-test/train.csv
  python tools/kca/kca.py kaggle verify --path /tmp/kca-dl-test --json
    → {"ok": false, "mismatched": ["train.csv"], ...}
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: verify pass + tamper detection.
```

---

## Loop Prompt 5 — Resume paused jobs (M5-T005)

```
Read:
1. docs/tasks/m5/M5-T005-resume-paused-jobs.md
2. scripts/run_job.py  (--job-id load path)
3. src/worker/worker.py  (AgentWorker.run, pause hooks)
4. tools/kca/decisions.py  (cmd_approve)
5. supabase/migrations/0003_m3_worker.sql  (agent_job_events)

Goal: make `scripts/run_job.py --job-id <uuid>` resume a paused job from the
last turn boundary instead of starting over.

Worker changes (src/worker/worker.py):
  - On ApprovalRequired:
    - db.update_job(job_id, status='paused', turns_used=current, cost_usd=current)
    - db.append_job_event(job_id, 'approval_pause', turn_number=current,
                          event_data={'operation': op, 'tool_input': ti,
                                      'decision_id': did})
  - Provide a class-method `AgentWorker.resume(job_id, ...)` that:
    - Loads job + payload
    - Reads agent_job_events, walks to compute (turns_used, cost_usd, last_msg)
    - Initialises BudgetTracker from that point
    - If last event is approval_resume: bypass the gate for the matching
      tool_input the next time it appears (one-shot allowlist)

Decisions changes (tools/kca/decisions.py):
  - cmd_approve: after resolve_decision, if the decision is linked to a job_id,
    append_job_event(job_id, 'approval_resume', event_data={'decision_id': did})

run_job changes (scripts/run_job.py):
  - If --job-id is given without --prompt:
    - Load existing job
    - Use AgentWorker.resume(...) instead of starting fresh
    - Same exit-code contract: 0 done, 1 failed, 2 paused (again, different op)

Verification:
  # End-to-end (requires SUPABASE_DB_URL):
  # 1) Start a dry-run job that triggers a gated op → paused
  JOB_ID=$(python scripts/run_job.py --prompt "trigger external_fetch" \
    --require-approval external_fetch --dry-run --json | python -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))")
  # 2) Find the pending decision
  DID=$(python tools/kca/kca.py decisions list --json | python -c "
  import sys,json; d=json.load(sys.stdin)['decisions']; print(d[0]['id'])")
  # 3) Approve and resume
  python tools/kca/kca.py decisions approve --id "$DID" --json
  python scripts/run_job.py --job-id "$JOB_ID" --dry-run --json
    → status=done
  # 4) Events show pause → resume → done
  psql "$SUPABASE_DB_URL" -c "select event_type from agent_job_events where job_id='$JOB_ID' order by id"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: full pause→approve→resume cycle, event trail.
```

---

## Loop Prompt 6 — Model routing (M5-T006)

```
Read:
1. docs/tasks/m5/M5-T006-model-routing.md
2. src/worker/_types.py  (JobPolicy.model)
3. scripts/run_job.py  (_build_policy / _resolve_policy)
4. docs/adr/0002-hybrid-worker-model-routing.md
5. docs/adr/0004-litellm-provider-layer.md

Goal: route model choice per job type; record + log it explicitly.

New file: src/worker/routing.py
  MODEL_ROUTES = {
      "research":   "claude-haiku-4-5",
      "implement":  "claude-sonnet-4-6",
      "experiment": "claude-sonnet-4-6",
      "eval":       "claude-opus-4-7",
      "analysis":   "claude-opus-4-7",
      "review":     "claude-opus-4-7",
  }
  def model_for(job_type: str, *, override: str | None = None) -> str:
      return override or MODEL_ROUTES.get(job_type, "claude-sonnet-4-6")

scripts/run_job.py:
  - Add --job-type <type> (default 'implement').
  - In _resolve_policy: policy.model = routing.model_for(args.job_type, override=args.model).
  - JSON output adds "model": policy.model.

New ADR: docs/adr/0010-model-routing.md
  - Table above
  - Rationale: Opus reserved for harder reasoning; Sonnet for default coding;
    Haiku for triage/log summarisation.
  - Override precedence: --model > routing table > default Sonnet.

Update docs/design-decisions.md to link the new ADR.

Verification:
  python -c "
  from src.worker.routing import model_for
  assert model_for('eval') == 'claude-opus-4-7'
  assert model_for('implement') == 'claude-sonnet-4-6'
  assert model_for('eval', override='claude-haiku-4-5') == 'claude-haiku-4-5'
  print('PASS routing')
  "
  python scripts/run_job.py --prompt p --dry-run --job-type analysis --json \
    | python -c "import sys,json; d=json.load(sys.stdin); assert 'opus' in d.get('model',''); print('PASS analysis→opus')"
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: routing + ADR present.
```

---

## Loop Prompt 7 — CI GitHub Actions (M5-T007)

```
Read:
1. docs/tasks/m5/M5-T007-ci-github-actions.md
2. Makefile  (supabase-up / test* targets)
3. tests/test_kca_db_smoke.py  (@requires_db skip behaviour)

Goal: write .github/workflows/test.yml with three jobs: no-db, live-db, lint.

Workflow shape:
  on: [pull_request, push]
  jobs:
    no-db:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5 with python-version: '3.12'
        - run: pip install -e ".[dev]"
        - run: python -m pytest tests/ -v
          # @requires_db tests auto-skip without env vars

    live-db:
      if: ${{ github.event.pull_request.head.repo.full_name == github.repository || github.event_name == 'push' }}
      runs-on: ubuntu-latest
      services:
        postgres:
          image: postgres:15
          env:
            POSTGRES_PASSWORD: postgres
          ports: ["5432:5432"]
          options: >-
            --health-cmd "pg_isready -U postgres"
            --health-interval 5s --health-timeout 5s --health-retries 10
      env:
        SUPABASE_DB_URL: postgres://postgres:postgres@localhost:5432/postgres
        KCA_DB_TARGET: local
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5 with python-version: '3.12'
        - run: pip install -e ".[dev]"
        - run: |
            for f in supabase/migrations/000*.sql; do
              psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$f"
            done
        - run: python -m pytest tests/ -v

    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5 with python-version: '3.12'
        - run: pip install ruff
        - run: ruff check .
        - run: ruff format --check .

Verification:
  yamllint .github/workflows/test.yml          # if available, else just yaml.safe_load
  python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"
    → no exception
  # Optional: `act -j no-db` runs locally if act is installed.
  python -m pytest tests/ -v   → 0 failures

Do NOT git add or commit. Report: workflow file parses, jobs listed.
```

---

## Loop Prompt 8 — TC-2 House Prices (M5-T008)

```
Read:
1. docs/tasks/m5/M5-T008-tc2-house-prices.md
2. docs/testing/competition-test-cases.md  (TC-2 section)
3. docs/milestones/m4/loop-prompts.md  Loop Prompt 8  (TC-1 structure)

Goal: run a full multi-experiment loop and assert RMSLE comparison logic.

Setup:
  TMPCOMP=$TMPDIR/m5test/kaggle-house-prices
  rm -rf "$TMPCOMP"
  mkdir -p "$TMPCOMP"/{src/house_prices,notebooks,kernels,docs/research,runs,artifacts,data}
  cd "$TMPCOMP"
  git init -q -b main
  git config user.email t@t && git config user.name t
  echo "# House Prices" > README.md
  git add . && git commit -q -m init

Baseline script (src/house_prices/baseline.py):
  - Load via sklearn.datasets.fetch_california_housing (network-free).
  - Ridge() with 5-fold KFold(random_state=42), metric = RMSLE.
  - Print JSON {"metric": "cv_rmsle", "value": <float>}.
  - Write submission.csv as `Id,SalePrice` with synthetic rows.

Iteration script (src/house_prices/log1p_target.py):
  - Same model with log1p(y); transform predictions back via expm1.
  - Should yield a lower cv_rmsle.

Loop:
  # Experiment 1
  python src/house_prices/baseline.py
  R1=$(kca run init --competition house-prices-advanced-regression-techniques \
       --hypothesis "ridge-baseline" --json | jq -r .run_dir)
  kca run record-metric --run-dir "$R1" --key cv_rmsle --value <val> --json

  # Experiment 2
  python src/house_prices/log1p_target.py
  R2=$(kca run init --competition house-prices-advanced-regression-techniques \
       --hypothesis "ridge-log1p" --json | jq -r .run_dir)
  kca run record-metric --run-dir "$R2" --key cv_rmsle --value <val> --json

Validation (print PASS/FAIL per line):
  1. R1 + R2 meta.json + metrics.json exist
  2. submission.csv 1460 lines (1 header + 1459 rows)
  3. submission.csv columns = "Id,SalePrice"
  4. SalePrice values all > 0
  5. cv_rmsle(R2) < cv_rmsle(R1)
  6. kca decisions list --json — no pending items
  7. python -m pytest tests/ -v — 0 failures

Output "TC-2 HOUSE-PRICES PASS" if all 7 pass.

Do NOT git add or commit. Report: all 7 checks.
```

---

## Loop Prompt 9 — M5 smoke tests (M5-T009)

```
Read:
1. docs/tasks/m5/M5-T009-m5-smoke-tests.md
2. tests/test_m4_smoke.py  (style + env scrub helpers)
3. tools/kca/research.py, tools/kca/research_fetch.py
4. tools/kca/kg.py  (download + verify)
5. src/worker/routing.py

Goal: create tests/test_m5_smoke.py with 10–12 pytest tests; all pass
without ANTHROPIC_API_KEY, SUPABASE_DB_URL, or KAGGLE_KEY (one test against
a local in-process HTTP server is allowed).

Required tests:
  1. test_research_fetch_refuses_localhost()
  2. test_research_fetch_against_local_server(tmp_path)
       — http.server.HTTPServer on ephemeral port; assert raw.html + main.txt + hash
  3. test_research_add_no_db(tmp_path)
  4. test_research_list_no_db()
  5. test_kaggle_download_verify_roundtrip(tmp_path)
  6. test_kaggle_download_verify_mismatch(tmp_path)
  7. test_model_routing_defaults()
  8. test_model_routing_override()
  9. test_run_job_job_type_flag()
       — assert printed model id is Opus for 'analysis'
 10. test_external_fetch_gate_blocks()
 11. test_external_fetch_gate_allows_default()
 12. test_resume_paused_dry_run(tmp_path)
       — seed agent_job_events with paused; run_job --job-id completes;
         turns_used accumulates. (Skip cleanly when no DB.)

Verification:
  python -m pytest tests/test_m5_smoke.py -v   → all pass
  python -m pytest tests/ -v                    → 0 failures

Do NOT git add or commit. Report: count + per-test status.
```

---

## Loop Prompt 10 — M5 exit criteria (M5-T010)

```
Goal: verify ALL M5 exit criteria. Gate before M5 is declared complete.

Run each and report PASS/FAIL/SKIP:

Schema + DB (requires SUPABASE_DB_URL):
 1. Migration 0005 idempotent (apply twice)
 2. research_items has html_artifact_id / text_artifact_id / content_hash / source_policy
 3. research_citations table exists

Research CLI:
 4. kca research --help lists fetch | add | list | show | cite
 5. kca research fetch --url http://localhost/ --json → ok=false (private-net)
 6. kca research fetch against a local http.server writes
    artifacts/research/<hash>/{raw.html, main.txt} and DB rows when DB up
 7. kca research list --json exit 0 without DB

Approval gate:
 8. JobPolicy.approval_gates['external_fetch'] == False
 9. _check_approval_gate('external_fetch', {'approval_gates': {'external_fetch': True}})
    raises ApprovalRequired

Kaggle download / verify:
10. kca kaggle download --resume skips already-hashed files
11. kca kaggle verify reports ok=true on intact, ok=false on tamper

Resume paused jobs (requires SUPABASE_DB_URL):
12. pause → approve → resume cycle: agent_job_events sequence is
    approval_pause → approval_resume → done

Model routing:
13. model_for('eval') is Opus; model_for('implement') is Sonnet
14. scripts/run_job.py --job-type analysis prints Opus in --json

CI:
15. .github/workflows/test.yml parses; jobs no-db | live-db | lint present

TC-2:
16. TC-2 House Prices 7/7 checks PASS

Tests:
17. python -m pytest tests/ -v (no DB) — 0 failures
18. python -m pytest tests/ -v (live DB) — 0 failures

Output:
  Print the validation matrix.
  If all non-SKIP pass: output "M5 EXIT CRITERIA MET".
  Create docs/milestones/m5/final-review.md (mirror docs/milestones/m4/final-review.md template) with
  a M6 follow-ups section:
    1. ADR-0010 route-table tuning under real load
    2. Multi-agent review loop (independent Opus/GPT review of Sonnet output)
    3. Local vLLM/Ollama integration for log triage
    4. OTEL telemetry dashboard for turns_used / cost_usd / tool_call latency
    5. Per-competition browser allowlists in competition_policy
    6. Background research watcher (RSS/forum new-post polling)

Do NOT git add or commit. Report: full validation matrix, final status.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
pip install requests readability-lxml beautifulsoup4 pyyaml
pip install -e .   # ensure kca is on PATH

# Optional Playwright for JS-heavy pages
pip install playwright && playwright install chromium

# Verify M5 base
kca --help
python -c "from src.worker._types import JobPolicy; p=JobPolicy(); print(p.approval_gates.get('external_fetch'))"
```

### DB

```bash
# Local Supabase stack already running:
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@supabase-db:5432/postgres
# (or postgres://postgres:postgres@127.0.0.1:54322/postgres if using `make supabase-up`)
```

### Settings additions for autonomous M5 loop

Add to `.claude/settings.json` allow-list (extend the M4 list):

```json
"Bash(kca research*)",
"Bash(kca kaggle verify*)",
"Bash(python scripts/run_job.py --job-id*)",
"Bash(python scripts/run_job.py --job-type*)",
"Bash(mkdir -p /tmp/kaggle-house-prices*)",
"Bash(git -C /tmp/kaggle-house-prices*)",
"Bash(python /tmp/kaggle-house-prices/src/house_prices/*.py)"
```

### Full autonomous run

```bash
claude "
Execute M5 Loop Prompts 0 through 10 from docs/milestones/m5/loop-prompts.md in sequence.
Each prompt's acceptance checks must pass before moving to the next.
On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push.
Do not call the real Anthropic API or Kaggle API.
Use --dry-run for all worker tests.
For DB validation use SUPABASE_DB_URL=postgresql://postgres:s3cr3t@supabase-db:5432/postgres
(or postgres://postgres:postgres@127.0.0.1:54322/postgres for the make supabase-up stack).
Report PASS/FAIL for each prompt's verification step inline.
"
```

### Closeout
vLLM/Ollama:
我有2个本地算力资源:
1. RTX 4090 on Void Linux
- hostname: snorlax
- IP: 192.168.18.66
- service: vllm-coder (active)
  - MODEL="Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
  - SERVED_MODEL_NAME="rtx4090"
  - HOST="0.0.0.0"
  - PORT="8000"
- service: ollama (installed but inactive)
  - MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"
  - HOST="0.0.0.0"
  - PORT="11434"
2. RTX 3090 on Windows (WSL Debian)
- hostname: may (currently shutdown)
- IP: 192.168.18.77
- service: vllm (inactive due to some glitches)
  - MODEL="openai/gpt-oss-20b"
  - SERVED_MODEL_NAME="rtx4090"
  - HOST="0.0.0.0"
  - PORT="8000"
- service: ollama (installed but inactive)
  - MODEL="qwen3:1.7b" # or qwen25-7b
  - HOST="0.0.0.0"
  - PORT="11434"

对unreachable 的 host/LLM service, 请也将相应配置包含到 env.example 中, 建议相应job 执行前可以先快速检查这些 service 的 availability, 其他还有什么需要补充的请告知, 请继续完成 M6 的计划规划之后, commit 并 push
