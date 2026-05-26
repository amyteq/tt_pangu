# legacy-archaeologist report for tools/legacy/kkr.py + tools/legacy/kkr.yaml

Source: tools/legacy/kkr.py @ 6231fd1f54b6, tools/legacy/kkr.yaml @ 0543e71a5aa1

_Produced under the M9.4 Discovery / Debate Gate as the demonstration
replay (M9.4-T005). The agent body lives in
`.claude/agents/legacy-archaeologist.md`; this artefact is a manual
execution of that agent's protocol because the
`.claude/skills/design-archaeology/SKILL.md` orchestration is owned by
M9.3-T001 and was not yet on disk at replay time._

## 1. Workflows supported

- `push <name>` — build a Kaggle notebook from `<code_file>` in
  `kkr.yaml`, push it as a Kaggle kernel under `<owner>/<slug>`.
  Entry: `kkr.py:2194`; main: `kkr.py:2293`; new-run impl:
  `_create_new_run` at `kkr.py:1511`.
- `submit [name]` — submit (a) a freshly built version or (b) an
  existing version selected by `NAME`, `--run`, or `--kernel/--version`.
  Entry: `kkr.py:2216`; existing-version path: `_submit_existing` at
  `kkr.py:1733`.
- `watch [name]` — poll remote kernel status until terminal.
  Entry: `kkr.py:2244`; impl: `_watch_impl` at `kkr.py:1943`.
- `fetch [name]` — download `source/output` artifacts for a selected
  run. Entry: `kkr.py:2267`; impl: `_fetch_impl` at `kkr.py:2006`.
- `status [name]` — one-shot remote-status query. Entry:
  `kkr.py:2272`; impl: `_status_impl` at `kkr.py:2074`.
- `list` — list tracked runs from the local registry. Entry:
  `kkr.py:2277`; row builder uses `_list_registry_entries` at
  `kkr.py:848`.

Cross-cutting flags on every subcommand: `--dry-run`, `--json`,
`--yaml`, `--run-root`, `--env`, `--quiet`, `-v/--verbose`
(`kkr.py:2158–2173`).

## 2. Hidden assumptions

- `kkr.yaml` has a `_base` block whose keys are merged with the
  per-config block via `_deep_merge` (`kkr.py:421–445`, validated at
  `kkr.py:491`). Per-config blocks override scalars and union-extend
  list-typed keys (`LIST_CFG_KEYS` at `kkr.py:60–66`).
- The `id` field MUST be `owner/slug`; `_slug_parts` at `kkr.py:466`
  raises if missing. Owner is derived from `id`, not specified
  independently — evidence: `kkr.py:520`.
- `_msg` template is `kkr@{ts}` by default (`kkr.py:514`,
  `_format_submit_message` at `kkr.py:551`), `{ts}` is filled at submit
  time, 500-character cap enforced at `kkr.py:558` — Kaggle rejects
  longer messages.
- `kkr.yaml` carries inline comments flagging two patches required
  against `kaggle==1.8.3`: one for `owner/model-slug` `model_sources`
  format (`kkr.yaml:31`), another to enable the H100 `docker_image`
  override (`kkr.yaml:38`). These patches are tribal knowledge — if the
  replacement does not preserve or supersede them, real pushes silently
  fail.
- Local registry root defaults to `.kkr/registry/` under
  `--run-root`; `--run-root` defaults to `DEFAULT_RUN_ROOT`
  (`kkr.py:2162`). Multiple concurrent runs on the same host all share
  one registry tree.

## 3. User personas / accounts / owners — load-bearing

This is the section the original migration missed (see
`docs/meeting-notes/2026-05-24-r3.md` §6). The legacy tool *encodes*
multi-Kaggle-account submission as a first-class concept and the
replacement must not erase it.

- **`harrysun2006`** owner — see `kkr.yaml:7` `_base.id`, `kkr.yaml:58`
  (`a09h`), `kkr.yaml:77` (`b09h`), `kkr.yaml:90` (`c09h`),
  `kkr.yaml:108` (`d09h`). The `h` suffix in config names means "owned
  by harrysun2006".
- **`firefly2006`** owner — see `kkr.yaml:66` (`a09m`), `kkr.yaml:83`
  (`b09m`), `kkr.yaml:98` (`c09m`), `kkr.yaml:116` (`d09m`). The `m`
  suffix in config names means "owned by firefly2006".
- **`andreasbis`** owner — appears only in `kernel_sources` for `a09*`
  configs (`kkr.yaml:61, 69`) — i.e. a third-party kernel reused by
  both `h` and `m` flows. Not an active submission account, but an
  upstream code source the replacement must keep allowed.
- **Owner-to-env-file mapping** lives in `_load_env_for_owner` at
  `kkr.py:528–548`. Three resolution paths in order:
  1. `--env <path>` override — raises `FileNotFoundError` if the
     given path does not exist (`kkr.py:535–537, 547`).
  2. Programmatic `env_map[owner]` lookup (`kkr.py:538–539`).
  3. Fallback to `Path(".") / f".env.{owner}"` (`kkr.py:541`).
  Calling `load_dotenv(path, override=True)` (`kkr.py:543`) overrides
  any in-process Kaggle credentials, so back-to-back pushes under
  different owners work without an external account switcher.
- Selector aliases by suffix (`h` / `m`) are convention, not enforced
  by code. The replacement must either (a) preserve the convention and
  document it, or (b) introduce an explicit `owner:` field per config
  and migrate the YAML in place.

## 4. Side effects

- Kaggle kernel push: `_get_kaggle_api()` at `kkr.py:587` returns an
  authenticated `KaggleApi`; subsequent `kernels_push` / `kernels_status`
  / `kernels_output` invocations write to Kaggle servers under the
  owner currently loaded into the in-process credentials.
- Kaggle competition submit: chained off a successful push (see
  `_submit_existing` at `kkr.py:1733`); writes a competition submission
  under the current owner.
- Filesystem writes inside `--run-root` (default `.kkr/`):
  - `manifest.json` per run (`kkr.py:824–828`).
  - `registry/<run_id>.json` per run (`kkr.py:816, 838`).
  - Cached kernel outputs in `extracted_dirs` (`kkr.py:178`).
- `load_dotenv(..., override=True)` (`kkr.py:543`) mutates
  `os.environ` for the lifetime of the process. Long-running
  orchestrators must isolate.

## 5. State files / registries / dotenv overrides

- `.kkr/<run_dir>/manifest.json` — per-run `RunManifest`
  (`kkr.py:201–222`).
- `.kkr/registry/<run_id>.json` — `RegistryEntry`
  (`kkr.py:230–250`); driven by `_save_registry` (`kkr.py:838`) and
  `_list_registry_entries` (`kkr.py:848`).
- `.env`, `.env.{owner}`, or `<env_override>` — read by
  `_load_env_for_owner` (`kkr.py:528–548`). Treat `.env.{owner}` as a
  load-bearing schema, not an ad-hoc convention.
- File names: `DEFAULT_PUSH_FILENAME`, `DEFAULT_WATCH_FILENAME`,
  `DEFAULT_FETCH_FILENAME`, `DEFAULT_SUBMIT_FILENAME`
  (`kkr.py:43–46`) — used as legacy artifact filenames inside a run
  directory.

## 6. Config dimensions

Flag / env / YAML knobs that change behaviour. Defaults in parens.

- CLI (common, `kkr.py:2158–2173`):
  - `--yaml` (`kkr.yaml`), `--run-root` (DEFAULT_RUN_ROOT),
    `--env` (none → `.env.{owner}`), `--json` (false), `--dry-run`
    (false), `--quiet` (false), `-v/--verbose` (count).
- CLI (selector, `kkr.py:2174–2187`): `name` (positional),
  `--run`, `--kernel`, `--version`.
- CLI (push, `kkr.py:2197–2215`): `--stub`, `--wait`,
  `--interval` (DEFAULT_INTERVAL), `--timeout` (DEFAULT_TIMEOUT).
- CLI (submit, `kkr.py:2221–2243`): `--stub`, `--msg`, `--wait`
  (BooleanOptional, default False), `--interval`, `--timeout`.
- CLI (watch, `kkr.py:2249–2266`): `--wait` (BooleanOptional,
  default True), `--interval`, `--timeout`.
- CLI (list, `kkr.py:2282–2289`): `--limit` (50), `--refresh`.
- YAML knobs (`kkr.yaml:1–47`): `id`, `title`, `code_file`,
  `language`, `kernel_type`, `is_private`, `enable_gpu`,
  `enable_tpu`, `enable_internet`, `competition`, `submit_file`,
  `submit_type`, `competition_sources`, `dataset_sources`,
  `kernel_sources`, `model_sources`, `docker_image`,
  `machine_shape`, `_msg`, `_stub`, `_exts`, `_refs`,
  `_drop_tags`.

## 7. Features to preserve

- Multi-Kaggle-account / owner / env mapping (see §3). Why: the
  legacy YAML encodes 4 active configs per session (a/b/c/d in `h` and
  `m` variants), each routed to a different owner; the replacement
  cannot collapse this without breaking the established submission
  workflow. Evidence: `kkr.yaml:57–121`.
- `--dry-run` on every subcommand. Why: dry-run is the canonical
  smoke-test path; `_create_new_run` short-circuits at `kkr.py:1529`
  when `args.dry_run` is set.
- Stable JSON emission via `--json`. Why: downstream automation
  (`_emit_ok` at `kkr.py:332`) consumes shape; rename or reshape
  breaks any consumer.
- Local registry (`.kkr/registry/`). Why: replays, audit, and
  cross-day status queries depend on it; the platform should mirror
  this into the DB but keep a local copy for offline operation.
- Watch / status / fetch lifecycle. Why: Kaggle kernel runs are
  asynchronous and a successful submit can take minutes — polling
  must survive process restarts.
- `_deep_merge` semantics for `_base` + per-config (`kkr.py:421`).
  Why: list-union behaviour on `kernel_sources` / `model_sources`
  is relied on by every per-config block in `kkr.yaml`.

## 8. Features to deprecate

- The two `kaggle==1.8.3` patches flagged in `kkr.yaml:31, 38`. Why:
  the platform can pin a known-good `kaggle` version (or use the
  Kaggle Python API directly) and remove monkey-patching. Verify
  newer `kaggle` accepts `owner/model-slug` and `docker_image`
  fields natively before dropping.
- The `_exts` mechanism for run-extensions
  (`kkr.yaml:47` listing `kkr_simple`, `kkr_report`, `kkr_pycoll`;
  invoked at `kkr.py:122`). Why: bespoke per-run report shims have
  been superseded by the platform's `agent_reviews` + OTEL telemetry
  in M6; if any extension still has unique value, lift it into the
  platform as a tool, not a YAML knob.

## 9. Questions for `requirements-skeptic`

- Does the replacement expose an explicit `owner:` field, or does it
  inherit the `id: owner/slug` convention? Evidence: `kkr.yaml:7`,
  `kkr.py:466`.
- How does the replacement resolve credentials when multiple owners
  are active in one orchestration run? Evidence: `kkr.py:528–548`.
- Is `.env.{owner}` part of the public contract, or an implementation
  detail? Evidence: `kkr.py:541`.
- What happens to the `andreasbis/aimo-3-utils` kernel-source
  dependency if the replacement no longer supports cross-owner
  `kernel_sources`? Evidence: `kkr.yaml:61, 69`.
- Does the replacement preserve `--dry-run` semantics on every
  subcommand, or only on push/submit? Evidence: `kkr.py:1529, 1749`.

## 10. Parity tests

- `test_kkr_parity_push_dry_run` — invoke `push a09h --dry-run`,
  assert the plan JSON contains `owner=harrysun2006`,
  `slug=gpt-oss-120b-a09h`, and resolves `.env.harrysun2006` (or
  documented replacement). Fixture: a minimal `kkr.yaml`.
- `test_kkr_parity_owner_switch` — push `a09h` then `a09m`, assert
  the in-process credentials switched and that the second run did
  not inherit the first run's owner. Fixture: two-owner `kkr.yaml`.
- `test_kkr_parity_registry_roundtrip` — push, list, watch, fetch,
  assert one `RegistryEntry` per push with stable `run_id`.
- `test_kkr_parity_submit_message_cap` — supply a 600-char `_msg`,
  assert the replacement rejects with the same 500-char limit
  (`kkr.py:558`).
- `test_kkr_parity_dry_run_no_api_call` — patch the Kaggle API to
  raise on any call, assert dry-run completes without invoking it.
