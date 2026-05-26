# requirements-skeptic report for migrating tools/legacy/kkr.py into KCA

Source: tools/legacy/kkr.py @ 6231fd1f54b6, tools/legacy/kkr.yaml @ 0543e71a5aa1
Upstream: docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md

_Produced under the M9.4 Discovery / Debate Gate (M9.4-T005). The agent
body lives in `.claude/agents/requirements-skeptic.md`; this artefact
is a manual execution of that agent's protocol against the proposed
KCA replacement of the legacy `kkr.py` flow._

## hidden_constraints

1. What is the maximum number of distinct Kaggle owners the replacement
   must support concurrently in one orchestration run? — consequence
   if unanswered: the replacement may pick a single-owner credential
   pattern (env vars set once at startup) and silently degrade the
   `harrysun2006` ↔ `firefly2006` dual-account workflow encoded in
   `kkr.yaml:57–121`.
2. Is `.env.{owner}` part of the public KCA contract, or an
   implementation detail the platform reserves the right to change? —
   consequence: if it's public, the KCA installer and onboarding docs
   need a documented `.env.<owner>` convention; if private, the
   platform owes users a migration path and a deprecation window.
3. Are `kaggle==1.8.3` monkey-patches (`kkr.yaml:31, 38`) still
   required against the version the platform pins, or are they
   superseded? — consequence: shipping the replacement without
   testing against the actually-pinned `kaggle` could silently break
   `model_sources` parsing or H100 `docker_image` overrides on first
   real push.
4. What is the maximum submission message length the replacement
   enforces? — consequence: legacy caps at 500 chars
   (`kkr.py:558`); a different cap downstream is a silent contract
   change.
5. Is the local registry (`.kkr/registry/`) the canonical state, or
   is the Supabase DB the canonical state with the local registry
   as a cache? — consequence: ambiguity here causes split-brain
   between offline-developed runs and platform-tracked runs.

## personas_and_accounts

1. The legacy tool encodes `harrysun2006` (`h` suffix) and
   `firefly2006` (`m` suffix) as distinct Kaggle owners and
   `andreasbis` as a kernel-source supplier (`kkr.yaml:7, 58, 66, 77,
   83, 90, 98, 108, 116, 61, 69`). Which of these survive in the
   replacement, with what role? — consequence: a single-owner
   replacement drops 50% of the live submission paths.
2. Does the replacement allow per-experiment owner override at the
   CLI, the way `--env <path>` overrides at `kkr.py:534–537`? —
   consequence: removing per-experiment override forces users to
   relaunch the platform between owner switches.
3. Are there additional Kaggle owners the user runs under not
   present in this committed `kkr.yaml`? — consequence: the
   archaeology may have under-counted because the YAML is committed
   but the actual `.env.*` files are gitignored.
4. Does the platform track which owner a given submission ran under
   in the `submissions` / `runs` table? — consequence: without an
   owner column the leaderboard-attribution audit trail breaks.
5. How does the platform reconcile a user being a GitHub identity, a
   Supabase user, AND a Kaggle owner — possibly with N:N mapping
   per project? — consequence: if the data model assumes 1:1, the
   multi-account case cannot be modelled at all.

## side_effects

1. Does the replacement preserve `--dry-run` on every subcommand, or
   only on push/submit? — consequence: dry-run gaps mean the smoke
   test path can't cover watch/fetch/status without hitting Kaggle.
2. The legacy `_load_env_for_owner` calls `load_dotenv(...,
   override=True)` at `kkr.py:543`, mutating `os.environ` in-process.
   Does the replacement isolate per-job credentials, or share the
   ambient environment? — consequence: shared env means one job can
   read the next job's secrets.
3. What reverses an accidental kernel push? — consequence: if the
   replacement does not surface a "delete-version" path,
   misconfigured pushes accumulate as draft versions Kaggle never
   garbage-collects.
4. What reverses an accidental competition submit? — consequence:
   Kaggle does not allow submission deletion; the platform must
   prevent rather than recover. Is the approval gate sufficient?
5. Where do `extracted_dirs` (`kkr.py:178`) land in the replacement?
   Inside the workspace, or in a platform-managed artifact store? —
   consequence: workspace bloat vs. unclear retention policy.

## edge_cases

1. What happens when a push starts under owner A and a credential
   switch happens mid-watch? — consequence: stale `KAGGLE_USERNAME`
   in the in-process env hits the wrong Kaggle account during
   status polling.
2. What happens if `_msg` formatting produces an empty string after
   trimming? — consequence: legacy raises at `_format_submit_message`
   only on >500 chars (`kkr.py:558`); empty `_msg` silently submits
   with `kkr@{ts}` default.
3. What happens if `kkr.yaml` has overlapping `kernel_sources`
   entries across `_base` and per-config? — consequence:
   `union_list` (`kkr.py:421`) deduplicates by simple equality;
   structured (dict) entries may not deduplicate as expected.
4. What happens during a partial registry write — process killed
   between `_save_manifest` and `_save_registry`? — consequence:
   orphaned manifest with no registry entry will not appear in
   `list`.
5. What happens if two concurrent `push` invocations allocate the
   same run id? — consequence: `_create_new_run` at `kkr.py:1511`
   uses `allocate=not args.dry_run` (`kkr.py:1523`); concurrent
   non-dry-run pushes may collide.

## rollback

1. If the replacement ships and a user wants to fall back to
   `tools/legacy/kkr.py`, is the legacy CLI still expected to work
   against the same `.kkr/registry/` directory? — consequence: if
   the registry schema is changed in flight, both tools see a
   broken registry.
2. Is the migration step idempotent? — consequence: re-running it
   after a partial failure should be safe.
3. Does the replacement write any state that the legacy CLI cannot
   ignore? — consequence: forward-incompatible additions silently
   poison rollback.
4. Is there an "export to legacy YAML" path for emergency rollback?
   — consequence: without it, the only fallback is the last commit
   of `kkr.yaml`, which loses any per-experiment edits made through
   the platform.
5. What is the rollback gate: a CLI command, a feature flag, a
   redeploy, or an out-of-band manual procedure? — consequence:
   ambiguity here means rollback during an incident is slow.

## explicit_unknowns

- Whether the `harrysun2006` / `firefly2006` owners are still active
  Kaggle accounts (cannot be inferred from the committed YAML
  alone — see memory `reference_supabase_db` for unrelated
  authoritative-config patterns).
- Whether `andreasbis/aimo-3-utils` is a permanently public Kaggle
  utility kernel or a moving target.
- Whether the H100 `docker_image` `gcr.io/kaggle-private-byod/...`
  (`kkr.yaml:39`) requires special Kaggle account whitelisting; the
  comment "可以 patch kaggle 1.8.3, 来使用 H100 GPU" hints at it but
  doesn't confirm.
- Whether the replacement is expected to support `submit_type:
  local` (CSV submit) AND `submit_type: notebook` (kernel push)
  through the same code path, or split per ADR-0009 / M10.
- Whether the platform's `kca kaggle push` (M10) is intended to
  *replace* `kkr.py push` or to *co-exist* with it during
  transition.
