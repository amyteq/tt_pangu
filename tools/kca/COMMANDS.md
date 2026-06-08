# kca command reference

`kca` is the stable execution layer the agent calls via Bash. Each subcommand declares a
side-effect level so the host (skills, hooks, humans) can decide whether to allow, gate,
or block it.

All commands emit a single JSON object to stdout. Exit codes: `0` ok, `1` runtime error,
`2` blocked (gated remote op without approval).

## Side-effect levels

| Level         | Meaning                                          | Default policy                                              |
|---------------|--------------------------------------------------|-------------------------------------------------------------|
| `READ_ONLY`   | No writes anywhere                               | Always allowed                                              |
| `LOCAL_WRITE` | Writes only inside the repo/workspace            | Allowed, logged                                             |
| `REMOTE_WRITE`| Writes to external service (Kaggle kernel push, dataset upload) | Requires `KCA_ALLOW_REMOTE=1` + human approval |
| `SUBMISSION`  | Kaggle competition submission                    | Requires `KCA_ALLOW_REMOTE=1` + explicit human approval     |

## Command table

| Command                       | Side-effect    | Wraps legacy tool         | Notes                                       |
|-------------------------------|----------------|---------------------------|---------------------------------------------|
| `kca nb to-py`                | `LOCAL_WRITE`  | `tools/legacy/nb2py.py`   | `.ipynb` → percent-format `.py`             |
| `kca nb to-ipynb`             | `LOCAL_WRITE`  | `tools/legacy/py2nb.py`   | percent-format `.py` → `.ipynb`             |
| `kca run init`                | `LOCAL_WRITE`  | (native)                  | Creates `runs/<comp>/<run_id>/`             |
| `kca run record-metric`       | `LOCAL_WRITE`  | (native)                  | Appends to `metrics.json`                   |
| `kca run list`                | `READ_ONLY`    | (native)                  |                                             |
| `kca kaggle submit`           | `SUBMISSION`   | _will wrap_ `kkr.py submit` | Blocked without `KCA_ALLOW_REMOTE=1` (stub)|
| `kca kaggle push`             | `REMOTE_WRITE` | _will wrap_ `kkr.py push`   | Blocked without `KCA_ALLOW_REMOTE=1` (stub)|
| `kca kaggle upload`           | `REMOTE_WRITE` | _will wrap_ Kaggle dataset upload | Blocked without `KCA_ALLOW_REMOTE=1` (stub) |
| `kca kaggle watch`            | `READ_ONLY`    | _will wrap_ `kkr.py watch`  | Stub                                       |
| `kca kaggle fetch`            | `READ_ONLY`    | _will wrap_ `kkr.py fetch`  | Stub                                       |
| `kca kaggle list`             | `READ_ONLY`    | _will wrap_ `kkr.py list`   | Stub                                       |
| `kca eval score`              | `READ_ONLY`    | (native, planned)         | Stub                                        |
| `kca eval compare`            | `READ_ONLY`    | (native, planned)         | Stub                                        |
| `kca workspace init`          | `LOCAL_WRITE`  | `git worktree add`        | Creates detached-HEAD worktree under `.workspaces/<job_id>/` |
| `kca workspace clean`         | `LOCAL_WRITE`  | `git worktree remove`     | Removes worktree; best-effort DB update     |
| `kca workspace list`          | `READ_ONLY`    | `git worktree list`       | Lists active workspaces under `.workspaces/` |
| `kca decisions list`          | `READ_ONLY`    | (native)                  | List pending human approval requests        |
| `kca decisions approve`       | `LOCAL_WRITE`  | (native)                  | Approve a pending decision                  |
| `kca decisions deny`          | `LOCAL_WRITE`  | (native)                  | Deny a pending decision                     |
| `kca ctf event register`      | `LOCAL_WRITE`  | `src/db/ctf.register_event` | Idempotent on `--slug`; `credentials_ref` is a path hint only |
| `kca ctf event list`          | `READ_ONLY`    | `src/db/ctf.list_events`  | JSON list of registered events              |
| `kca ctf event info`          | `READ_ONLY`    | (native)                  | Single event row by slug                    |
| `kca ctf challenge add`       | `LOCAL_WRITE`  | `src/db/ctf.add_challenge` | Idempotent on (event, slug); attaches optional ctf_scopes row |
| `kca ctf challenge fetch`     | `REMOTE_WRITE` | (planned via `research_fetch`) | Refuses without `KCA_ALLOW_REMOTE=1` + matching `ctf_scopes.target_urls` row |
| `kca ctf challenge list`      | `READ_ONLY`    | (native)                  | List challenges for an event                |
| `kca ctf challenge info`      | `READ_ONLY`    | `src/db/ctf.get_challenge` | Single challenge row by (event, slug)       |
| `kca ctf scope set`           | `LOCAL_WRITE`  | (native)                  | Upsert a `ctf_scopes` row keyed by name     |
| `kca ctf scope list`          | `READ_ONLY`    | (native)                  | List `ctf_scopes` rows                      |
| `kca ctf scope verify`        | `READ_ONLY`    | (native)                  | Exit 0 iff URL ∈ `target_urls` AND scope not expired; else exit 2 |
| `kca ctf solver run`          | `SUBMISSION`*  | (planned via worker)      | `--dry-run` is `LOCAL_WRITE`; otherwise fires `challenge_run` reviewer gate |
| `kca ctf flag submit`         | `SUBMISSION`   | (planned via worker)      | `--dry-run` is `LOCAL_WRITE`; otherwise fires `flag_submit` reviewer gate. Flag value is read from `--flag-file` and is **never echoed**. |

\*`kca ctf solver run` is `LOCAL_WRITE` under `--dry-run` and elevates to
`SUBMISSION`-class via the worker's `challenge_run` target_op when
`--reviewer-gate` is set. Cross-link: `src/worker/worker.py::_TOOL_TO_TARGET_OP`.

### `kca ctf` reviewer-gate map

| CLI invocation                          | Reviewer-gate op  | Default policy (per ADR-0017) |
|-----------------------------------------|-------------------|-------------------------------|
| `kca ctf solver run` (no `--dry-run`, with `--reviewer-gate`) | `challenge_run` | ask |
| `kca ctf flag submit` (no `--dry-run`)  | `flag_submit`     | ask |
| `kca ctf challenge fetch` (no `--dry-run`) | `network_egress` | deny outside `ctf_scopes.target_urls`; ask when scope+URL match |

The `--dry-run` form on every gated subcommand bypasses the network and
the reviewer gate while still emitting a JSON envelope describing the
prospective side effect — useful for skill prompts and CI smoke tests.

### `kca ctf flag submit` — flag-value discipline

- The flag value is **read from `--flag-file`** (the file is opened
  inside the Python process; nothing under `~/.ctf/` is read by the
  Claude Code Read/Edit/Write tools).
- The command emits only the integer `flag_length`, `accepted=true|false`
  and the event's HTTP status. The flag string is **never** added to
  any JSON envelope, audit row, log line, or PR body.
- The credential-loading helper `_load_event_credentials(event_slug)`
  is the single allow-listed call-site for the guard_tool deny
  exception over `~/.ctf/<slug>.json` added in M11-T002. It returns
  boolean-presence fields (`has_username` / `has_token` /
  `has_team_id`) for any output-bound code path; the underscored
  raw fields stay local to the POST-building stack frame.

## Safety

Remote-write and submission commands are guarded by **two independent layers**:

### Layer A — kca internal gate (`tools/kca/kg.py`)

`REMOTE_WRITE` and `SUBMISSION` commands check the env var `KCA_ALLOW_REMOTE`:

- Unset / not `"1"` → emit `{"ok": false, "error": "remote operation requires KCA_ALLOW_REMOTE=1 and human approval", ...}` and exit `2`.
- `KCA_ALLOW_REMOTE=1` → print `[kca] REMOTE OPERATION: ...` to stderr and proceed (currently stubs).

This makes silent execution in an autonomous loop impossible: the agent must set the env
var explicitly per shell, and a human is expected to be on the other side of the prompt.

### Layer B — `.claude/settings.json` hook layer

`Bash(python tools/kca/kca.py kaggle submit*)`, `kaggle push*`, and `kaggle upload*` are
listed under `permissions.ask` — Claude must prompt the human before invoking them.

Direct CLI bypass routes are listed under `permissions.deny` (hard block):

- `Bash(kaggle competitions submit*)`
- `Bash(kaggle kernels push*)`
- `Bash(kaggle datasets create*)`, `Bash(kaggle datasets version*)`
- `Bash(python tools/legacy/kkr.py submit*)`, `Bash(python tools/legacy/kkr.py push*)`
- `Bash(tools/legacy/kkr.py submit*)`, `Bash(tools/legacy/kkr.py push*)`

Either layer alone stops accidental submission. Both layers in place is the design.

### Approval event recording (M2-T005)

When Layer A blocks a `kaggle submit | push | upload`, kca **also** inserts a
`pending` row in `human_decisions` (best-effort — DB unavailability never
prevents the refusal). The envelope then includes:

- `approval_request_id` (uuid) — the new row's id, or absent if DB write failed
- `approval_recorded` — `true`/`false`
- `approval_warning` — present only on failure, with a short reason

This is the first link between kca's runtime gates and the control plane.
Future milestones (M3+) may move the gate from env-var to "an approved row
exists for this attempt".

## Artifact storage

Artifact bytes live in the local filesystem under
`runs/<comp>/<run_id>/artifacts/<filename>` in M2. The `artifacts.storage_path`
column uses a URI scheme so the M3 migration to Supabase Storage is a
1:1 path rewrite without schema changes. See **ADR-0008** (`docs/adr/0008-artifact-storage-local-first.md`).

## Skill invocation reference

Skills are prompt templates in `.claude/skills/*/SKILL.md`. They tell Claude how to use
kca; they never call each other and never call kca directly themselves.

| Skill      | Invocation   | Typical kca commands called                              |
|------------|--------------|----------------------------------------------------------|
| `/kg-nb`   | `/kg-nb`     | `kca nb to-py`, `kca nb to-ipynb`                        |
| `/kg-run`  | `/kg-run`    | `kca run init`, `kca run record-metric`, `kca run list`  |
| `/kg-eval` | `/kg-eval`   | `kca eval *` (future)                                    |
| `/kg-loop` | `/kg-loop`   | `kca nb` + `kca run` + `kca kaggle watch`                |

Existing skills `kaggle-evaluation-harness`, `kaggle-tooling-integration`,
`kaggle-experiment-loop`, `research-brief`, `ctf-sandbox`, `agent-iteration-review`
remain available under their current names; the `kg-*` family above is additive.

## Open questions (for follow-up milestones)

- `kca kaggle *` subcommands are stubs only — M2 will wire them into `kkr.py`.
- `kca eval *` is unimplemented.
- No `--dry-run` flag on remote commands yet; recommended for M2.
- No structured event log under `.agent/` yet; M3 work.
