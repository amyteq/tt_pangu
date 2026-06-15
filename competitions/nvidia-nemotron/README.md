# NVIDIA Nemotron Model Reasoning Challenge (nemo)

> Canonical language: **English**. Original Chinese tracking material preserved in `tracking_zh.md` /
> `notes_zh.md` and in GitHub issue #86. Aliases: `nemo`, `nemotron`.
> Kaggle slug: `nvidia-nemotron-model-reasoning-challenge`.

## Status snapshot
- status: **active** (deadline **2026-06-15 23:59 UTC**, imminent)
- phase: submission (closing)
- current objective: **hold the best score (0.86, `nemo-merge-soup`) to close**
- best known local/CV: per-kernel held-out only (no single canonical CV); see `submissions.md`
- best known LB/public: **0.86 own real-training** (`nemo-merge-soup` = SVD soup of v14+c1+b1); top **~0.90**, base ~0.47 (refreshed 2026-06-15)
- current blocker: none — the 0.85 ceiling was broken by a model-soup of comparable+complementary
  adapters (v14 0.85 + c1 0.85 + b1 0.85 on different data → **soup 0.86**); earlier strong+weak
  merge (T7 0.82) and high-dose synth (v15 0.84) had regressed
- next task: hold 0.86 to close (deadline 2026-06-15); post-comp: T12 local metric, KCA-core YAML (#85)

## Key links
- rules: ./rules.md
- strategy: ./strategy.md · zh: ./strategy_zh.md
- tasks: ./tasks.md
- tracking (issue #86 tables, EN): ./tracking.md · zh: ./tracking_zh.md
- submissions: ./submissions.md
- bugs: ./bugs.md
- references: ./references.md
- insights: ./insights.md
- kernel config (single source of truth): ./kca-nemo.yaml
- kernels (flat percent-`.py` sources): ./kernels/ · shared modules: ./lib/
- postmortem: ./postmortems/2026-06-14-context-consolidation.md
- historical hub: GitHub issue #86 (kept open for history; do not use for new status)

## Kernel config & push workflow
All kernel variations for this competition (both accounts) live in **`./kca-nemo.yaml`**
(modelled on `tools/legacy/kkr.yaml`): a `_base` section holds shared fields, each named
section overrides only what differs (`id` carries the account: `harrysun2006`=harry,
`firefly2006`=may). **`kernel-metadata.json` is no longer source-controlled** — it is
generated on the fly at push time. Sources are flat: `kernels/<name>.py` (percent format),
shared dev modules in `lib/` (embedded into the kernels at assemble time).

```sh
# 1) materialise a push dir (metadata.json + built .ipynb) for one section
python tools/kca/yaml_meta.py build competitions/nvidia-nemotron/kca-nemo.yaml v14 \
    --src-dir competitions/nvidia-nemotron/kernels --out "$TMPDIR/kca-build/v14"
# 2) push (auto-watch off for long runs)
python tools/kca/kca.py kaggle push --kernel-dir "$TMPDIR/kca-build/v14" --no-watch
# 3) on COMPLETE, submit from Kaggle storage
python tools/kca/kca.py kaggle submit -c nvidia-nemotron-model-reasoning-challenge \
    --kernel harrysun2006/nemo-replay-v14 --version <v> --file submission.zip --message "..."
```

## Scheduling convention
- **Long-running training kernels** (`baseline`, `v10`, `v14`, `v15`, `b*`, `c*` — ~5–8h):
  schedule **~22:00–24:00 AEST** so they run overnight; retrieve + analyze results next
  morning, then loop on the next direction. Marked `schedule: overnight` in `kca-nemo.yaml`.
- **Short kernels** (`merge_t7` CPU passthrough, `validate_kernel`): run in **daytime** so a
  human + AI can watch and react closely. Marked `schedule: daytime`.
- Each training kernel carries a ≤8h wall-clock guard (B7) so an overnight run always
  saves + zips before the Kaggle session limit.

## Current top 3 priorities
1. Hold the **0.86** (`nemo-merge-soup`) entry through the 2026-06-15 deadline.
2. Post-competition: localize the official metric + min-logprob hard-validation set (T12).
3. Post-competition: elevate the `kca-<slug>.yaml` + on-the-fly-metadata + flat-layout + scheduling pattern into KCA core (#85).

## Latest update
- date: 2026-06-15
- source: PRs #90/#94/#95/#106/#107; final-sprint kernels b1/b2/c1/c2 + soup
- summary: final-sprint scores — b1 0.85, b2 0.84, c1 0.85, c2 0.83 (none beat v14's 0.85), but the
  **v14+c1+b1 SVD model-soup reached 0.86 — new best, own real-training** (+0.01). The 0.85 ceiling fell
  to a soup of *comparable + complementary* adapters (the §9b-H condition T7's strong+weak merge lacked).
