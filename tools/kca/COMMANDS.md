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

## Safety

Remote-write and submission commands are guarded by **two independent layers**:

### Layer A — kca internal gate (`tools/kca/kaggle.py`)

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
