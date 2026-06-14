# design-red-team report for the KCA replacement of `tools/legacy/kkr.py`

Source: tools/legacy/kkr.py @ 6231fd1f54b6, tools/legacy/kkr.yaml @ 0543e71a5aa1
Upstream archaeology: docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md
Upstream skeptic:     docs/evidence/m9_4-kkr-replay/requirements-skeptic.md

_Produced under the M9.4 Discovery / Debate Gate (M9.4-T005). The
agent body lives in `.claude/agents/design-red-team.md`; this
artefact is a manual execution of that agent's protocol. The
"proposed design" being refuted is the current M9 / M10 trajectory
that absorbed `kkr.py`'s push/submit semantics into `tools/kca/kg.py`
(via `cmd_push`, `cmd_submit`) without an explicit multi-owner
contract._

## alternatives

1. **Owner-as-first-class field in `RunSpec`.** Introduce an explicit
   `owner: str` field on the platform's run/experiment record and on
   every CLI subcommand (`kca kaggle push --owner harrysun2006 ...`).
   Resolve credentials by looking up a Supabase-managed
   `kaggle_credentials` table keyed by `(project_id, owner)`. Sketch:
   the CLI passes `owner` through to a worker; the worker loads the
   matching credential set into a short-lived per-job environment
   (no `os.environ` mutation). Key tradeoff vs proposal: adds one
   schema column and one Supabase RLS path, but eliminates ambient
   credential state and makes "which owner pushed this kernel" a
   queryable fact rather than a log artefact. Closest legacy
   evidence: `kkr.py:528–548` (per-owner env), `kkr.py:520` (owner
   derived from `id`).

2. **Per-job dotenv subprocess isolation.** Keep the
   `.env.{owner}` convention from `kkr.py:541`, but run each
   Kaggle-touching subcommand in a fresh subprocess with only the
   selected dotenv loaded, instead of mutating the parent process's
   `os.environ` (`kkr.py:543`). Sketch: `kca` shells out to a small
   `kaggle-runner` subprocess; the parent never sees credential
   state. Key tradeoff vs proposal: zero schema change, lower risk
   of credential bleed between concurrent jobs, but adds
   per-subcommand fork overhead and makes long-running watch loops
   slightly harder to instrument with the platform's OTEL spans
   (`agent_telemetry_spans` from M6).

3. **Credential-scoped tool wrappers via the M7 permission policy.**
   Treat `kaggle_submit(owner)` and `kernel_push(owner)` as separate
   operations in `.kca/permissions/*.yaml` (M7 policy layer), each
   with its own `allow/ask/deny` resolution and its own audit row.
   Sketch: tools never directly read credentials; the permission
   layer materialises a short-lived credential token per call.
   Key tradeoff vs proposal: tightest audit story (every owner-scoped
   external write is a distinct permission decision), at the cost
   of expanding the M7 policy surface from one Kaggle-write operation
   to N (one per active owner) and requiring policy authors to
   enumerate owners in advance. Closest legacy evidence:
   `kkr.py:587–595` (single ambient `KaggleApi`).

## dropped_capabilities

- **Multi-account submission via suffix convention.** The legacy
  `kkr.yaml` runs four config families (a/b/c/d) each in `h` /
  `m` variants, routing to `harrysun2006` and `firefly2006`
  respectively. The current platform trajectory has no explicit
  owner field on its run record; absorbing `kkr.py push/submit`
  into `tools/kca/kg.py::cmd_push` without §3's owner-as-first-class
  field silently collapses this to a single owner. Evidence:
  `tools/legacy/kkr.yaml:57–121` (every per-config block declares
  its own `id: owner/slug`); `tools/legacy/kkr.py:520` (owner
  parsed from `id`); `tools/legacy/kkr.py:528–548` (owner-keyed
  env-file resolution). Survives in: alternative 1, alternative 2,
  alternative 3, legacy.
- **Per-experiment `--env <path>` override.** Legacy CLI allowed
  overriding the dotenv path on a single invocation
  (`tools/legacy/kkr.py:535–537`). The proposed `kca kaggle push`
  signature (per `docs/milestones/m10/loop-prompts.md` "What's in scope") does
  not expose a `--env` flag. Evidence: `tools/legacy/kkr.py:2165`.
  Survives in: alternative 2, legacy.
- **`kernel_sources` cross-owner reuse.** Legacy YAML can reference
  another owner's kernel (`andreasbis/aimo-3-utils`) as a build
  source. Evidence: `tools/legacy/kkr.yaml:61, 69`. Survives in:
  legacy, alternative 1 (with an explicit
  `cross_owner_kernel_sources` allow-list); not yet wired into
  alternative 3.
- **Stable JSON shape for `--json` output.** Legacy `_emit_ok` at
  `tools/legacy/kkr.py:332` and `_emit_fail` define a contract many
  ad-hoc scripts depend on. The platform's `kca kaggle push --json`
  emits a different shape (an `experiment_runs` row). Evidence:
  unavailable in the current branch — route to `open_disagreements`.

## long_term_costs

cognitive_load:    Without an explicit owner field, every new
                   contributor must read `_load_env_for_owner` to
                   understand that `kca kaggle push` silently picks a
                   credential from `os.environ` and that the
                   `.env.<owner>` filesystem schema is load-bearing.
                   Alternative 1 trades that for one schema column
                   and one CLI flag.
ops_burden:        Ambient-credential failures look like "the wrong
                   account submitted" — a 3am page that requires
                   reading audit logs to reconstruct. Alternative 2
                   reduces this to "subprocess exited 1"; alternative
                   3 surfaces it as a denied permission policy
                   resolution before any external write.
extensibility:     Next likely scope expansions: (a) a third Kaggle
                   account for a teammate, (b) per-owner Kaggle API
                   throttling (Kaggle's rate limits are per-owner,
                   not per-IP). The current trajectory needs a code
                   change to absorb (a); alternative 1 needs a row
                   insert. Neither (a) nor (b) is easy on the
                   current trajectory because owner is not modelled
                   at all.
blast_radius:     Worst case on the current trajectory: a job
                   intended for `firefly2006` pushes to
                   `harrysun2006` because the ambient env was set
                   by the previous job. That kernel push goes on
                   the wrong leaderboard, may consume the other
                   account's daily-submission quota, and the
                   `submissions` row has no field to record which
                   owner ran it. Alternatives 1 and 3 prevent this
                   structurally; alternative 2 prevents it via
                   subprocess isolation.

## open_disagreements

- The current M10 plan accepts the proposed
  `tools/kca/kg.py::cmd_push` without an explicit owner contract.
  Disagree — next step: open a follow-up issue
  (labels: `area:kaggle`, `type:feature`, `policy:approval-required`)
  to add an `owner` field on `runs` / `experiment_runs` and a
  `--owner` flag on `kca kaggle push` / `kca kaggle submit` before
  the next live kernel-push milestone after M10.
- The `--env <path>` override is not in the M10 scope. Disagree —
  next step: ask human whether `.env.<owner>` is the public
  contract (in which case `--env <path>` is the documented escape
  hatch) or an implementation detail (in which case the platform
  owes a migration to a credentials table).
- The `_msg` 500-char cap and the `{ts}` template are not
  re-documented in the M10 spec. Disagree — next step: spike a
  parity test (`tests/test_kkr_submit_message_cap`) that exercises
  the cap against `tools/kca/kg.py::cmd_submit` before M11.
- The legacy `_emit_ok` / `_emit_fail` JSON shape may have
  consumers outside this repo. Disagree — next step: research the
  JSON-shape contract (grep for `kkr_push.json`, `kkr_watch.json`
  filename literals in any sister repo); defer to a follow-up
  issue if a real consumer is found.
- The `kaggle==1.8.3` monkey-patch dependency is hidden tribal
  knowledge. Disagree — next step: write a smoke test against the
  pinned `kaggle` version (in `tests/test_kaggle_version_smoke.py`)
  that asserts `owner/model-slug` parsing and `docker_image`
  field acceptance work without patches; if it fails, the
  knowledge becomes a test failure rather than a silent push
  failure.
