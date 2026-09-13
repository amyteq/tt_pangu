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

| Account | Kernel (ver) | families | max/fanout | sub id | public | private | status |
|---|---|---|---|---|---:|---:|---|
| harrysun2006 | **sec-attack-jed-x** (v3) | **direct,deputy** | **40/20** | 54134283 | 2.400 | 0.600 | COMPLETE |
| harrysun2006 | sec-attack-jed (v4) | deputy,direct,filewash | 30/12 | 54134273 | 1.440 | 0.360 | ⚠ ERROR |
| firefly2006 | sec-attack-jed (v3) | deputy,direct,filewash | 30/12 | 54134296 | 1.440 | n/a | COMPLETE |
| firefly2006 | sec-attack-jed-x (v3) | filewash,direct | 24/12 | 54134299 | 1.080 | n/a | COMPLETE |
| harrysun2006 | (stray auto-submit v1) | — | — | 54132637 | — | — | ERROR |

> `private` filled in 2026-09-13 after close (see **Final results** below). `n/a` = firefly2006 not re-polled — those
> credentials now return `403 Forbidden`; their public values stand as read on 2026-06-29. `54134273` read COMPLETE on
> 2026-06-29 and reports **ERROR** on re-poll, with its scores still attached; cause not investigated.

**Results read 2026-06-29** (private score hidden until close). **Lever confirmed: fast-breadth wins** — all-1-message
families (`direct` exfil + `deputy`) at the highest fanout/cap scored best (2.40); the slow 7-message `filewash` chains
+ small cap scored lowest (1.08). The two identical balanced configs scored identically (1.440) → the eval is
deterministic. **Next: scale fast-breadth** (more domains/recipients = more distinct cells), drop file-wash.

### Iteration (2026-06-29)
| Account | Kernel (ver) | families | max/fanout | sub id | public | private | status |
|---|---|---|---|---|---:|---:|---|
| harrysun2006 | sec-attack-jed-xl (v1) | direct,deputy | 120/60 | 54183733 | **7.200** ⭐ | **1.800** | COMPLETE |

> Hypothesis was: 3× the fanout/cap of the 2.40 winner → more distinct firing cells → higher score, though
> "aggregation may not be linear". **Confirmed — and it *was* linear**: 2.400 → 7.200 is exactly **3.00×** for exactly
> 3× the breadth (max40/fanout20 → max120/fanout60). Same all-1-message families, so it stayed well under the
> 9000s/phase replay budget.

### Final results (competition closed 2026-09-01)

Re-polled 2026-09-13. The competition **closed 2026-09-01 23:59** — confirmed from the Kaggle API, which also settles
the `⚠ unverified` deadline note in `competition.yaml`. Featured, $50,000 USD, **4,186 teams**.

```
kaggle competitions submissions ai-agent-security-multi-step-tool-attacks
kaggle competitions leaderboard ai-agent-security-multi-step-tool-attacks -d
```

1. **Breadth scaled linearly.** 2.400 → 7.200 for 3× the cap/fanout, to three significant figures. The fast-breadth
   lever held across this range; we never found its ceiling.
2. **Private is exactly `public / 4` on every scored submission** (7.200→1.800, 2.400→0.600, 1.440→0.360). A constant
   ratio across three different configs points to a **fixed public/private split of the same cell population** rather
   than a harder private guardrail set — i.e. public score was a faithful proxy and the private LB added nothing.
   (Firefly's two were not re-polled, so this holds on 3 of 5 rows.)
3. **⚠ We are absent from the final leaderboard.** The full public-LB snapshot (4,186 rows, downloaded 2026-09-13)
   contains **no row for `harrysun2006` or `firefly2006`**, despite two COMPLETE non-zero submissions. Top public is
   **46.425**; our 7.200 would have placed around **rank ~3115 / 4186**. Cause unknown — possibly no submission was
   ever *selected* for the final standing, or the two `ERROR` submissions affected eligibility. **Open question**: if
   we re-enter a Kaggle code competition, verify submission *selection* explicitly before the deadline.

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
