# Tasks — sec-attack

## Now
- [x] **T1 (SDK-confirmed) target agent + guardrail:** default agent `AUTO`→**gpt_oss** (factory); default guardrail
      **`optimal_public`** (report.json); private LB swaps a held-out guardrail via `AICOMP_ATTACK_GUARDRAIL_ID` /
      entry-point group `aicomp_sdk.attack_guardrails`. *(Still verify deadlines/limits/prize on the official page —
      those remain [WEB ⚠].)*
- [x] **T2 Local loop up:** `aicomp validate/evaluate redteam attack.py --env gym --agent deterministic` runs green
      (deps: aicomp-sdk + pydantic + gymnasium; no torch for the deterministic path).
- [x] **T3 Scorer reproduced exactly:** `eval/reproduce_scorer.py` — our `raw=Σ SEVERITY_W+2·unique_cells` ==
      SDK `score_attack` on allow-all (0.05) and `optimal_public` (0.00). Caps found: 2000 findings / ≤32 msgs / hops=4.

## Next
- [x] **T4 Go-Explore baseline ported + run** → `kernels/attack_goexplore.py`; floor **0.00 vs `optimal_public`**
      (deterministic, gym). (It's blocked — expected; bypass needed.)
- [x] **T6 Bypass generators (H2):** `kernels/attack_bypass.py` (file-wash + http.post data-blind-spot) →
      **18.0 vs `optimal_public`** (was 0.00); `eval/validate_bypass.py` + `eval/instruction_agent.py`. *(H3 encoded-
      exfil refuted for the sentinel — see strategy.md.)*
- [~] **T5 Real-agent run (H6):** Kaggle submission notebook built + pushed (`kernels/sec-attack-jed.ipynb` →
      `harrysun2006/sec-attack-jed`); verifies templates against the REAL in-kernel agent (gpt_oss), keeps firing
      families, fans out across benign sinks. **Pending:** read run score/logs → tune `MAX_CANDIDATES`/phrasing → submit to LB.
- [ ] **T7 Scale + stack:** grow to ~2000 distinct chains + predicate-stacking (toward 180–1000 raw/200); add best-2000 ranking.
- [ ] **T8 Robustness:** build a held-out guardrail approximating the private one; both current holes may be closed there.

## Backlog
- [ ] H2 file-wash window tuning; H3 encoded-exfil generator; H4 four predicate-family generators + stacking.
- [ ] H5 offline web-corpus mining (which pages/queries drive a real agent to a scored action).
- [ ] H7 bound the snapshot archive to search longer within 1800 s.
- [ ] Build a *held-out* guardrail of our own (approximate the private one) to measure robustness, not public-LB overfit.
- [ ] Decide the 2 final-submission portfolio (breadth-max vs robustness-max).
- [ ] Adopt `kca-<slug>.yaml` + on-the-fly metadata for attack.py push once the loop is real (relates to #85).

## Blocked
- Real-agent dev blocked on **T1/T5** (which agent?) and GPU availability (snorlax/may).

## Done
- [x] Folder `competitions/sec-attack/` created, mirrored on `nvidia-nemotron`.
- [x] Source-verified mechanics writeup (`research.md`) from `aicomp-sdk` 3.1.2 (pip-downloaded + read).
- [x] T1 (agent/guardrail confirmed) · T2 (local loop) · T3 (scorer reproduced) · T4 (baseline 0.00) · T6 (bypass 18.0).

## Proposed GitHub issues
> Not created here; titles + acceptance criteria only.
- **"sec-attack: reproduce local scorer + Go-Explore baseline floor"** — AC: `aicomp evaluate` runs green; our offline
  `score_attack` equals the CLI normalized score on ≥3 runs; baseline score + unique-cell count recorded in `submissions.md`.
- **"sec-attack: confirm LB target agent + private-guardrail behavior"** — AC: official-page evidence cited for the
  evaluator agent(s); a real-agent baseline run recorded; public/private overfit risk documented.
