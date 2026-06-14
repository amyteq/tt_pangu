# M12-T004: hackathon-experiment-loop skill + hackathon-runner permission profile + submission_checklist tool

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Ship the agent-facing pieces that drive the hackathon flow:

1. `.kca/skills/hackathon-experiment-loop/SKILL.md` — workflow recipe
   mirroring `.kca/skills/kaggle-experiment-loop/SKILL.md` but tuned
   for the hackathon submission pack.
2. `.kca/permissions/hackathon-runner.yaml` — permission profile
   matching the M9 / M10 `competition-runner.yaml` pattern.
3. New `submission_checklist` tool — input: `competition_id` +
   `run_id`; output: structured checklist driven by
   `competitions.submission_format` (jsonb).

## Tag

Routine.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 4
4. `docs/adr/0018-generalized-competition-type.md` (T001 output)
5. `docs/architecture/kca-cli-architecture.md` — four-layer model
6. `.kca/skills/kaggle-experiment-loop/SKILL.md` — skill body precedent
7. `.kca/permissions/default.yaml`, `.kca/permissions/competition-runner.yaml`,
   `.kca/permissions/permissive-dev.yaml`
8. `tools/kca/agent/tool_executor.py` — tool registry / ToolSpec shape
9. `src/worker/tools.py` — gate lookup path (post-T002 refactor)
10. `tools/kca/devpost.py` (T003 output) — adapter surface
11. `supabase/migrations/0009_m12_competition_type_teams.sql` (T002) —
    `competitions.submission_format` jsonb shape

## Scope

1. Create `.kca/skills/hackathon-experiment-loop/SKILL.md` with the
   same YAML front-matter shape as `kaggle-experiment-loop`. Body
   covers four phases:
   - **Research** — ingest hackathon rules + deadline; capture
     `submission_format` requirements.
   - **Idea** — propose 1–3 ideas; record under `research_items` /
     experiment metadata (reuse existing tables, no schema change).
   - **Prototype** — implement the minimum viable demo; record the
     run via `kg-run` (existing skill).
   - **Submission pack** — assemble `runs/<slug>/<run_id>/submission_pack/`
     and write `submission-checklist.json` via the new
     `submission_checklist` tool. Pause before any external write.
   The skill MUST end with a "Stop condition" note: do NOT call
   `devpost_submit` from inside the skill; that's M12-T007 under
   reviewer-gate.
2. Create `.kca/permissions/hackathon-runner.yaml`:
   - `devpost_submit: ask`
   - `demo_upload: ask`
   - `team_invite: deny`
   - All other gates inherit from `default.yaml`.
   Permission file follows the same structured-JSON / YAML shape as
   `competition-runner.yaml`.
3. Add the `submission_checklist` tool:
   - Implementation file: `tools/kca/submission_checklist.py` (new) or
     extend `tools/kca/run.py`.
   - Input: `competition_id` (uuid), `run_id` (uuid).
   - Reads `competitions.submission_format` jsonb (populated by T003);
     reads the contents of `runs/<slug>/<run_id>/submission_pack/`.
   - Output: a structured checklist (JSON-serializable):
     `[{"item": "README.md", "status": "done|todo|blocked", "evidence": "<path-or-blank>"}, ...]`.
   - Register the tool in `tools/kca/agent/tool_executor.py` (or
     equivalent registry) with `permission: ask` set to the new
     hackathon-runner profile.
4. Add 3–4 unit tests in `tests/test_m12_submission_checklist.py`:
   - Deterministic output for a fixed `submission_format` jsonb +
     a fixture submission_pack directory.
   - "todo" status when a required file is missing.
   - "done" status when the file exists.
   - Tool registration round-trip: registry lookup returns the tool;
     permission profile resolution returns `ask` under hackathon-runner.

## Non-goals

- Do NOT add `cmd_submit` to `tools/kca/devpost.py`. That's T007.
- Do NOT add UI pages or routes. That's T005.
- Do NOT run the skill end-to-end here. That's T006.
- Do NOT extend `submission_checklist` to mutate any DB state. It is
  a read-only inspector.
- Do NOT add a new agent under `.claude/agents/`. The skill calls into
  existing agents (`requirements-skeptic` / `design-red-team` if
  needed at ideation; default agents otherwise).
- Do NOT create new tables. Existing tables (`research_items`,
  `experiment_runs`) carry idea / metric data.

## Acceptance criteria

- `.kca/skills/hackathon-experiment-loop/SKILL.md` parses as YAML
  front-matter + Markdown body via the existing skill loader
  (`python -c "from tools.kca.agent.skill_loader import load_skill;
  load_skill('hackathon-experiment-loop')"` exits 0).
- `.kca/permissions/hackathon-runner.yaml` parses; the resolver in
  `tools/kca/agent/permission_policy.py` (post-T002) returns the
  expected gate decision for `(devpost_submit, hackathon-runner)` →
  `ask`.
- `submission_checklist` tool registers in the tool registry; calling
  it with a fixture competition + run produces a deterministic
  JSON-serializable structure with the expected `item / status /
  evidence` shape.
- `tests/test_m12_submission_checklist.py` passes (no DB needed for
  the fixture path; the DB test runs only when `SUPABASE_DB_URL` is
  set).
- Existing skill / permission / tool tests still pass.
- `ruff check .` clean. `kca skill list` shows
  `hackathon-experiment-loop` alongside `kaggle-experiment-loop`.

## Permissions

- File writes to: `.kca/skills/hackathon-experiment-loop/SKILL.md`,
  `.kca/permissions/hackathon-runner.yaml`,
  `tools/kca/submission_checklist.py` (new) or extension of
  `tools/kca/run.py`, registry hook in
  `tools/kca/agent/tool_executor.py`, `tests/test_m12_submission_checklist.py`.
- No DB writes by the tool (checklist is read-only).
- No external network calls.
- `git commit` / `git push` deferred to T009 closeout.

## Closeout format

```
M12-T004 closeout
  Skill: .kca/skills/hackathon-experiment-loop/SKILL.md (parses)
  Permission profile: .kca/permissions/hackathon-runner.yaml (parses)
  New tool: submission_checklist (registered, ask under hackathon-runner)
  Tests: tests/test_m12_submission_checklist.py (PASS / N tests)
  kca skill list: hackathon-experiment-loop present
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T005 (UI deadline + checklist pages)
```

## Related issues

- ADR-0018 — referenced for the policy hierarchy.
- Closing issue for M12 — gets a comment confirming the skill +
  profile + tool land without DB schema change.

## Stop condition

Stop after 80 turns. If the skill loader rejects the SKILL.md YAML
front-matter, halt and diagnose — do NOT edit the skill loader to
relax validation. If `submission_checklist` test output is
non-deterministic, halt — non-determinism breaks downstream M12-T008.
