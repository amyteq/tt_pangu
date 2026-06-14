# M5 → M6 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/m5/final-review.md` and `docs/milestones/README.md` § M6._

Paste this into a fresh session that is starting **M6 (multi-agent review + OTEL telemetry + local-model layer)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M5 are complete.** Your job is to start **M6**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M6** section.
5. `docs/milestones/m5/final-review.md` — what landed in M5 (18 checks PASS) + the
   "DB access note" for the container-IP DSN pattern reused in M6.
6. `docs/milestones/m6/loop-prompts.md` — sequenced task prompts for M6.
7. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
8. Latest files in `docs/adr/`, including `0007-otel-telemetry` if present.

## State at M5 exit

- Migration `0005` applied: `research_items` extensions + `research_citations`
  table with RLS / FKs / indexes.
- `kca research add / fetch / list / show / cite` wired up; private-net guard
  blocks loopback/internal URLs by default; `external_fetch` approval gate
  via ADR-0006.
- Fetched pages land under `artifacts/research/<hash>/{raw.html,main.txt}`.
- `kca kaggle download --resume` reuses a sha256 manifest; `kca kaggle verify`
  reports ok=true on intact files, ok=false on tampered ones.
- Paused-job resume: `approval_pause → approval_resume → done` event chain
  works end-to-end; `turns_used` accumulates across the pause boundary.
- Model routing per job type (`src/worker/routing.py`, ADR-0010): Sonnet for
  implement/experiment, Opus for eval/analysis, Haiku for triage; CLI override
  always wins.
- `.github/workflows/test.yml` defines `no-db / live-db / lint` jobs.
- TC-2 House Prices: 7/7 checks, RMSLE-log1p experiment beats baseline,
  1460-line submission with `Id,SalePrice` header and `SalePrice > 0`.
- 18/18 M5 validation checks PASS against live DB at
  `postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` (container IP on
  the `tt_cv` Docker network).

DB access note: the hosted-style DSN above talks directly to the
`supabase-db` container; the host-port-mapped `localhost:5432` is the
pooler, not direct Postgres. Container IPs change on `docker compose down/up`;
refresh with
`docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.
DB calls require `dangerouslyDisableSandbox=true`.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with **Prompt 0 of `docs/milestones/m6/loop-prompts.md`** (typically migration 0006
for `agent_reviews` + `agent_telemetry_spans`). Goal of M6: a sync reviewer
agent fires before high-stakes ops and writes a verdict to `agent_reviews`;
OpenTelemetry spans cover job / turn / tool / reviewer / local-probe with
three exporters (stderr, SQLite, Supabase); new `log_triage` and `summarise`
job types route to a LAN local-LLM layer with cloud fallback; TC-3
Spaceship Titanic exercises the reviewer-gate path end-to-end.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
