# M6 / MVP-6 — final integration review

_Branch: `main`._

## Milestone exit (per docs/milestones/README.md)

> Multi-agent review + OTEL telemetry + local-model layer. A sync
> reviewer fires before high-stakes operations (`kaggle_submit`,
> `supabase_migrate`, `git_force_push`, `dataset_upload`,
> `delete_artifact`), reads the job's event trail, emits
> `approve | reject | abstain`, and either satisfies the matching
> approval gate, escalates to humans, or fails the job. OpenTelemetry
> spans cover the job, each turn, each tool call, each reviewer run,
> and each local-endpoint probe — exported to stderr, a local SQLite
> file, and Supabase. Two new job types — `log_triage` and `summarise`
> — route through a LAN local-LLM layer with cloud fallback.

**Status: met.** All 19 non-SKIP checks PASS against the live local
Supabase stack at
`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` (container IP on
the `tt_cv` Docker network; DB and local-endpoint calls run with
`dangerouslyDisableSandbox=true`).

## Validation matrix

| #  | Check                                                                                        | Result | Notes |
|----|----------------------------------------------------------------------------------------------|--------|-------|
| 1  | Migration 0006 idempotent (apply twice)                                                      | PASS   | First apply: CREATE TABLE/INDEX/ALTER; re-apply: only `NOTICE: already exists`; rc=0 both. |
| 2  | `agent_reviews` has all T000 columns                                                         | PASS   | id, job_id, run_id, reviewer_model, reviewer_kind, target_op, verdict, rationale, evidence, cost_usd, decision_id, otel_span_id, created_at. |
| 3  | `agent_telemetry_spans` exists with full shape                                               | PASS   | id, trace_id, span_id, parent_span_id, job_id, kind, name, started_at, ended_at, duration_ms, attributes, status, error. |
| 4  | `agent_jobs.otel_trace_id` + `otel_root_span_id`                                             | PASS   | Both columns present and nullable. |
| 5  | `kca local list --json` with default env.example → 0 endpoints                               | PASS   | `{"ok": true, "endpoints": [], "side_effect": "READ_ONLY"}`. |
| 6  | `kca local probe --json` with 2 endpoints reports per-endpoint ok/latency                    | PASS   | Both probes return ok=false with connection-refused on the bogus loopback ports; ok_count=0. |
| 7  | `kca local pick --json` returns fallback when none up                                        | PASS   | `{"ok": false, "reason": "no endpoint available", "fallback": "claude-haiku-4-5"}`. |
| 8  | `routing.resolve_local_or_fallback("summarise")`                                             | PASS   | None-pick → `claude-haiku-4-5`; reachable endpoint → that endpoint's served model name. |
| 9  | `kca review --help` lists `list / show / run`                                                | PASS   | All three subcommands registered. |
| 10 | `Reviewer(dry_run=True).review(...)` returns `verdict=approve`                                | PASS   | Reviewer model resolves to `claude-opus-4-7`; deterministic approve. |
| 11 | Reviewer gate fires on `kaggle_submit`; `agent_reviews` row created with `verdict=approve`   | PASS   | `_maybe_consult_reviewer` returns `"approve"`; one row inserted; idempotent on re-call. |
| 12 | Reject path: ESCALATE_REJECT=1 → `reject_escalate`; =0 → `reject_fail`                       | PASS   | Both outcomes verified against the worker hook. |
| 13 | `KCA_OTEL_EXPORTERS=console` emits stderr `kind=job/turn/tool` lines                          | PASS   | 4 span lines observed in `--dry-run` (1 job + 2 turn + 1 tool). |
| 14 | `KCA_OTEL_EXPORTERS=sqlite` populates the SQLite file                                        | PASS   | `select kind, count(*) → job=1, turn=2, tool=1`. |
| 15 | `KCA_OTEL_EXPORTERS=supabase` populates `agent_telemetry_spans`                              | PASS   | 4 rows for the run's trace_id; dry-run mode keeps `job_id=NULL` to avoid the agent_jobs FK. |
| 16 | `KCA_OTEL_ENABLED=0` → no stderr, no SQLite, no Supabase writes                              | PASS   | stderr empty; no SQLite file created at the configured path. |
| 17 | TC-3 Spaceship Titanic 8/8 checks                                                            | PASS   | R1 LR cv_auc=0.9032; R2 HGB cv_auc=0.9873; 4277-line submission with `PassengerId,Transported`; reviewer auto-approved `kaggle_submit`; no pending decisions; pytest clean. |
| 18 | `python -m pytest tests/ -v` (no DB)                                                         | PASS   | 44 passed, 9 skipped, 0 failures. |
| 19 | `python -m pytest tests/ -v` (live DB)                                                       | PASS   | 46 passed, 7 skipped, 0 failures (against `postgres@172.21.0.4:5432`). |

## DB access note

Same shape as M5. The hosted-style DSN
`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` connects to the
`supabase-db` container directly on the `tt_cv` Docker network; the host
port-mapped `localhost:5432` is the pooler, not direct Postgres. Container
IPs change on `docker compose down/up`; refresh with
`docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.

DB and local-endpoint calls (LAN 192.168.x targets) need
`dangerouslyDisableSandbox=true` because the sandbox proxy allow-list
excludes both the local Docker bridge and the LAN GPU hosts.

## What landed

- `supabase/migrations/0006_m6_reviews_spans.sql` — `agent_reviews`,
  `agent_telemetry_spans`, `agent_jobs.otel_*` columns. Forward-only,
  idempotent, additive.
- `tools/kca/db.py` — `create_review` / `get_review` / `list_reviews` /
  `find_review_for_op` / `record_span` (never-raises) / `list_spans` /
  `set_job_trace`. Verdict validation in `{approve, reject, abstain}`.
- `src/worker/local_model.py` — `LocalEndpoint`, `load_endpoints`
  (`KCA_LOCAL_ENDPOINT_<n>_*`), `probe`, `ProbeCache` (TTL), `pick_endpoint`
  (priority list / cache), `litellm_kwargs_for`, fallback model.
- `src/worker/routing.py` — `log_triage` + `summarise` → `"local"`;
  `resolve_local_or_fallback(job_type)` returns `(model_id, endpoint|None)`.
- `tools/kca/local.py` — `kca local list / probe / pick / triage / summarise`.
- `env.example` — 4 commented endpoint blocks (snorlax-vllm, snorlax-ollama,
  may-vllm, may-ollama), 5 reviewer knobs, 4 OTEL knobs, plus the routing
  knobs. `may-vllm` is documented with served name `rtx4090` (matches the
  host's actual `SERVED_MODEL_NAME`).
- `src/worker/reviewer.py` — `Reviewer`, `ReviewRequest`, `ReviewVerdict`,
  strict JSON output schema, dry-run mode, event-trail trimming, and a
  triage hand-off when the trail exceeds 8 KB.
- `src/worker/worker.py::_maybe_consult_reviewer` — wires the reviewer
  into the approval gate path with the 4 outcome tags
  (`approve / reject_escalate / reject_fail / abstain`) and the
  idempotent `find_review_for_op` skip.
- `src/worker/telemetry.py` — minimal in-house Tracer/Span with three
  exporters (console / sqlite / supabase). `KCA_OTEL_ENABLED=0`
  short-circuits all writes; spans tag job_id only when a DB-backed job
  row exists, avoiding the agent_jobs FK in dry-run mode.
- `src/worker/triage.py` — `triage_job_events` and `summarise_text` via
  LiteLLM; require-local short-circuit; cloud fallback.
- `tools/kca/review.py` — `kca review list / show / run`; `--include-reviews`
  flag on `kca decisions list`.
- `docs/adr/0011-local-model-endpoints.md`,
  `docs/adr/0012-multi-agent-review.md`,
  `docs/adr/0013-otel-console-sqlite-supabase.md`.
- `tests/test_m6_smoke.py` — 14 tests covering load_endpoints, probe,
  pick, routing fallback, reviewer dry-run, reviewer prompt truncation,
  OTEL console / sqlite / disabled, `kca local list`, `kca review list`,
  `kca review run`, and a DB-gated round trip.

## M7 follow-ups

1. **UI shell** — Lovable / TypeScript dashboard surfacing
   `agent_reviews`, `agent_telemetry_spans`, and recent runs so the
   reviewer + telemetry data has a face. Today everything is read via
   `kca review list` and SQL.
2. **Reviewer self-improvement loop** — periodic pass that mines
   `agent_reviews.rationale` for recurring rejection patterns and
   promotes them to ADR candidates (or to additions in
   `KCA_REVIEWER_TRIGGER_OPS`). Closes the loop between auditable
   verdicts and project memory.
3. **OTEL trace export to Tempo / Honeycomb** — keep the in-house
   tracer for dev, but make `KCA_OTEL_EXPORTERS=otlp` work by lazily
   loading `opentelemetry-exporter-otlp`. Off by default; the install
   stays slim.
4. **Local-model warm pool** — keep one local endpoint loaded across
   jobs (the worker currently re-probes on cache TTL expiry). Adds a
   tiny daemon that holds an OpenAI client open and exposes a same-host
   socket to the worker.
5. **Multi-agent debate mode** — ≥ 2 independent reviewers per
   high-stakes op, with a deterministic tie-break (unanimous approve
   → resume, otherwise human). Useful for high-blast-radius ops like
   `supabase_migrate`.
6. **Per-competition reviewer policy overrides** — read
   `competition_policy.reviewer.*` from the `competitions` row so each
   competition can set its own trigger set, model, and escalation
   policy without re-deploying.
