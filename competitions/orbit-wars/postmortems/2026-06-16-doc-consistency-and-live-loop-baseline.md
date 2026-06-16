# Doc consistency + live-loop baseline (OW-P0-DOCS-LIVE-001)

> 2026-06-16. Branch `worktree-orbit-docs-live-baseline`. Normalizes Orbit Wars docs before
> strong-tier foundation/model work. **Docs-only — no agent/ops code changed.**

## Facts reconciled
- **2p/4p ladder relevance** (check 1): already correct post-#114 — `tracking.md`/`tasks.md`/`EPISODES.md` #3 state the ladder is ~half 4p and **4p updates μ**; `arena/eval_4p.py` is the 4p gate (T17); every candidate gated in BOTH 2p and 4p. No change needed.
- **flyingfox identity** (check 2): `flyingfox` = harrysun2006's profile/display name = **US** (confirmed, PR #114/#116). Re-tagged the one stale label in `tracking.md` (the "flyingfox's 205-episode history" format-correction bullet now says "our own kuni05 submission, sub 53582503"). Full map: `live/player_identity_map.md` (added in #116).
- **latest-2 slots** (check 3, last-known — read-only Kaggle refresh NOT run, see blocker): harry [`v4_scheduler.tar.gz` _pending_, `submission_kuni.tar.gz` ~1079.7], may [`v3_forecast.py` _pending_, `v3_2_coarr.py` ~640.7]. Documented in `submissions.md` / `tracking.md` orbit5 cycle.
- **early-stop policy** (check 4): added an explicit **Early-stop / promotion policy** section to `tasks.md` referencing the 10/20-episode gates toward **μ ≥ 1200** (immediate fix_required on hard bugs; weak after 10 if flat/down; release slot after 20 if not climbing toward 1200 / below the kuni05 ~1080 anchor). Noted `configs/early_stop_policy.yaml` is referenced by the task pack but **not yet present** (`unknown`); `ops/track_submission.py` currently emits a keep/replace recommendation.
- **live-loop commands** (check 5): `ops/README.md` updated — added `episode_discover.py` + `track_submission.py` to the Modules table and a **recommended daily commands** block, and corrected the stale "automatic discovery not exposed" note (per-submission discovery via `EpisodeService/ListEpisodes` IS available and is how the 4p-format + matchmaking findings were made).
- **phase/task backlog** (check 6): added a **Strong-tier breakthrough phase backlog** section to `tasks.md` mapping prompts 00–07 (research ✅ / docs-baseline / FlightOracle / BattlefieldState+ledger / replay dataset / snorlax training / hybrid integration / ladder loop) with the hybrid model-centric + deterministic-execution architecture.

## Live-loop readiness
`ops/` is intact and unchanged (`live_loop.py --once`, `account_manager.py --status`, `episode_discover.py`, `track_submission.py`). Daily read-only tracking commands are now documented in `ops/README.md`.

## ⚠ VALIDATION BLOCKER (acceptance criterion: "documented")
The **Bash execution environment was non-functional for this entire session** — every shell command (including a bare `echo`) returned exit 1 with no output, across a session restart; the two PreToolUse hooks (`guard_tool.py`, `format_gate.py`) were verified benign, so the cause is the wedged persistent shell (likely after a `dangerouslyDisableSandbox` decline during earlier worktree churn). Consequence:
- The **Validation block was NOT run**: `git status --short`, `git diff --stat/--name-status`, `python -m py_compile competitions/orbit-wars/ops/*.py`, `python -m py_compile competitions/orbit-wars/agent/main.py`.
- The optional **read-only Kaggle refresh** (`account_manager.py --status`, `kaggle competitions submissions`) was NOT run — slot state above is last-known (2026-06-16), not freshly refreshed.
- These edits are **docs-only** (no `.py` touched), so `py_compile` of `ops/`/`agent/main.py` is **unaffected** by this task (those files are unchanged + previously compiled/ran).
- Changes are **uncommitted** (git unavailable) and live in worktree `worktree-orbit-docs-live-baseline`.
**To verify + commit when the shell is restored** (full CLI relaunch): run the Validation block above (expect a docs-only diff, py_compile clean), then commit + PR.

## ✅ RESOLVED (shell restored via host reboot, 2026-06-16)
The command channel came back after a full host reboot (a CLI relaunch alone did not fix it). Re-ran everything:
- **Validation block PASS:** `git status --short` shows only the 4 doc files; `git diff --stat` = docs-only (40 insertions); `py_compile ops/*.py` → OK; `py_compile agent/main.py` → OK.
- **Read-only Kaggle refresh DONE:** orbit5 submissions are now **COMPLETE/scored** — harry [`v4_scheduler` **703.9**, `submission_kuni` **1069.9**], may [`v3_forecast` **678.1**, `v3_2_coarr` **644.4**]. v4/v3 settled ≈ predicted (~700/~686), both well short of μ≥1200; kuni05 (~1070) remains our best. `tracking.md` slot line updated to these current values.
- Committed (docs-only). Prompt 01 acceptance: **PASS**.
