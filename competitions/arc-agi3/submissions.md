# Submissions — ARC-AGI-3

> RHAE-scored Kaggle notebook track. **Daily limit = 1 submission/account/day**
> (verified 2026-06-27; the retroactive "Team AIRIS" change). 4 candidates built +
> validated; 2 submitted today (1/account), 2 queued for next day.

## Kernels (all pushed + run COMPLETE, boilerplate clean, agent logic validated locally vs 25 public envs)
| Kernel | Account | Agent | GPU | Pushed | Run | Submitted |
|---|---|---|---|---|---|---|
| arc3-goose (slug `arc3-goose-stochasticgoose-cnn`) | harrysun2006 | canonical StochasticGoose CNN | yes | ✅ v1 | COMPLETE | ✅ 2026-06-27 (id 54111934, PENDING) |
| arc3-goosenov | harrysun2006 | CNN + novelty escape | yes | ✅ v1 | COMPLETE | ⏸ blocked by 1/day → next day |
| arc3-explore | firefly2006 | frame-diff heuristic | no | ✅ v1 | COMPLETE | ✅ 2026-06-27 (id 54111957, PENDING) |
| arc3-reactive | firefly2006 | object-centric heuristic | no | ✅ v1 | COMPLETE | ⏸ blocked by 1/day → next day |

## Submission log
| Date | Kernel | id | Submit type | Public LB | Private LB | Notes |
|---|---|---|---|---:|---:|---|
| 2026-06-27 | harrysun2006/arc3-goose-stochasticgoose-cnn | 54111934 | code-comp (-k -v1 -f submission.parquet) | PENDING | — | canonical StochasticGoose CNN; scored rerun running (~up to 8h) |
| 2026-06-27 | firefly2006/arc3-explore | 54111957 | code-comp (-k -v1 -f submission.parquet) | PENDING | — | frame-diff heuristic; scored rerun running |
| (next day) | harrysun2006/arc3-goosenov | — | queued | — | — | 400 today (1/account/day cap) |
| (next day) | firefly2006/arc3-reactive | — | queued | — | — | 400 today (1/account/day cap) |

## Validation evidence (local, vs real public games via arc-agi SDK + anon key)
- All 4 agents ran clean end-to-end against public games (no exceptions); gateway-style
  contract confirmed (`available_actions` raw ints `[1,2,3,4,6]`, no `score`, frame `(1,64,64)`).
- Kaggle normal-run logs: each produced `my_agent.py` + `submission.parquet`, NbConvert OK;
  only non-fatal pip dependency-resolver notice.

## Submission checklist
- [ ] local RHAE computed over the 25 public envs (don't burn quota blind)
- [ ] notebook is **one-click runnable** (no manual config/clicks)
- [ ] runs **< 12h**, **no internet** at eval (no hosted LLM API calls)
- [ ] uses `OperationMode.COMPETITION` (API-only, level-resets only, auto-scores)
- [ ] runtime cost within **$10K** cap
- [ ] no secrets / no API keys committed to the notebook
- [ ] daily submission limit not exceeded (⚠ confirm exact limit — Kaggle login)
- [ ] track confirmed (Official = no harness; Community = harness allowed)
- [ ] result recorded here
