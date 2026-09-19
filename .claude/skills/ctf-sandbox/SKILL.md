---
name: ctf-sandbox
description: Use for authorized CTF challenge solving only: local challenge analysis, sandboxed exploitation, solver scripts, flags, and writeups within explicitly provided scope.
---

# CTF Sandbox Workflow

Use this workflow only for explicitly authorized CTF challenges, local labs, or target scopes provided by the human.

## Safety scope

Allowed:

- Analyze local challenge files.
- Run challenge containers or binaries provided for the CTF.
- Interact with explicitly provided CTF endpoints.
- Write solver scripts and educational writeups.

Not allowed:

- Scan public IP ranges or unrelated domains.
- Attack third-party systems.
- Steal or exfiltrate real credentials.
- Deploy malware, persistence, or destructive payloads.
- Use CTF techniques outside the authorized scope.

## Workflow

1. Restate the authorized scope and target.
2. Inventory files, services, ports, and constraints.
3. Identify category: crypto, pwn, web, reversing, forensics, misc, OSINT, etc.
4. Form hypotheses and run minimal safe checks.
5. Keep commands and outputs logged.
6. Build a solver or exploit only within the challenge scope.
7. Produce a concise writeup with root cause, steps, flag, and mitigation idea if relevant.

If scope is unclear, ask the human to define the CTF target before running security tooling.

## KCA CLI surface (M11+)

Use these `kca ctf` subcommands when the challenge has been registered against the local DB (`ctf_events` / `ctf_challenges` / `ctf_scopes`):

- `kca ctf event list` / `kca ctf event info --slug <event>` — READ_ONLY inventory.
- `kca ctf challenge list --event <event>` / `kca ctf challenge info --event <event> --slug <challenge>` — READ_ONLY inventory.
- `kca ctf scope verify --slug <scope> --target <url>` — READ_ONLY in-scope/out-of-scope check before any network call.
- `kca ctf solver run --event <event> --challenge <challenge> [--dry-run]` — invokes the solver loop. Without `--dry-run` this is a SUBMISSION-class call gated by the `challenge_run` reviewer-op (see `docs/adr/0017-ctf- approval-gates.md`); with `--dry-run` it records only the prospective side-effect shape and skips the network/docker call.
- `kca ctf flag submit --event <event> --challenge <challenge> --flag-file <path> [--dry-run]` — submits a recovered flag to the event API. Gated by the `flag_submit` reviewer-op; the CLI never echoes the flag string, only `accepted=true|false` and HTTP status.

Operational discipline for the solver loop (M11-T005 pattern):

- Recover the flag in-memory; verify against `expected.sha256` (sha256 of the flag string) instead of comparing flag values directly.
- Record only `flag_length` into `experiment_run_metrics` / `ctf_attempts`. Never persist the flag value to any column, log line, JSON envelope, or filesystem cache.
- Scrub solver `response_excerpt` of the flag string (and any flag-format-regex match) before passing it to `src/db/ctf.py::record_attempt`.
- Use `kca run init --competition ctf-<event-slug>` + `kca run record-metric --key flag_length --value <len>` to attach the attempt to an `experiment_runs` row so the M11 audit trail joins cleanly.
- For web challenges: `docker compose -f <bundle>/docker-compose.yml down -v` after each solve, regardless of pass/fail, so no dangling container outlives the solve cycle.
