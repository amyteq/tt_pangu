# Submissions — nemo

> Every known push/submit/LB record from issue #86 (Table 2 + comments) and the kernel README.
> Quota: 5/team/day. "Local" = per-kernel held-out (not a single canonical CV). Unknowns = `unknown`.
> Submission IDs are not recorded in available evidence.

| Date | Version | Run/Experiment (kernel) | Local CV | Public LB | Private LB | Submit/push type | Artifact | Notes |
|---|---|---|---:|---:|---:|---|---|---|
| 2026-06 | identity | untrained adapter | — | 0.47 | unknown | kernel | adapter | base reference |
| 2026-06 | v5 | bare-answer SFT, 120 steps | unknown | 0.61 | unknown | kernel | adapter | kernel README |
| 2026-06 | v6 | CoT, loss over prompt+padding (bug) | unknown | 0.44 | unknown | kernel | adapter | masking bug → regression |
| 2026-06 | v7 | CoT + response-only mask, 400 steps | unknown | 0.65 | unknown | kernel | adapter | prior best before A/B |
| 2026-06-12 | ctx4k (T1) | `harrysun2006/...`; seq4096, 580 steps, loss 0.147 | unknown | 0.67 | unknown | kernel | adapter | new best then; +0.02 over v7 |
| 2026-06-12 | ctx2k (T2) | `firefly2006/...`; seq2048, 583 steps, loss 0.186 | unknown | 0.42 | unknown | kernel | adapter | below base; right-trunc cut `\boxed{}` (negative lesson) |
| 2026-06-12 | v10 (T4) | `firefly2006/nemo-rule4k-v10`; 8000 ex, 558 steps, loss 0.93 | held-out 3/4 | 0.59 | unknown | kernel | adapter | merge-pool member |
| 2026-06-13 | **v14 (T10)** | `harrysun2006/nemo-replay-v14`; seq8192, 254/254 steps, loss ~0.05 | unknown | **0.85** | unknown | kernel | adapter | **best**; +0.18; PR #90 |
| 2026-06-14 | t7 merge | `harrysun2006/nemo-merge-t7`; SVD rank32(1.0·v14+0.25·ctx4k+0.25·v10) | reldiff ~0.18–0.27 | 0.82 | unknown | kernel | adapter | regression −0.03; route closed; PR #94 |
| 2026-06-14 | v15 (T11) | `harrysun2006/nemo-synth-v15`; 2640 synth ex, 337/337 steps, loss ~0.002 | CoT-answer 1930/1930 | 0.84 | unknown | kernel | adapter | regression −0.01; PR #95 |

## Kernel push status
- All listed kernels were pushed and evaluated (LB returned). v15 (`nemo-synth-v15`) was the last run (2026-06-14).
- ⚠ No live Kaggle status refresh performed in this consolidation. Read-only refresh is now **authorized** (creds in `.vscode/.env.harry`, `.vscode/.env.may`); pending follow-up to fill in submission IDs / private LB (read-only only — no submit/push/upload). Status above reflects issue #86 evidence current to 2026-06-14 ~05:00 UTC.

## Submission checklist
- [ ] local validation passed (validate_kernel.py + fail-fast preflight)
- [ ] submission shape checked (submission.zip @ /kaggle/working; rank32/α32)
- [ ] no secrets
- [ ] runtime acceptable (≤8h wall-clock guard)
- [ ] approval obtained (remote submit needs human approval)
- [ ] result recorded (this table)
