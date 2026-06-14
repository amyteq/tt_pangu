# Postmortem: context consolidation (nemo, 2026-06-14)

> KCT-002: consolidated the long issue-#86 tracking context into English canonical docs under
> `competitions/nvidia-nemotron/`. Builds on KCT-001 (PR #100). Chinese originals preserved as `_zh` sidecars.
> The original KCT-001 postmortem is preserved (English) in [`2026-06-14-kct-001-initial-consolidation.md`](./2026-06-14-kct-001-initial-consolidation.md).

## Sources read
- GitHub issue **#86** (body + 5 comments; Chinese strategy/tracking hub) — primary.
- `work/00.nemo.md` (ChatGPT competition analysis, zh); `work/00.nemotron_3_versions.zip` (3 ChatGPT scripts, names only).
- `worklogs/nemo.md`, `worklogs/nemo2.md`; `experiments/kernel/README.md`; PRs #90/#94/#95.
- `experiments/synth/nemo_synth_gen.py`, `experiments/merge/svd_merge.py`, `kernels/*/kernel-metadata.json` (also indexed in `references.md`).

## Key facts recovered
- Submit rank≤32 LoRA adapter (Nemotron-3-Nano-30B-A3B, Mamba+MoE); greedy `max_tokens=7680, temp=0`;
  extract `\boxed{}` (exact or numeric 1e-2); metric accuracy; 9 reasoning categories; train ~9500; hidden test.
- Deadline 2026-06-15 23:59 UTC; 5 submissions/team/day; top ~0.89; base ~0.47.
- LB progression: v5 0.61 → v7 0.65 → ctx4k 0.67 → v10 0.59 → **v14 replay 0.85 (best)** → T7 merge 0.82 → v15 synth 0.84.

## Decisions recovered
- D1–D9 all confirmed 2026-06-12 (see `tracking.md` Table 1). Merge scope = own adapters only (D3); #85 tooling post-comp (D6); seq8192 + ≤8h guard (D9).
- Closing recommendation (comment 4): **hold 0.85**.

## Open blockers
- 0.85 appears to be the ceiling with current levers; beating it likely needs undisclosed top-tier tricks.

## Active tasks recovered
- Hold 0.85 to deadline; optional half-dose cryptarithm-only synth (user-decides).

## Known submissions/results recovered
- See `submissions.md` / `tracking.md` (kernel push + LB table). Private LB `unknown`.

## Bugs recovered
- See `bugs.md` (ctx2k truncation, v6 masking, BatchEncoding fail-fast, eval truncation T13, ptxas, data glob, timeout, cryptarithm single≠total).

## Reusable insights
- Faithful public-recipe replay is the dominant lever; augmentations dilute it; eval harness must mirror the
  official metric; push-time lint + fail-fast preflight. See `insights.md` / `_shared/`.

## Chinese→English translations performed
- Issue #86 Tables 1–3 (D1–D9, T1–T13, References) → `tracking.md` (EN). Comments 2/4 key conclusions → EN in `tracking.md`/`strategy.md`/`insights.md`.
- Interim Chinese KCT-001 docs (README/rules/strategy/tasks/submissions/bugs/references/insights) → rewritten English canonical.

## _zh sidecars created
- `tracking_zh.md` (verbatim issue #86 body, Chinese 3 tables), `notes_zh.md` (zh source pointers + key comment excerpts).

## Uncertain or missing context
- Private LB; exact submission IDs; exact train row count; `test.csv`=first-3-train claim (as reported).
- Read-only Kaggle status **refreshed 2026-06-14** (both accounts via `kaggle competitions submissions`; all submissions `COMPLETE`). Best own real-training = 0.85 (v14); raw account public max = 0.86 (2026-05-15 public-fork); leaderboard top ~0.90. Private LB not released. The Kaggle submissions API exposes no numeric submission ID (date+description is the key).

## Proposed follow-up issues
- "nemo: post-deadline archival" (finalize LB/CV + private LB + final postmortem; status → archived).
- "nemo: port official metric + min-logprob hard-val set (T12)".
