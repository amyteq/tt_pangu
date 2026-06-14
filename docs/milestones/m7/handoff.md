# M7 → M8 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/m7/final-review.md` and `docs/milestones/README.md` § M8._

Paste this into a fresh session that is starting **M8 (product UI shell)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M7 are complete.** Your job is to start **M8**.

M7 shipped the operator/developer-facing CLI scaffold; M8 is the human-facing
UI shell on top of the same control plane and CLI/API surface.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M8** section (planned capabilities
   and exit criteria).
5. `docs/milestones/m7/final-review.md` — what landed in M7 (28/28 checks PASS) and
   the M8 follow-ups list.
6. `docs/architecture/kca-cli-architecture.md` — the four-layer model
   (Command / Skill / Tool / Job) the UI will call into.
7. `docs/milestones/m7/loop-prompts.md` — for context on how M7 sequenced its work and
   as a template structure for `docs/milestones/m8/loop-prompts.md` once it is written.
8. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
9. Latest files in `docs/adr/`.

## State at M7 exit

- Four-layer KCA scaffold landed: **Command** (`tools/kca/*.py`), **Skill**
  (`.kca/skills/<name>/SKILL.md`), **Tool** (`tools/kca/agent/tool_registry.py`,
  16 tools registered), **Job** (`src/worker/`).
- `tools/kca/agent/skill_loader.py`: `SkillMeta`, `Skill`, `load_skill`,
  `list_skills`, `render_skill`; YAML frontmatter parser; `$arg` substitution.
- `tools/kca/agent/command_registry.py`: `REGISTRY` seeded with 12 commands
  (10 existing + `skill` + `tool`); `kca.py` `build_parser()` walks the
  registry so new commands auto-register.
- `tools/kca/agent/tool_registry.py`: `TOOL_REGISTRY` with 16 tools; helpers
  `get_tool`, `list_tools`, `default_decision`.
- `tools/kca/agent/permission_policy.py`: `PolicyRecord`, `PermissionPolicy`,
  `load_policy`, `resolve_for_skill`; resolution priority
  `deny > mode-allow > default_decision > tool default > "ask"`.
- Three permission profiles: `.kca/permissions/{default,permissive-dev,competition-runner}.yaml`.
- `tools/kca/skill.py` (`kca skill list / show / run [--dry-run]`) and
  `tools/kca/tool.py` (`kca tool list / audit / doctor`) wired in.
- Audit logging (`tools/kca/agent/audit.py`): JSONL at `.agent/audit.jsonl`,
  best-effort DB via `append_job_event(event_type="tool_audit")`; logs
  `args_hash` (SHA-256), never raw args.
- Seed skills: `run-milestone`, `triage-log`, `prepare-submission`,
  `review-pr`, plus `_test_fixture` for tests.
- `tests/test_m7_smoke.py` (15 tests) green; `docs/architecture/kca-cli-architecture.md`
  (214 lines, 11 required headings) present.
- 28/28 M7 validation checks PASS against live DB
  (`postgres@172.21.0.4:5432`); DB calls require
  `dangerouslyDisableSandbox=true`.

Carried into M8 (from `docs/milestones/m7/final-review.md` § M8 follow-ups):

1. **Wire skill execution through the worker** — `kca skill run <name>`
   (non-`--dry-run`) currently emits audit + a note. M8 should pipe a
   rendered skill body into `AgentWorker` with `JobPolicy.approval_gates`
   populated from `resolve_for_skill`.
2. **DB-side audit table.** Promote `agent_job_events.event_type="tool_audit"`
   into a dedicated `agent_tool_audit` migration + view if the volume justifies it.
3. **Skill schema validation.** Add a JSON-Schema gate for SKILL.md frontmatter.
4. **Tool registry → worker tool executor.** Hook `ToolSpec.timeout_s`,
   `sandbox`, and `approval_label` into `src/worker/worker.py::_tool_call`
   so the runtime matches the declared policy.
5. **`.kca/skills/_test_fixture/`.** Remove or rename to a real platform skill.
6. **CI live-db job.** Confirm secret wiring and gate forks.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

There is no `docs/milestones/m8/loop-prompts.md` yet. Your first task is to draft the
M8 loop prompts (mirroring the M7 structure: numbered prompts per task, an
exit-criteria prompt, autonomous-run guidance, a closeout checklist) before
implementing anything substantive. Sequence the M8 work around the
deliverables in `docs/milestones/README.md` § M8:

- Project/competition dashboard.
- Prompt/task queue.
- Agent run logs and event timeline (use the OTEL spans from M6).
- Research notes and discussions.
- Experiment/run table.
- Approval inbox for submissions/remote actions (the UI for the M7
  permission policy + reviewer verdicts from M6).
- Artifact browser.
- Decision-gate UI showing `operation`, `cv_score`, `cost_so_far`, artifact,
  and Approve / Reject / Ask-agent-to-improve actions.

Stack constraints (per `docs/milestones/README.md` § M8): TypeScript-first React
(Next.js or Vite/React) developed in Claude Code; Supabase client must
never bypass the policy gates that M6/M7 enforce.

Confirm the M8 loop-prompt plan with the human before implementing.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
