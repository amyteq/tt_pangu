# M11-T005: Agent worker loop solves bundled challenges locally

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Drive `AgentWorker` through one solve cycle per bundled challenge from
T004 — web and crypto — recovering both flags locally without real
network. Record `ctf_attempts` rows (`accepted=true`) and matching
`experiment_runs` rows with `flag_length` only (not value). No reviewer
gate fires in this Loop Prompt: gates are exercised in T006 with the
gates ON.

## Read first

1. M11-T004 closeout (bundled challenges + scope rows)
2. `.claude/skills/ctf-sandbox/SKILL.md` — workflow body; may be
   extended here to cite the new `kca ctf` commands
3. `src/worker/worker.py` — `AgentWorker` loop, `_tool_call`,
   `_should_consult_reviewer` (T002 wiring)
4. `tools/kca/run.py` — run-init + record-metric
5. `tools/kca/ctf.py::cmd_solver_run` (T003)
6. `src/db/ctf.py::record_attempt`
7. `docs/tasks/m9/M9-T002-baseline-loop.md` — closest precedent (Kaggle
   baseline-loop pattern)

## Scope

1. **Per-challenge solve cycle.** For each bundled challenge:
   - Read `challenge.yaml` + `description.md` + attachments.
   - Category triage (web vs. crypto — straightforward from `category`
     field, but the agent should restate the strategy in its log).
   - For web: `docker compose -f data/ctf/<event>/<web-slug>/docker-
     compose.yml up -d` brings up the local service on the private
     network; agent solver uses `httpx` against `localhost:<port>`.
   - For crypto: in-process solve — no docker, no network.
   - Recover the flag.
   - Verify against `expected.sha256` (sha256 of the flag string).
   - Record via `kca ctf solver run --event <slug> --challenge <slug>
     --dry-run` (since the reviewer-gate exercise is T006, this T005
     pass runs with `--dry-run` semantics for the gate path, but
     **does not** skip the actual solve).

2. **Run / attempt records.** For each successful solve:
   - `kca run init --competition ctf-<event-slug> --run-id <challenge-slug>`
   - `kca run record-metric --run-id <run-id> --name flag_length --value <len>`
   - `record_attempt(challenge_id=..., accepted=True, http_status=None,
     flag_length=<len>, response_excerpt='<solver excerpt with flag
     redacted>', run_id=<run-id>)`
   - NEVER pass the flag string to any recorder.

3. **Skill extension.** Optionally extend
   `.claude/skills/ctf-sandbox/SKILL.md` workflow body to cite the
   `kca ctf solver run` / `kca ctf flag submit` commands. Keep the
   safety-scope section unchanged.

4. **Docker cleanup.** After each web challenge solve:
   `docker compose -f <path> down -v`. The closeout must show no
   dangling containers from this Loop Prompt.

## Non-goals

- Do not fire any reviewer gate in this Loop Prompt. T006 exercises
  gates ON.
- Do not submit any flag to a real event. T007 owns that.
- Do not solve more than the two bundled challenges from T004.
- Do not log the flag value anywhere — `experiment_runs.metrics`,
  `ctf_attempts.response_excerpt`, agent log, audit row, closeout.
- Do not modify `src/worker/worker.py` or `tools/kca/ctf.py` in this
  Loop Prompt (their scaffolding is owned by T002 / T003). If the
  solve surfaces a worker bug, file it as a follow-up issue and stop.

## Acceptance criteria

- Both bundled challenges solved: flag recovered and verified against
  `expected.sha256`.
- `ctf_attempts` has exactly 2 new rows with `accepted=true` for the
  current solve cycle.
- `experiment_runs` has 2 matching rows; each row's `metrics` JSON
  contains `flag_length` but NO `flag`, `flag_value`, or any string
  that matches the flag-format regex.
- Agent log / stdout / stderr audit-grep: 0 occurrences of the actual
  flag string (sha256-check after redaction).
- `docker ps --filter "name=m11-" --format "{{.ID}}"` returns empty
  after solve cleanup.
- The two `experiment_runs` rows are visible via `kca run list --json`.

## Permissions

- Local file reads under `data/ctf/`.
- LOCAL_WRITE DB inserts via `src/db/ctf.py` helpers.
- `docker compose up -d` / `down -v` on local-only networks.
- Local HTTP calls to `localhost:<port>` (in scope per the web
  challenge's `ctf_scopes.target_urls`).
- `dangerouslyDisableSandbox=true` for DB calls (per protocol §3).

## Closeout format

```
M11-T005 closeout
  Web challenge: <slug> — solved, flag_length=<n>, sha256 verified
  Crypto challenge: <slug> — solved, flag_length=<n>, sha256 verified
  ctf_attempts new rows: 2 (accepted=true)
  experiment_runs new rows: 2 — flag_length recorded; flag NOT logged
  Docker cleanup: no dangling containers
  Audit-grep for flag string in logs: 0 hits
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T006 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T005 closes the "local solve loop"
  bullet.

## Stop condition

Stop after 100 turns. If either challenge cannot be solved within 40
turns, halt and ask — DO NOT downgrade the challenge to a trivial
one. If the agent ever holds the flag string in a logged variable,
halt and refactor before continuing. If docker-compose fails to come
up on the sandbox network, halt and propose either (a) a
`docker network create m11-net` step in T004 or (b) a port-host
alternative scope.
