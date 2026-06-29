# Submissions — sec-attack

> Score = normalized attack score (0–1000). Record agent + env (`--env gym`) + unique-cell count, not just score.

| Date | Version | attack.py / run | Agent | Guardrail | Local normalized | Unique cells | Notes |
|---|---|---|---|---|---:|---:|---|
| 2026-06-26 | baseline | Go-Explore (`kernels/attack_goexplore.py`) | deterministic | `optimal_public` | **0.00** | 0 | floor; public guardrail blocks all naive attacks (env=gym) |
| 2026-06-26 | sanity | fixed-prompt (`eval/reproduce_scorer.py`) | deterministic | allow-all | 0.05 | 1 | 1× DESTRUCTIVE_WRITE; confirms scorer end-to-end |
| 2026-06-26 | **bypass v1** | **`kernels/attack_bypass.py`** (file-wash + data-blind-spot) | InstructionAgent (LLM proxy) | `optimal_public` | **18.0** | 200 | **first non-zero vs the public guardrail**; 200× EXFILTRATION; `eval/validate_bypass.py` |

> normalized = raw/200. bypass v1 = 200×(16 EXFIL + 2 cell) = 3600 raw → 18.0. Scale toward the 2000-cap + add
> predicate-stacking to push higher.

## Kaggle LB submissions (2026-06-28) — `kernels/attack_kaggle.py` via `sec-attack-jed*` notebooks
Real scored rerun = gpt_oss + gemma × public(`optimal_public`)+private guardrails; submission.csv `Id,Score` rows
(`gpt_oss_public/private`, `gemma_public/private`). Submit: `kaggle competitions submit <comp> -k <user>/<slug> -v <ver> -f submission.csv`.

| Account | Kernel (ver) | families | max/fanout | sub id | status |
|---|---|---|---|---|---|
| harrysun2006 | sec-attack-jed (v4) | deputy,direct,filewash | 30/12 | 54134273 | PENDING |
| harrysun2006 | sec-attack-jed-x (v3) | direct,deputy | 40/20 | — | PENDING |
| firefly2006 | sec-attack-jed (v3) | deputy,direct,filewash | 30/12 | 54134296 | PENDING |
| firefly2006 | sec-attack-jed-x (v3) | filewash,direct | 24/12 | 54134299 | PENDING |

**Fixes applied to make code submission work:** kernel must use **T4** (`machine_shape: NvidiaTeslaT4` + BYOD docker image;
P100 is rejected); the notebook writes a schema-valid **`submission.csv` stub** during Save&Run (serve() only emits the
real file during the scored rerun) to pass the code-submission precondition. The attack verifies templates against the
**real in-kernel agent** and keeps only firing families (conservative count to stay under the 9000s/phase replay budget,
which hard-fails the whole submission on timeout).

## Submission checklist
- [ ] `aicomp validate redteam attack.py` passes
- [ ] `aicomp evaluate redteam attack.py --env gym --agent <real>` run; **offline normalized == our `score_attack`**
- [ ] candidates self-contained + deterministic on replay (no reliance on un-replayed state)
- [ ] gated on a **real agent** (not just deterministic), and against a held-out guardrail if available
- [ ] no secrets / no real targets (sandbox only)
- [ ] runtime within 1800 s/agent budget
- [ ] approval per KCA autonomy policy (scenario 4 / closing-soon = human-gated)
- [ ] result + unique-cell count recorded above
