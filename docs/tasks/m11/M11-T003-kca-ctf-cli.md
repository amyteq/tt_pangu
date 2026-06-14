# M11-T003: `kca ctf` CLI surface

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Add `tools/kca/ctf.py` with the `event` / `challenge` / `scope` / `solver` /
`flag` subcommands; register the `ctf` subparser in
`tools/kca/kca.py::add_parsers`; document the surface in
`tools/kca/COMMANDS.md`. All LOCAL_WRITE commands write only to the local
DB. Remote calls (challenge fetch, flag submit) require
`KCA_ALLOW_REMOTE=1` + `dangerouslyDisableSandbox` AND a matching
`ctf_scopes.target_urls` row.

## Read first

1. M11-T001 closeout (DB helpers in `src/db/ctf.py`)
2. M11-T002 closeout (new approval ops + worker wiring)
3. `tools/kca/competition.py` — `cmd_register` precedent (LOCAL_WRITE,
   idempotent)
4. `tools/kca/kg.py` — `cmd_submit` + `cmd_push` (credential-gate +
   reviewer-gate + audit-row sequence)
5. `tools/kca/research_fetch.py` — HTTP + Playwright; **reuse**, do
   not fork
6. `tools/kca/kca.py::add_parsers` — subparser registration pattern
7. `tools/kca/COMMANDS.md` — CLI documentation pattern
8. `.claude/settings.json` — ask-list (Bash(kca ctf …) entries from T002)

## Scope

1. **`tools/kca/ctf.py` subcommands.**

   ```text
   kca ctf event register --slug <slug> --name <name> [--ctftime-id <n>]
                          [--url <event-url>] [--start-at <iso>]
                          [--end-at <iso>] [--credentials-ref <path-hint>]
   kca ctf event list [--project <slug>] [--json]
   kca ctf event info --slug <slug> [--json]

   kca ctf challenge add --event <slug> --slug <slug> --name <name>
                         --category {web,crypto,rev,pwn,forensics,osint,misc}
                         [--points <n>] [--description <text>]
                         [--expected-flag-format <regex>]
                         [--attachments-path <path>]
                         [--remote-endpoint <url>] [--scope <scope-slug>]
   kca ctf challenge fetch --event <slug> --slug <slug>
                           [--via {http,playwright}]
                           # remote fetch requires KCA_ALLOW_REMOTE=1
                           # AND ctf_scopes.target_urls match
   kca ctf challenge list --event <slug> [--json]
   kca ctf challenge info --event <slug> --slug <slug> [--json]

   kca ctf scope set --slug <slug> --authorized <text>
                     --target-urls <url[,url...]>
                     [--local-only] [--expires-at <iso>]
   kca ctf scope list [--json]
   kca ctf scope verify --slug <slug> --url <url>
                        # returns exit 0 if url ∈ target_urls AND not expired

   kca ctf solver run --event <slug> --challenge <slug>
                      [--dry-run] [--reviewer-gate]
                      # if --dry-run, no challenge_run gate fires
                      # if --reviewer-gate AND not --dry-run, gate fires

   kca ctf flag submit --event <slug> --challenge <slug>
                       --flag-file <path>
                       [--dry-run]
                       # if --dry-run, prints request shape, no network
                       # if not --dry-run, requires:
                       #   1) KCA_ALLOW_REMOTE=1
                       #   2) dangerouslyDisableSandbox=true
                       #   3) ctf_scopes row covering submit endpoint
                       #   4) reviewer-gate approved (T006)
                       # flag is read from --flag-file, never echoed
   ```

2. **Credential loading.** `_load_event_credentials(event_slug)` reads
   `~/.ctf/<slug>.json` (with `username`, `token`, optional `team_id`)
   OR `CTF_<EVENT>_USERNAME` + `CTF_<EVENT>_TOKEN` env vars. This is the
   single allow-listed call-site for the guard_tool deny exception
   added in T002. Echo only boolean presence — never the value.

3. **`tools/kca/kca.py::add_parsers`.** Register the `ctf` subparser.
   Mirror the shape of `kaggle.add_parsers` / `competition.add_parsers`.

4. **`tools/kca/COMMANDS.md`.** Document each subcommand with: purpose,
   side-effect level (`READ_ONLY` / `LOCAL_WRITE` / `REMOTE_WRITE` /
   `SUBMISSION`), required env, reviewer-gate it triggers (if any),
   and a one-line example. The `flag submit` entry MUST note that the
   flag value is read from `--flag-file` and never echoed.

5. **Smoke tests.** Add `tests/test_kca_ctf_cli.py` covering:
   - `kca ctf event register` is idempotent (re-running with the same
     slug updates rather than duplicates).
   - `kca ctf scope verify` returns exit 0 for in-scope URL and exit
     non-zero for out-of-scope URL.
   - `kca ctf flag submit --dry-run` prints the request shape WITHOUT
     reading the flag file content (read header only; mock the file).
   - `kca ctf flag submit` (no `--dry-run`) refuses without
     `KCA_ALLOW_REMOTE=1` and without a matching scope.
   - No credential value or flag value appears in any test's stdout /
     stderr (audit-grep assertion).

## Non-goals

- Do not insert any challenge / event rows here. T004 owns fixtures.
- Do not exercise the reviewer-gate end-to-end. T006 owns that.
- Do not make any real network call. T007 owns the single live submit.
- Do not add a `kca ctf event watch` calendar-poll subcommand — that's
  out-of-scope follow-up.

## Acceptance criteria

- `kca ctf --help` lists the five sub-namespaces (`event`, `challenge`,
  `scope`, `solver`, `flag`).
- Each subcommand prints a useful `--help` description matching the
  side-effect level documented in COMMANDS.md.
- `tests/test_kca_ctf_cli.py` passes; no flag / credential values
  appear in stdout / stderr.
- `tools/kca/COMMANDS.md` documents each subcommand with side-effect
  level + reviewer-gate trigger.
- `kca ctf flag submit --dry-run` works without `KCA_ALLOW_REMOTE=1`;
  same command without `--dry-run` refuses without it.
- `ruff check tools/kca/` clean.

## Permissions

- Local file edits to `tools/kca/`, `tests/`.
- LOCAL_WRITE DB calls via `src/db/ctf.py` (via the local container).
- No real external network calls in this Loop Prompt.

## Closeout format

```
M11-T003 closeout
  tools/kca/ctf.py: <n> subcommands across {event, challenge, scope, solver, flag}
  Registered in tools/kca/kca.py::add_parsers: YES
  tools/kca/COMMANDS.md: kca ctf surface documented
  tests/test_kca_ctf_cli.py: <n> passed
  Audit-grep for flag/credential leakage in test stdout: 0 lines
  ruff check tools/kca/: clean
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T004 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T003 closes the "CLI surface" bullet.

## Stop condition

Stop after 60 turns. If `kca ctf flag submit` cannot be authored
without ever holding the flag string in a logged variable, halt and
propose an ADR amendment (the file should be opened, read into memory,
POSTed, and the local reference dropped — but never `print()`/`logger
.info()` the value).
