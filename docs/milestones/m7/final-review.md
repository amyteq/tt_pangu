# M7 / KCA-CLI — final integration review

_Branch: `main`._

## Milestone exit (per docs/milestones/README.md M7)

> Give the KCA platform a stable, inspectable CLI architecture with four
> explicit layers: **Command**, **Skill**, **Tool**, **Job**. Ship a skill
> loader, a tool registry, a permission policy layer with `allow | ask | deny`
> resolution, the `kca skill list / show / run` and `kca tool list / audit /
> doctor` subcommands, four seed skills, audit logging to `.agent/audit.jsonl`,
> 12–15 smoke tests, and an architecture document.

**Status: met.** All 28 non-SKIP checks PASS. The DB live-suite check ran
against `postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`
(container IP on the local Supabase stack; calls run with
`dangerouslyDisableSandbox=true`).

## M7 EXIT CRITERIA MET

## Validation matrix

| #  | Check | Result | Notes |
|----|-------|--------|-------|
| 1  | `python -m pytest tests/ -v -m "not db"` | PASS | 59 passed, 9 skipped, 0 failures. |
| 2  | `ruff check .` | PASS | All checks passed. |
| 3  | `ruff format --check .` | PASS | 56 files already formatted. |
| 4  | Workflow YAML parses; `no-db / live-db / lint` present | PASS | `yaml.safe_load` ok; jobs set = {no-db, lint, live-db}. |
| 5  | `load_skill('run-milestone').name == 'run-milestone'` | PASS | |
| 6  | `load_skill('triage-log').arguments == ['job_id']` | PASS | |
| 7  | `load_skill('prepare-submission').approval_policy == 'default'` | PASS | |
| 8  | `'bash' in load_skill('review-pr').allowed_tools` | PASS | |
| 9  | `load_skill('__missing__')` raises `FileNotFoundError` | PASS | |
| 10 | `render_skill(run-milestone, {task_path: 'x'})` substitutes | PASS | `'x'` in rendered body. |
| 11 | `REGISTRY.list_all()` includes skill, tool, kaggle, decisions | PASS | 12 commands registered. |
| 12 | `REGISTRY.get('kaggle').side_effect == 'SUBMISSION'` | PASS | |
| 13 | `list_tools(side_effect='SUBMISSION')` ⊇ {kaggle_submit, kaggle_push} | PASS | |
| 14 | `default_decision('__unknown__') == 'ask'` | PASS | |
| 15 | `load_policy('default').resolve('kaggle_submit') == 'ask'` | PASS | |
| 16 | `load_policy('permissive-dev').resolve('bash') == 'allow'` | PASS | |
| 17 | `load_policy('competition-runner').resolve('kaggle_submit', mode='competition-finalization') == 'allow'` | PASS | |
| 18 | `kca skill list --json` lists the 4 seed skills | PASS | run-milestone, triage-log, prepare-submission, review-pr. |
| 19 | `kca skill show run-milestone --json` returns ok + meta | PASS | All frontmatter fields present in payload. |
| 20 | `kca skill run run-milestone --arg task_path=… --dry-run --json` | PASS | rendered_prompt contains the task path; 9 tool_permissions entries. |
| 21 | `kca skill run _test_fixture --dry-run --json` (no `--arg`) | PASS | exit=1; `{"ok": false, "error": "missing argument: task_path"}`. |
| 22 | `kca tool list --json` returns ≥ 15 tools | PASS | 16 tools registered. |
| 23 | `kca tool doctor --json` issues=[] | PASS | tools_checked=16. |
| 24 | `kca tool audit --json` ok=true | PASS | 2+ JSONL records present from prior runs. |
| 25 | `.agent/audit.jsonl` written by skill run | PASS | Last record: tool=bash, decision=allow. |
| 26 | `docs/architecture/kca-cli-architecture.md` ≥ 80 lines | PASS | 214 lines. |
| 27 | All 11 required section headings present | PASS | Overview, Four layers, Skill format, Tool registry, Permission policy, Audit trail, Decision gate, Directory layout, Adding a new command / skill / tool. |
| 28 | `python -m pytest tests/test_m7_smoke.py -v` | PASS | 15/15 pass in 0.36 s. |
| —  | (live-db) `pytest` with SUPABASE_DB_URL set | PASS  | 61 passed, 7 skipped, 0 failures against `postgres@172.21.0.4:5432`. |

## DB access note

DB validation reused the M5/M6 path. The hosted-style DSN
`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` connects directly to
the `supabase-db` container; the host-port-mapped `localhost:5432` is the
pooler, not direct Postgres. Container IPs change on `docker compose
down/up`; refresh with
`docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.

DB calls require `dangerouslyDisableSandbox=true`; the M7 audit path is
file-first, so the live-db check is informational only — M7 itself adds no
new migrations.

## What landed

### New code

- `tools/kca/agent/__init__.py` — package marker.
- `tools/kca/agent/skill_loader.py` — `SkillMeta`, `Skill`, `load_skill`,
  `list_skills`, `render_skill`; YAML frontmatter parser; `$arg` substitution.
- `tools/kca/agent/command_registry.py` — `CommandSpec`, `CommandRegistry`,
  module-level `REGISTRY` seeded with 12 commands (10 existing + `skill` +
  `tool`).
- `tools/kca/agent/tool_registry.py` — `ToolSpec`, `TOOL_REGISTRY` (16 tools),
  `get_tool`, `list_tools`, `default_decision`. Constants for valid
  side-effect / approval / sandbox labels.
- `tools/kca/agent/permission_policy.py` — `PolicyRecord`, `PermissionPolicy`,
  `load_policy`, `resolve_for_skill`. Resolution priority:
  deny > mode-allow > default_decision > tool default > "ask".
- `tools/kca/agent/audit.py` — `AuditRecord`, `AuditLogger` (file + optional
  DB), `log_policy_decision`. `args_hash` (SHA-256), not raw args.
- `tools/kca/skill.py` — `kca skill list / show / run [--dry-run]`.
- `tools/kca/tool.py` — `kca tool list / audit / doctor`.
- `tools/kca/kca.py` — `build_parser()` rewritten to walk
  `REGISTRY.list_all()` so new commands auto-register.

### New data

- `.kca/skills/_test_fixture/SKILL.md` — fixture for the loader test path.
- `.kca/skills/run-milestone/SKILL.md` — platform-dev milestone runner.
- `.kca/skills/triage-log/SKILL.md` — log triage via local/cloud LLM.
- `.kca/skills/prepare-submission/SKILL.md` — submission validator + decision
  record creator.
- `.kca/skills/review-pr/SKILL.md` — branch/PR review skill.
- `.kca/permissions/default.yaml` — conservative profile; submissions ask.
- `.kca/permissions/permissive-dev.yaml` — bash + git allowed; submissions ask.
- `.kca/permissions/competition-runner.yaml` — kaggle_submit allowed only in
  `competition-finalization` / `human-approved` modes; `budget_exceeded: deny`.

### Tests + docs

- `tests/test_m7_smoke.py` — 15 tests; all green in 0.36 s; no creds needed.
- `docs/architecture/kca-cli-architecture.md` — 214-line architecture doc.

### Repairs

- Cleared ruff lint + format drift (`scripts/run_job.py` E402 noqa; `db.py`
  F401 noqa for re-exported `sql`).

## M8 follow-ups

1. **Wire skill execution through the worker.** M7 ships the CLI surface
   only; `kca skill run <name>` (no `--dry-run`) emits audit + a note. M8
   should pipe a rendered skill body into `AgentWorker` with the resolved
   `JobPolicy.approval_gates` populated from `resolve_for_skill`.
2. **DB-side audit table.** `audit.py` currently best-efforts into
   `agent_job_events` with `event_type="tool_audit"`; add a dedicated
   `agent_tool_audit` migration + view if the volume justifies it.
3. **Skill schema validation.** Add a JSON-Schema gate for SKILL.md
   frontmatter so malformed seed skills fail at `list_skills()` instead of
   silently skipping.
4. **Tool registry → worker tool executor.** Hook `ToolSpec.timeout_s`,
   `sandbox`, and `approval_label` into `src/worker/worker.py::_tool_call` so
   the runtime path matches the declared policy.
5. **`.kca/skills/_test_fixture/`.** Either delete after the smoke tests
   stop depending on a real-skill fixture, or rename to a real platform
   skill.
6. **CI live-db job.** `live-db` job exists in the workflow file but has not
   been exercised on PRs yet; confirm secret wiring and gate fork forks.
