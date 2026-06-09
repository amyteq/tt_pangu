# M11 CTF workflow architecture

_Milestone: M11 — authorized CTF / lab workflow._
_Date: 2026-06-09._

## 1. CTFtime calendar discovery and event registration (human action)

The CTF entry point is the [CTFtime calendar](https://ctftime.org/calendar/).
The human browses upcoming events, decides which to enter, and registers
on the event site directly (no browser-automated sign-up in M11).

After registration the human:

1. Creates a credential file at `~/.ctf/<event-slug>.json` with shape:
   ```json
   { "username": "...", "token": "...", "team_id": "..." }
   ```
   (`team_id` is optional; omit for individual participation.)
   Alternatively: set `CTF_<EVENT>_USERNAME` + `CTF_<EVENT>_TOKEN` env vars.
2. Runs `kca ctf event register --slug <event-slug> --name "..." --url "..." --start <ISO> --end <ISO>` to create a `ctf_events` row in the local DB. This is a LOCAL_WRITE; it does not touch the event site.
3. Runs `kca ctf event info --slug <event-slug>` (READ_ONLY) to verify the row.

The `.claude/hooks/guard_tool.py` hook denies direct `~/.ctf/*.json` reads from any path except the allow-listed `kca ctf` flow. The credential is never echoed in logs, audit rows, or PRs.

## 2. Credential file shape and load path (two-tier model)

KCA distinguishes two credential tiers — the CTFtime platform account
(single per user) and per-event accounts (one per event that requires
its own signup). Each tier has its own storage location, loader, and
hook carve-out.

### Tier 1 — CTFtime.org platform account (`~/.env`)

Used for the CTFtime calendar / event-registration flow and for events
that accept CTFtime SSO (no separate per-event signup needed).

Storage: `~/.env` (one file per user, single account).

Required keys:

| Key | Required | Notes |
|---|---|---|
| `CTFTIME_USERNAME` | yes | e.g. `flyingfox` |
| `CTFTIME_PASSWORD` | yes (or `CTFTIME_TOKEN`) | session password |
| `CTFTIME_TOKEN`    | alternative to `CTFTIME_PASSWORD` | API token, if the user prefers |

Loader: `tools/kca/ctf.py::_load_ctftime_credentials()` — the single
allow-listed call-site for the `.claude/hooks/guard_tool.py` carve-out on
`~/.env`. Direct Read/Edit of `~/.env` via the Claude Code tools is
**denied** at the hook layer; only the loader (running in-process inside
the kca CLI) may open the file.

Fallback: if `~/.env` is absent, the loader checks the same names in
the process environment (`CTFTIME_USERNAME` + `CTFTIME_PASSWORD` /
`CTFTIME_TOKEN`) for CI-friendliness.

### Tier 2 — Per-event accounts (`~/.ctf/<slug>.json`)

Used when an event requires its own signup distinct from CTFtime SSO.

Storage: `~/.ctf/<event-slug>.json` (one file per event).

Resolution order (first match wins):

1. `~/.ctf/<event-slug>.json` — JSON object with `username`, `token`, optional `team_id`.
2. Environment variables `CTF_<EVENT_SLUG_UPPER>_USERNAME` and `CTF_<EVENT_SLUG_UPPER>_TOKEN`.

Loader: `tools/kca/ctf.py::_load_event_credentials(slug)` — the single
allow-listed call-site for the hook carve-out on `~/.ctf/`. Raises
`CredentialsMissing` if neither path yields a complete pair; exit code 1
with a redacted message (no credential value emitted).

### Common discipline

- Credentials are held in memory only for the duration of the HTTP call
  inside the POSTing function (`cmd_flag_submit`).
- The raw values are dropped from memory immediately after the request
  body is built.
- The values are NEVER written to `ctf_attempts`, `agent_reviews`,
  `human_decisions`, `agent_tool_audit`, stdout, stderr, PR bodies, or
  GitHub comments.
- `_safe_cred_presence(creds)` strips both loaders' output to
  `{source, has_username, has_token, has_team_id}` for any stdout-bound
  use; only those booleans cross the function boundary.

## 3. Challenge inventory and category triage

After event registration:

1. `kca ctf challenge add --event <slug> --challenge-slug <slug> --category web --points 100 --description "..."` inserts a `ctf_challenges` row (LOCAL_WRITE).
2. `kca ctf challenge list --event <slug>` lists challenges with their category and scope reference.
3. `kca ctf scope set --event <slug> --challenge <slug> --target-urls "http://localhost:18080" --local-only true` creates or updates a `ctf_scopes` row.

Category triage in the solver loop:

- `web` — docker-compose service; solver uses httpx against localhost; no external network needed for frozen bundles.
- `crypto` — in-process Python; no network; deterministic from committed parameters.
- `pwn`, `rev`, `forensics` — recognized as valid categories in `ctf_challenges.category` but the M11 solve loop does not implement agent loops for these; filed as M11 follow-up.

The challenge inventory is read-only from the perspective of the solver worker.
Adding challenges requires a separate `kca ctf challenge add` invocation (LOCAL_WRITE, not subject to the `challenge_run` gate).

## 4. Solver execution under the `challenge_run` gate

The `challenge_run` operation (ADR-0017) gates any solver invocation against a target whose URL appears in `ctf_scopes.target_urls` OR is a local in-scope service.

Gate flow for a local-solve run:

1. Worker stages the solver invocation: target URL + challenge slug.
2. `should_consult_reviewer("challenge_run")` returns True for all three permission profiles.
3. `run_review(target_op="challenge_run", ...)` writes an `agent_reviews` row.
4. `decision_api` surfaces the pending decision; the UI Approval Inbox renders it.
5. Human approves via UI or `kca decisions approve --id <id>`.
6. Worker proceeds: `kca ctf solver run --event <slug> --challenge <slug>`.
7. For `web`: `docker compose up -d` → wait for HTTP 200 → run `solver_template.py::solve()` → capture flag → `docker compose down -v`.
8. For `crypto`: in-process `solver_template.py::solve()` → capture flag.

The `kca ctf solver run --dry-run` path skips the gate entirely (records a
dry-run audit row but does not open an `agent_reviews` row).

Solver execution is local only. No remote challenge endpoint is contacted
in the M11 frozen-bundle path; the gate fires to establish the approval-flow
discipline for when a live event's challenge endpoint IS the target.

## 5. Flag recovery and sha256 verification

After the solver returns:

1. The flag string is held only in the local Python process variable.
2. `hashlib.sha256(flag.encode()).hexdigest()` computes the digest.
3. The digest is compared against `expected.sha256` in the challenge bundle:
   - Match → `accepted=true` in the resulting `ctf_attempts` row.
   - No match → `accepted=false`; the solve loop halts and reports the discrepancy without printing the flag or the expected value.
4. `flag_length` (integer) is recorded in `experiment_runs` via `kca run record-metric --key flag_length --value <N>`.
5. `ctf_db.record_attempt(challenge_id=..., accepted=True, http_status=None, flag_length=N, response_excerpt="<scrubbed>")` writes the `ctf_attempts` row. The flag string is never passed to this function.
6. The flag is dropped from the local variable immediately after step 5.

For the web challenge (`web-1-cookie-monster`) the harness generates a fresh flag per run and writes its sha256 into `expected.sha256` before starting docker-compose. The `expected.sha256` file is the single stable artifact; the flag value is ephemeral.

For the crypto challenge (`crypto-1-tiny-rsa`) the flag is mathematically determined by the committed `params.json` (RSA parameters); `expected.sha256` is static and committed.

## 6. Flag submission under the `flag_submit` gate

The `flag_submit` operation (ADR-0017) gates any call to a live event's submit API.

Gate flow:

1. Worker stages the flag submission: event slug + challenge slug + flag string (in memory only).
2. `should_consult_reviewer("flag_submit")` returns True for all three profiles.
3. `run_review(target_op="flag_submit", ...)` writes an `agent_reviews` row (rationale includes challenge slug + event slug only; NOT the flag value).
4. Human approves via UI or `kca decisions approve --id <id>`.
5. For a live event (T007): `kca ctf flag submit --event <slug> --challenge <slug> --flag <flag>` runs the actual HTTP POST to the event's submit endpoint. The `ctf_scopes.target_urls` row must cover the submit endpoint. `KCA_ALLOW_REMOTE=1` must be set.
6. The `ctf_attempts` row is written with `accepted=true|false`, `http_status=<int>`, `flag_length=<N>`. The flag string is NOT stored in the DB.
7. The CLI output is exactly `accepted=true` or `accepted=false` plus the HTTP status. The flag is never echoed to stdout.

For LOCAL_WRITE dry-run paths (no live event), `http_status` is stored as `null`; `accepted` reflects the local sha256 comparison result.

## 7. Out-of-scope follow-ups

The following capabilities are recognized by the M11 data model and taxonomy
but are deferred to future milestones:

### Pwn / rev / forensics solve loops

`ctf_challenges.category` supports `pwn`, `rev`, `forensics` but M11 only
implements agent-loop solvers for `web` and `crypto`. Follow-up: author
`ctf-sandbox/SKILL.md` extensions for pwntools-based binary exploitation,
Ghidra / radare2 assisted reverse engineering, and forensic-artifact analysis.

### CTFtime calendar auto-watch

M11 requires the human to manually check CTFtime. A future milestone should
add `kca ctf event watch --ctftime` that polls the CTFtime API (with human
approval for each new event it proposes to register) and surfaces upcoming
events on the UI Dashboard. Blocked on: CTFtime API rate-limit policy,
team-credential rotation, and the per-event scope-set automation.

### Multi-event identity rotation

`ctf_attempts.event_account` and `ctf_attempts.team_id` columns (M11 T001
carry-over from T000 multi-account debate) exist to track which account
ran which attempt. M11 does not implement the rotation logic: picking a
different `~/.ctf/<slug>.json` per attempt or per event day. Follow-up:
author a `ctf-identity-rotation` policy in `.kca/permissions/` and wire
it to the credential-load path in `cmd_flag_submit`.

### Per-challenge rate-limit column

ADR-0017 notes a `ctf_scopes` extension: a `rate_limit_per_hour` column
so the worker can self-throttle before the gate fires. Not implemented in
M11. Follow-up: migration 0009 extension + guard in `cmd_flag_submit`.

### Hook-level enforcement of the Discovery / Debate Gate

Deferred from M9.4: a PreToolUse hook that refuses `Edit` on `src/**`
for `arch:` tasks without `discovery/` evidence under
`docs/evidence/<milestone>/discovery/`. Not implemented in M11.

### httpx-level `network_egress` interceptor for subprocess egress

ADR-0017 §enforcement-layer-pinning records that the `httpx`-level
interceptor for subprocess calls that bypass the reviewer-gate (e.g., a
solver script that shells out to `curl`) is deferred. The reviewer-gate
and `.claude/hooks/guard_tool.py` are the primary enforcement layers for M11.
