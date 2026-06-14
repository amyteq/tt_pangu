# Postmortem: initial context consolidation (nemo, KCT-001, 2026-06-14)

> Initial **KCT-001** consolidation snapshot, rebuilt from repo notes. English translation of the original
> Chinese KCT-001 postmortem, **preserved here per PR #102 review** (it was superseded in place by the
> KCT-002 consolidation). The current/superseding English consolidation is
> [`2026-06-14-context-consolidation.md`](./2026-06-14-context-consolidation.md).

## Sources read
- `experiments/kernel/README.md` (recipe, gotchas, score progression)
- `worklogs/nemo.md`, `worklogs/nemo2.md` (Chinese strategy hub; 2026-06-12 snapshot + D1–D7)
- `kernels/*/kernel-metadata.json`, `experiments/synth/nemo_synth_gen.py`, `experiments/merge/svd_merge.py`
- PR #90 / #94 / #95 (merge descriptions)

## Key facts recovered
- Format: rank≤32 LoRA adapter (Nemotron-3-Nano-30B-A3B, Mamba+MoE); greedy `max_tokens=7680, temp=0`;
  extract `\boxed{}` (exact or numeric 1e-2); metric accuracy; 9 reasoning categories; train ~9500; hidden test;
  5/team/day; deadline 2026-06-15 23:59 UTC.
- LB progression: base ~0.47 → v5 0.61 → v7 0.65 (best before 06-12) → v14 replay ~0.85 (per PR description); top ~0.89.
- Dual account: harrysun2006 / firefly2006 (B direction in parallel).

## Decisions recovered
- D1 B-direction submit auth; D2 v11 self-distillation GPU budget; D3 SVD merge own-adapters-only;
  D4 Unsloth priority; D5 external GPU (#83); D6 #85 YAML/user-pool post-competition; D7 inline update mechanism.
  (see `worklogs/nemo2.md` Table 1)

## Open blockers
- cryptarithm category accuracy low (bottleneck; forum 0.86→0.89 lever).
- deadline imminent (06-15); limited daily quota.

## Active tasks recovered
- v15 (cryptarithm-weighted synth) LB recovery; use full dual-account quota before the deadline;
  t7 SVD merge comparison (optional).

## Known submissions/results recovered
- see `submissions.md` (identity 0.47 / v5 0.61 / v7 0.65 with evidence; v10/v14/v15/t7 partial LB to backfill).

## Bugs recovered
- see `bugs.md` (ptxas-blackwell, data glob, BatchEncoding `.shape`, prompt+padding loss, F821/`.shape` preflight, cryptarithm weak).

## Reusable insights
- response-only masking is the key to CoT SFT; precompute CoT intermediate values; push-time lint + single-example preflight
  (see `insights.md`, `_shared/`).

## Uncertain or missing context
- exact public/private LB for v14/v15/t7 (v14 ~0.85 from PR description at KCT-001 time; v15 was running).
- exact train row count; nemo tracking issue number (not verified online during KCT-001 — later confirmed as #86 in KCT-002).

## Proposed follow-up issues
- "nemo post-deadline archival": backfill all CV/LB in `submissions.md`, write a final postmortem.
