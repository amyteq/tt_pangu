# Design archaeology — `tools/legacy/kkr.py` + `tools/legacy/kkr.yaml`

Produced by the [`design-archaeology`](../../.claude/skills/design-archaeology/SKILL.md) skill in M9.3-T003. Read-only on the legacy tree. Status: report only — no migration code may begin until `§8` is acknowledged by a human.

## 1. Workflows supported (subcommands / entry points)

Six argparse subcommands, each registered in `_build_parser`:

- `push` — build a notebook and push it as a Kaggle kernel version. `tools/legacy/kkr.py:2194-2215`
- `submit` — create+push a new version then competition-submit, or submit an already-selected existing version. `tools/legacy/kkr.py:2216-2243`
- `watch` — poll a selected run until it reaches a terminal status. `tools/legacy/kkr.py:2244-2266`
- `fetch` — download source/output artifacts for a selected run. `tools/legacy/kkr.py:2267-2271`
- `status` — query remote kernel status for a selected run and refresh the local registry. `tools/legacy/kkr.py:2272-2276`
- `list` — list tracked runs from the local registry, optionally refreshing remote status first. `tools/legacy/kkr.py:2277-2289`

`main()` entry: `tools/legacy/kkr.py:2293`. Run-root default: `.kkr/`. `tools/legacy/kkr.py:30`.

## 2. Hidden assumptions (env, paths, accounts, side effects)

- A `_base` block in `kkr.yaml` is required; missing it raises. `tools/legacy/kkr.py:491-492`
- An `_envs` mapping in `kkr.yaml` (Kaggle owner → dotenv path) is *consumed* even though the shipped `kkr.yaml` does not define it; the fallback is `.env.{owner}` in the cwd. `tools/legacy/kkr.py:495-502, 538-541`
- `--env` overrides per-invocation; `tools/legacy/kkr.py:2165, 528-548`. Missing override-target file is a hard error; missing fallback file is silently OK.
- All runs are stamped with `owner`/`slug` parsed from the kernel `id`. `tools/legacy/kkr.py:520`
- `_msg` template substitutes `{ts}`; result is hard-capped at 500 chars. `tools/legacy/kkr.py:551-559`
- Submission message length 500 is silently enforced; longer messages raise pre-call. `tools/legacy/kkr.py:558-559`
- `--dry-run` short-circuits all Kaggle calls; default is **off** (a real call will run). `tools/legacy/kkr.py:2168-2169`
- Kernel `id` must be `owner/slug`; the slug parser asserts this shape. `tools/legacy/kkr.py:520`

## 3. User personas / accounts / owners

**Two owners ship in the repo's `kkr.yaml`:** `harrysun2006` and `firefly2006`. `tools/legacy/kkr.yaml:7, 58, 66, 77, 83, 90, 98, 108, 116`.

The multi-owner / multi-account mechanism is the duplicated kernel-id pattern: blocks ending `h` (`a09h`, `b09h`, `c09h`, `d09h`) are owned by `harrysun2006`; blocks ending `m` (`a09m`, `b09m`, `c09m`, `d09m`) are owned by `firefly2006`. The same notebook (`b09.ipynb` for b/c blocks; `d09.ipynb` for d blocks; `a09{h,m}.ipynb` for a blocks) is pushed under both owners in parallel — **the practical effect is doubling daily Kaggle quota by running each experiment under two accounts**. `tools/legacy/kkr.yaml:54-121`.

Per-owner env resolution chain — exactly this order, with no further fallback:

1. `--env <path>` (cli override, applies to whichever owner is selected). `tools/legacy/kkr.py:534-537`
2. `_envs[<owner>]` from `kkr.yaml` (mapping yaml key, currently *not* populated in the shipped yaml). `tools/legacy/kkr.py:495-502, 538-539`
3. `./.env.{owner}` in cwd (the de-facto multi-account convention — e.g. `.env.harrysun2006`, `.env.firefly2006`). `tools/legacy/kkr.py:540-541`

Run-time owner is selected by the kernel-config block named on the CLI (`kkr.py push b09m` selects `firefly2006`). There is **no** `--owner` flag — owner is implied by the named config block.

## 4. State files / registries / caches

- `.kkr/` — default run-root for everything (default value at module level). `tools/legacy/kkr.py:30`
- `.kkr/registry/` — local registry of tracked runs (`RegistryEntry` dataclass). `tools/legacy/kkr.py:31, 813, 226-251`
- `.kkr/<run_id>/` — per-run dir with manifest, notebook, kernel metadata, push/submit results (`RunManifest` dataclass). `tools/legacy/kkr.py:201-222`
- `.kkr/<run_id>/<run_dir>` — workspace for the rendered notebook + kernel metadata. `tools/legacy/kkr.py:206`
- `.env.{owner}` files in cwd — owner-specific dotenvs read by `_load_env_for_owner`. `tools/legacy/kkr.py:541`

The `--run` selector binds tasks (watch / fetch / status / list / submit) to an existing `RUN_ID` under `.kkr/`. `tools/legacy/kkr.py:2180`.

## 5. Config dimensions (with example values found in tree)

YAML keys consumed (selected):

| Key | Example | Cite |
|---|---|---|
| `competition` | `ai-mathematical-olympiad-progress-prize-3` | `kkr.yaml:3` |
| `submit_file` | `submission.parquet` | `kkr.yaml:4` |
| `submit_type` | `notebook` (alt: `local`) | `kkr.yaml:5` |
| `id` (owner/slug) | `harrysun2006/gpt-oss-120b-b09h` / `firefly2006/gpt-oss-120b-b09m` | `kkr.yaml:77, 83` |
| `title` | `gpt-oss-120b b09h` | `kkr.yaml:78` |
| `code_file` | `b09.ipynb` | `kkr.yaml:79` |
| `language` / `kernel_type` | `python` / `notebook` | `kkr.yaml:10-11` |
| `is_private` / `enable_gpu` / `enable_tpu` / `enable_internet` | `true` / `true` / `false` / `false` | `kkr.yaml:12-15` |
| `competition_sources` | `[ai-mathematical-olympiad-progress-prize-3]` | `kkr.yaml:22-23` |
| `dataset_sources` | `[harrysun2006/aimo-p3-hard]` | `kkr.yaml:24-25` |
| `kernel_sources` | `[harrysun2006/aimo-3-utils]` / `[andreasbis/aimo-3-utils]` | `kkr.yaml:26-30, 61, 68` |
| `model_sources` | `[danielhanchen/gpt-oss-120b/Transformers/default/1]` | `kkr.yaml:32-33` |
| `docker_image` | `gcr.io/kaggle-private-byod/python@sha256:58f63...` | `kkr.yaml:39` |
| `machine_shape` | `NvidiaH100` | `kkr.yaml:40` |
| `_msg` | `kkr_auto_submit@{ts}` | `kkr.yaml:43` |
| `_stub` | `test('reference.csv')` / `test('p10.csv')` / `pass` | `kkr.yaml:46, 80, 95` |
| `_exts` | `['kkr_simple', 'kkr_report', 'kkr_pycoll']` | `kkr.yaml:47` |
| `_refs` | `[]` | `kkr.yaml:48` |
| `_envs` | (consumed but absent in shipped yaml) | `kkr.py:495` |

CLI flags shared via the `common` parser: `--env`, `--dry-run`, plus quiet/verbose. `kkr.py:2158-2172`. Selector flags: `--run`, `--kernel`, `--version`. `kkr.py:2174-2186`. Per-subcommand: `--stub` (push, submit), `--msg` (submit, max 500 chars), `--wait` (push/submit/watch), `--interval` (default DEFAULT_INTERVAL), `--timeout` (default DEFAULT_TIMEOUT, `0` = no timeout). `kkr.py:2198-2266`.

## 6. Side effects (network, FS, external APIs)

Network (Kaggle Python SDK, lazy import at `_get_kaggle_api` `kkr.py:587-593`):

- `api.kernels_push(...)` — kernel version push (write). Called from push/submit paths. `kkr.py:_create_new_run, kkr.py:1511`
- `api.kernels_status(<kernel_ref>)` — poll kernel status (read). `kkr.py:1279, 1340, 1394`
- `api.kernels_output(...)` — fetch output artifacts (read). Used by `fetch`.
- `api.competition_submit(...)` — local-file competition submission (write). `kkr.py:1225`
- `api.competition_submit_code(...)` — notebook-code competition submission (write). `kkr.py:1187`

FS writes:

- `.kkr/**` run/registry tree. `kkr.py:30, 813`
- `dotenv` mutates the process env via `load_dotenv(path, override=True)`. `kkr.py:542-544`

No subprocess invocations; no signal handlers. JSON is emitted to stdout via `_emit_ok` (`kkr.py:332`).

## 7. Preserve / change / drop matrix

| Behaviour | Preserve / Change / Drop | Rationale |
|---|---|---|
| Multi-owner kernel pairs (h-suffix / m-suffix per experiment) **— multi-account quota pool** | **Preserve (subject to §8 Q1)** | Doubles daily Kaggle quota; central reason `kkr.yaml` lists `harrysun2006` and `firefly2006` side by side. Dropping silently was the original M7–M9 archaeology miss this skill exists to prevent. |
| `_load_env_for_owner` three-step resolution (`--env` → `_envs[owner]` → `.env.{owner}`) | Preserve (port to KCA env model) | Same mechanism is the lowest-friction way to keep multi-account quota; aligns with the dev-phase secret policy (`.env.<owner>` reads are explicitly carved out). |
| `.kkr/registry/` local run registry | **Change** — replace with KCA `runs` Supabase table | KCA already has a `runs` table from M2/M3 (`supabase/migrations/0001_init.sql`, `0003_*.sql`); duplicating the local registry doubles state. |
| `--dry-run` default-off | Preserve | Matches existing kca behaviour; users expect explicit dry-run opt-in. |
| `--msg` 500-char hard cap | Preserve | Mirrors Kaggle's own limit; failing pre-call is better than mid-call. |
| Lazy `kaggle` SDK import via `_get_kaggle_api` | Preserve | Keeps the agent runnable in dry-run / CI without the SDK installed. |
| `competition_submit_code` vs `competition_submit` branching | Preserve | The notebook-submission path (used by M10 Petals to the Metal) and the file-submission path (used by M9 Spaceship Titanic) are different Kaggle endpoints; KCA already exercises both. |
| Top-level argparse layout (push / submit / watch / fetch / status / list) | **Change** — fold into existing `kca kaggle` subtree | KCA already has `kca kaggle list/submit/push/fetch`; adding parallel `kca kkr ...` would split mental load. |
| YAML key naming (`_base`, `_envs`, `_stub`, `_exts`, `_refs`, `_msg`) | **Drop** (do not adopt the `_<key>` underscore convention) | KCA uses plain keys (`base:`, `extensions:` etc.); the underscore was a kkr-local choice and porting it would be cargo. |
| `RunManifest` / `RegistryEntry` dataclasses | Change — replace with `runs` row + workspace dir | Same reason as the local registry: KCA already has these. |

## 8. Open design questions for human

1. **Multi-account quota pooling.** Should KCA M10+ re-introduce the `harrysun2006` / `firefly2006` paired-kernel pattern as a *first-class* feature (e.g. `kca kaggle push --owner-set h,m`), or treat it as a manual two-call workflow the user orchestrates? The yaml-level pairing is the design that was lost in the M7–M9 take-over; we should not silently re-drop it.
2. **Where does the owner→env mapping live in KCA?** Options: (a) port `_envs:` into a new KCA config file under `~/.config/kca/owners.yaml`, (b) keep the `.env.{owner}` convention but document it, (c) extend `kca kaggle` with `--profile <owner>` that loads `.env.<owner>` automatically. Each has a different secret-leak blast radius.
3. **Local registry vs Supabase `runs` table.** Confirm we are replacing `.kkr/registry/` with the existing `runs` table and not running both in parallel. If both, what is the source of truth?
4. **`_stub` extensions.** The legacy `_exts: ['kkr_simple', 'kkr_report', 'kkr_pycoll']` injects code into the rendered notebook. KCA does not have an equivalent. Do we port this, replace with KCA skills, or drop?
5. **`docker_image` + `machine_shape`.** `kkr.yaml:39-40` pins an exact Kaggle BYOD docker SHA and `NvidiaH100`. KCA's M10 (Petals to the Metal) is TPU. Do we generalise the field to `{cpu, gpu, tpu, byod-docker}` profiles, or keep it free-form?

## 9. Behavior parity test sketch (test names, no code)

- `test_kkr_push_dryrun_emits_manifest_and_no_kaggle_call` — proves dry-run never imports `kaggle.api.*` or writes to remote.
- `test_kkr_submit_existing_routes_to_competition_submit_for_local_submit_type` — proves the file-submission branch.
- `test_kkr_submit_routes_to_competition_submit_code_for_notebook_submit_type` — proves the notebook-submission branch.
- `test_kkr_multi_owner_env_resolution_picks_envs_then_dotfile_fallback` — proves the three-step env resolution for both owners with and without `--env`.
- `test_kkr_paired_push_h_and_m_produces_two_distinct_run_ids` — proves the multi-account quota-pool pattern still works after migration (or is explicitly dropped per §8 Q1).
- `test_kkr_msg_over_500_chars_raises_before_remote_call` — proves the 500-char gate.
- `test_kkr_watch_polls_until_terminal_status_and_records_pb_score` — proves the `watch` loop semantics.

## 10. Evidence — file:line citations for every claim

- `tools/legacy/kkr.py:30` — `DEFAULT_RUN_ROOT = Path(".kkr")`
- `tools/legacy/kkr.py:31` — `DEFAULT_REGISTRY_DIRNAME = "registry"`
- `tools/legacy/kkr.py:201-222` — `RunManifest` dataclass
- `tools/legacy/kkr.py:226-251` — `RegistryEntry` dataclass
- `tools/legacy/kkr.py:332` — `_emit_ok` JSON stdout
- `tools/legacy/kkr.py:489-521` — `_merged_config` (`_base` required; `_envs` consumed)
- `tools/legacy/kkr.py:520` — owner/slug parse from `id`
- `tools/legacy/kkr.py:528-548` — `_load_env_for_owner` (3-step resolution)
- `tools/legacy/kkr.py:551-559` — `_format_submit_message` (500-char cap)
- `tools/legacy/kkr.py:587-593` — `_get_kaggle_api` lazy import
- `tools/legacy/kkr.py:813` — registry path helper
- `tools/legacy/kkr.py:1187` — `api.competition_submit_code(...)`
- `tools/legacy/kkr.py:1225` — `api.competition_submit(...)`
- `tools/legacy/kkr.py:1279, 1340, 1394` — `api.kernels_status(...)`
- `tools/legacy/kkr.py:1511` — `_create_new_run`
- `tools/legacy/kkr.py:2158-2172` — `common` argparse parent (`--env`, `--dry-run`, quiet/verbose)
- `tools/legacy/kkr.py:2174-2186` — selector parent (`--run`, `--kernel`, `--version`)
- `tools/legacy/kkr.py:2193-2289` — six subparsers (push, submit, watch, fetch, status, list)
- `tools/legacy/kkr.py:2293` — `main`
- `tools/legacy/kkr.yaml:3-5` — competition / submit_file / submit_type
- `tools/legacy/kkr.yaml:7` — first appearance of owner `harrysun2006` in `_base.id`
- `tools/legacy/kkr.yaml:39-40` — `docker_image` + `machine_shape`
- `tools/legacy/kkr.yaml:43` — `_msg`
- `tools/legacy/kkr.yaml:46-48` — `_stub`, `_exts`, `_refs`
- `tools/legacy/kkr.yaml:57-71` — `a09h` / `a09m` (harrysun2006 / firefly2006 pair)
- `tools/legacy/kkr.yaml:76-86` — `b09h` / `b09m` pair
- `tools/legacy/kkr.yaml:89-104` — `c09h` / `c09m` pair
- `tools/legacy/kkr.yaml:107-121` — `d09h` / `d09m` pair
