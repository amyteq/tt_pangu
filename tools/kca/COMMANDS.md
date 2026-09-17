# kca command reference

`kca` is the stable execution layer the agent calls via Bash. Each subcommand declares a
side-effect level so the host (skills, hooks, humans) can decide whether to allow, gate,
or block it.

All commands emit a single JSON object to stdout. Exit codes: `0` ok, `1` runtime error,
`2` blocked (gated remote op without approval).

## Side-effect levels

| Level         | Meaning                                          | Intended policy                                             |
|---------------|--------------------------------------------------|-------------------------------------------------------------|
| `READ_ONLY`   | No writes anywhere                               | Always allowed                                              |
| `LOCAL_WRITE` | Writes only inside the repo/workspace            | Allowed, logged                                             |
| `REMOTE_WRITE`| Writes to external service (Kaggle kernel push, dataset upload) | Requires `KCA_ALLOW_REMOTE=1` + human approval |
| `SUBMISSION`  | Kaggle competition submission                    | Requires `KCA_ALLOW_REMOTE=1` + explicit human approval     |

The right-hand column is the **design intent**, not a description of what runs today: only `kca kaggle upload` is actually refused without `KCA_ALLOW_REMOTE`. See [Layer A](#layer-a--kca-internal-gate-toolskcakgpy) for the per-operation truth, and treat the intent column as the target state.

## Command table

| Command                       | Side-effect    | Wraps legacy tool         | Notes                                       |
|-------------------------------|----------------|---------------------------|---------------------------------------------|
| `kca nb to-py`                | `LOCAL_WRITE`  | `tools/legacy/nb2py.py`   | `.ipynb` → percent-format `.py`             |
| `kca nb to-ipynb`             | `LOCAL_WRITE`  | `tools/legacy/py2nb.py`   | percent-format `.py` → `.ipynb`             |
| `kca run init`                | `LOCAL_WRITE`  | (native)                  | Creates `runs/<comp>/<run_id>/`             |
| `kca run record-metric`       | `LOCAL_WRITE`  | (native)                  | Appends to `metrics.json`                   |
| `kca run list`                | `READ_ONLY`    | (native)                  |                                             |
| `kca kaggle <sub>`            | varies         | see below                 | 9 subcommands, each with its own stub/real classification and side-effect level — [own table below](#kca-kaggle-subcommands) |
| `kca eval score`              | `READ_ONLY`    | (native, planned)         | Stub                                        |
| `kca eval compare`            | `READ_ONLY`    | (native, planned)         | Stub                                        |
| `kca workspace init`          | `LOCAL_WRITE`  | `git worktree add`        | Creates detached-HEAD worktree under `.workspaces/<job_id>/` |
| `kca workspace clean`         | `LOCAL_WRITE`  | `git worktree remove`     | Removes worktree; best-effort DB update     |
| `kca workspace list`          | `READ_ONLY`    | `git worktree list`       | Lists active workspaces under `.workspaces/` |
| `kca goal init`               | `LOCAL_WRITE`  | (native)                  | Create the active `goals` row + write `experiments/<comp>/goal.md`; refuses with `ACTIVE_GOAL_EXISTS` if one is active (M14-T002) |
| `kca goal show`               | `READ_ONLY`    | (native)                  | Show the active goal + `goal_remaining_delta` (best LB vs `target_lb_score`); `--json` |
| `kca goal update`             | `LOCAL_WRITE`  | (native)                  | Partial field update or `--close --reason ...`; rewrites `goal.md` |
| `kca notify doctor`           | `READ_ONLY`    | (native)                  | Preflight the HITL channel: config, every bot's `TELEGRAM_*` presence (never values), live `getMe` per bot, `gh auth`, quiet-hours + routine budget (#197) |
| `kca notify send`             | `REMOTE_WRITE` | Telegram Bot API / `gh issue comment` | Levelled push (`gate`/`attention`/`digest`/`info`), `--bot` selects the entry bot; `digest`/`info` are deduped, daily-capped and quiet-hours-deferred unless `--force`; `--dry-run` renders without sending. Exit 0 sent (every channel took it) / 2 suppressed / 1 failed or `partial` |
| `kca notify decision`         | `REMOTE_WRITE` | Telegram Bot API + `gh issue comment` | Opens a decision request: GitHub comment is the record (`decision_id`/`plan_hash`/options/expiry), Telegram card is a read-only mirror linking to it (no option buttons in phase 1a — nothing consumes taps). Answer with `/decide <decision_id> <option_id>`; ids are validated against that parser at creation; lapsed requests never auto-approve |
| `kca contracts validate`      | `READ_ONLY`    | (native)                  | Validate every ledger record under `competitions/` against `contracts/` (ADR-0023): JSON Schema shape, then the cross-record invariants — id uniqueness, foreign keys, the Experiment/Run retry rule, the submission reconciliation rules. `--competition <slug>` narrows it; `--require-all-entities` also fails when an entity has no record (the CI coverage floor). No DB, no network |
| `kca contracts schemas`       | `READ_ONLY`    | (native)                  | List the eleven entities with their schema file, id pattern and record path |
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

### `kca kaggle` subcommands

Every `cmd_*` in `tools/kca/kg.py` gets a row here, and `tests/test_commands_doc_parity.py` fails the build if this table and `kg.py` disagree — on membership or on classification.

**Status** is the only column that says whether the command does anything: `real` means it performs the work described; `stub` means it returns `_emit_stub(...)` — a `{"ok": true, "stub": true}` envelope, exit `0`, no Kaggle call — and nothing else. **Side-effect** is the plain risk level: `local-only` (no network), `network-read` (reads Kaggle, changes nothing there), `remote-write` (changes state on Kaggle). **Envelope** is the `side_effect` value the JSON carries, from the `SideEffect` enum.

| Command               | Status   | Side-effect                                  | Envelope                                        | `kg.py` | Notes |
|-----------------------|----------|----------------------------------------------|-------------------------------------------------|---------|-------|
| `kca kaggle submit`   | **real** | **remote-write** — leaderboard submission     | `SUBMISSION`                                    | `:283`  | Runs `kaggle competitions submit` (`kg.py:337-353`); with `--kernel` it submits that kernel's output straight from Kaggle storage instead of uploading a local file. Checks `KAGGLE_USERNAME` / `KAGGLE_KEY` presence and the ADR-0020 §7 daily-budget gate first, then `_check_approval_gate("kaggle_submit")` — **which allows by default** (see Layer A below). |
| `kca kaggle push`     | **real** | **remote-write** (`--dry-run`: local-only)    | `REMOTE_WRITE` (`READ_ONLY` under `--dry-run`)  | `:433`  | Runs `kaggle kernels push`, then auto-polls the run until terminal (`--no-watch` opts out, `--poll-seconds` default 60, `--max-poll-minutes` default 60); returns push response + watch result. Credentials and the concurrency / daily-budget gates run on the real path only, then `_check_approval_gate("kernel_push")` — **which also allows by default**. A pre-push `ruff` lint refuses kernels with undefined names (`--skip-lint` / `KCA_SKIP_KERNEL_LINT=1`). A kernel push is **not** a leaderboard submission (#77). |
| `kca kaggle upload`   | **real** | **remote-write** — dataset version            | `REMOTE_WRITE`                                  | `:1038` | Runs `kaggle datasets version -p <path> -m "kca upload"`. The one Kaggle op whose gate **denies by default**: it refuses with exit `2` unless `KCA_ALLOW_REMOTE` is set, and records a pending `human_decisions` row when it does. |
| `kca kaggle download` | **real** | network-read + local-write                    | `LOCAL_WRITE`                                   | `:1077` | Runs `kaggle competitions download -c <slug> -p <path>` (default `./data/<competition>`), then writes `manifest.json` with per-file sha256 and size. `--resume` skips the fetch when every manifest entry already matches on disk. A missing `kaggle` CLI degrades to `rc=127` and still refreshes the manifest. No approval gate. |
| `kca kaggle verify`   | **real** | local-only                                    | `READ_ONLY`                                     | `:1200` | Re-hashes the files listed in `<path>/manifest.json` and reports `missing` / `mismatched`. Never contacts Kaggle. |
| `kca kaggle watch`    | **real** | network-read                                  | `READ_ONLY`                                     | `:1249` | Polls `kaggle kernels status <ref>` up to `--max-iterations` times, `--poll-seconds` apart, and reports `complete` / `error` / `unknown`. `--run` is a legacy alias for `--kernel`. |
| `kca kaggle score`    | **real** | network-read (`--update-db`: + local-write)   | `READ_ONLY`, or `LOCAL_WRITE` once a DB write lands | `:1317` | Reads the public LB via the Kaggle Python API `competition_submissions`, filtered by `--kernel-ref` / `--message-filter`. With `--update-db --submission-id` it writes `public_lb_score`, `status` and `public_score` onto that `submissions` row and re-labels the envelope `LOCAL_WRITE` (`kg.py:1387`); it refuses the DB write when no Kaggle row matched the filters. |
| `kca kaggle fetch`    | **stub** | local-only (declares `READ_ONLY`)             | `READ_ONLY`                                     | `:1392` | `_emit_stub("fetch", ...)` — echoes `--run` back and exits `0`. Contacts nothing. |
| `kca kaggle list`     | **stub** | local-only (declares `READ_ONLY`)             | `READ_ONLY`                                     | `:1396` | `_emit_stub("list", ...)` — always `{"ok": true, "stub": true}`. Contacts nothing. |

Two things this table is here to stop you assuming. First, a `stub` row's exit `0` is evidence of nothing: `fetch` and `list` never reach Kaggle, so any workflow that treats their success as "the run is there" is reading a constant. Second, the `real` remote-write rows genuinely reach Kaggle, and for `submit` and `push` **no gate in this process stops them** — `KCA_ALLOW_REMOTE` is load-bearing for `upload` alone. What holds on submit and push is the standing `CLAUDE.md` principle 6 rule to ask a human first, which is a written rule, not an enforced one.

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

`kca kaggle submit`, `push` and `upload` each call `_check_approval_gate(op, _policy_from_env())` (`kg.py:42-50`). It raises `ApprovalRequired` — envelope `{"ok": false, "error": "ApprovalRequired: <op>", ...}`, exit `2` — only when the operation is gated **and** `KCA_ALLOW_REMOTE` is unset. Whether an operation is gated comes from `KCA_POLICY`'s `approval_gates` map, falling back to `OPERATION_DEFAULTS` (`kg.py:21-30`):

| Operation        | Command               | `OPERATION_DEFAULTS` | Behaviour with no `KCA_POLICY` set                         |
|------------------|-----------------------|----------------------|-------------------------------------------------------------|
| `kaggle_submit`  | `kca kaggle submit`   | `False` (`kg.py:22`) | **not gated** — submits without `KCA_ALLOW_REMOTE`          |
| `kernel_push`    | `kca kaggle push`     | `False` (`kg.py:23`) | **not gated** — pushes without `KCA_ALLOW_REMOTE`           |
| `dataset_upload` | `kca kaggle upload`   | `True` (`kg.py:24`)  | gated — refuses with exit `2` unless `KCA_ALLOW_REMOTE` is set |

So Layer A does **not** make silent execution in an autonomous loop impossible. It stops `upload`; `submit` and `push` run unless a `KCA_POLICY` blob explicitly sets `approval_gates.kaggle_submit` / `.kernel_push` to `true`. The stricter env-var-only gate this section used to describe does exist — `_gate()` at `kg.py:53-59` — but it has **no call sites**; do not rely on it. This is the same gap `CLAUDE.md` principle 6 records: ask a human before every Kaggle submission or kernel push, because nothing here will stop you.

### Layer B — `.claude/settings.json` permission layer

This layer covers **push and upload only**, and it covers submission not at all:

| Pattern                                            | List in `.claude/settings.json` | Effect                          |
|----------------------------------------------------|----------------------------------|----------------------------------|
| `Bash(kaggle kernels push*)`                       | `ask` (`:100`)                   | prompts the human                |
| `Bash(kaggle datasets create*)` / `version*`       | `ask` (`:101-102`)               | prompts the human                |
| `Bash(python tools/kca/kca.py kaggle push*)`       | `ask` (`:103`)                   | prompts the human                |
| `Bash(python tools/kca/kca.py kaggle upload*)`     | `ask` (`:104`)                   | prompts the human                |
| `Bash(kaggle competitions submit*)`                | **`allow`** (`:91`)              | runs with no prompt              |
| `Bash(python tools/kca/kca.py kaggle submit*)`     | **`allow`** (`:92`)              | runs with no prompt              |
| `Bash(python tools/kca/kca.py*)`                   | `allow` (`:88`)                  | the catch-all every `kca` call matches |

No Kaggle pattern appears under `permissions.deny`. The legacy `kkr.py` deny entries this section used to list are not in the file either — `tools/legacy/kkr.py` invocations match no Kaggle-specific rule at all.

Both layers being in place is the design; neither layer is in place for submission. Combined with Layer A allowing `kaggle_submit` by default, a submission today passes unchallenged from the Bash tool to Kaggle. Asking first is a written rule (`CLAUDE.md` principle 6), and is the only thing standing there.

### Approval event recording (M2-T005)

When Layer A does block one of `kaggle submit` / `push` / `upload` — today that is `upload` by default, and the other two only under an explicit `KCA_POLICY` — kca **also** inserts a `pending` row in `human_decisions` (best-effort — DB unavailability never prevents the refusal). The envelope then includes:

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

- `kca kaggle fetch` and `kca kaggle list` are still stubs (`kg.py:1392`, `kg.py:1396`); the other seven subcommands are real. See the [`kca kaggle` subcommands](#kca-kaggle-subcommands) table.
- `kca eval *` is unimplemented.
- `--dry-run` exists on `kca kaggle push` only. `submit` and `upload` have no dry-run path.
- No structured event log under `.agent/` yet; M3 work.
