# References — Orbit Wars

> Each: title / URL or relative path / one-line note / relevance.

## Kaggle
- Competition page — https://www.kaggle.com/competitions/orbit-wars — Overview/Data/Code/Discussion (id 138420) — high.
- Rules — https://www.kaggle.com/competitions/orbit-wars/rules — 5/day, latest-2 scored — high.
- Public episode dataset — `kaggle/orbit-wars-episodes-2026-06-08` (~1.28 GB) — replay-mining source (T1) — high.
- Engine source `kaggle_environments/envs/orbit_wars/orbit_wars.py` — ground truth — high.

## Notebooks / agents (external, attributed)
- kuni05 "Producer Agent" (LB 1240.5) — https://www.kaggle.com/code/kuni05/lb-1240-5-orbit-wars-producer-agent-submission — our attributed entry source + strong-tier study — high.
- evogen v5 (LB 1093) — https://www.kaggle.com/code/penguin069/evogen-v5-1093 — weakest strong-tier; opening DFS + multi-source — high.
- romantamrazov (LB ~1224) — early adapted baseline (attributed) — medium.

## Internal notes / code
- `./README.md` — detailed chronological log (versions, design studies, dead-ends) — high.
- `./EPISODES.md` — real-game analyses (#1 Jake Will; #2 top-8 profiling) — high.
- `./LEAGUE.md` — version league results (submission-slot decisions) — high.
- `./VALIDATION.md` — pre-submit arena gate checklist (T10) — high.
- `agent/main.py`, `agent/versions/*.py` (v1..v4, forecast, v3_2, v3_2_coarr, kuni05) — agent implementations — high.
- `arena/suite_gate.py` — ladder-predictive suite gate; `arena/pool.py` — parallel arena; `arena/sweep_opt.py` — powered sweep — high.
- `arena/distill_*.py`, `arena/episodes_*.py` — T12 distillation + replay pipeline — medium.
- `submit.py` — compliance-gated multi-account submit tool — medium.

## Work docs (analysis)
- `work/00.orbit.md` — A1 (Claude) + A2 (ChatGPT) analysis (zh): rules, modular architecture (ThreatLedger…), ideas A–I, techniques 1–10 — high. (English digest in `notes_zh.md`.)

## Worklogs
- `worklogs/orbit.md`, `worklogs/orbit2.md` — Chinese strategy hub mirror + full history — high.

## Issues / PRs / commits
- GitHub issue **#87** — strategy & tracking hub (body + 15 comments; Chinese) — high. (Historical; future updates here.)
- Sibling hub: issue **#86** (NVIDIA Nemotron).
- PRs (merged): **#80** (agent + arena + EPISODES + utils), **#89** (snorlax compute doc). **#92** (v4 Scheduler).
- Cross-refs: **#83** (external GPU / snorlax), **#21** (multi-account quota), **#77/#78** (kca submit-link gaps).
- snorlax compute: `docs/tooling/remote-compute-snorlax.md` (PR #89).

## Research findings (OW-P0-RESEARCH-001, 2026-06-16)
- **kuni05 source:** public kernel id **121702304** (author kuni05), read-only pull OK; rules + exact flow-diff planner (NOT a NN), needs torch. Study: `discussions/2026-06-16-kuni05-system-study.md`; attribution + re-pull: `sources/README.md`.
- **Matchmaking (empirical, `ListEpisodes` over subs 53582503 n=239 + 53730511 n=32):** Kaggle pairs **similar-skill from the first game** (μ0=600 first opponent ≈601; per-episode |opp−our| median ~43–66; opponent μ tracks ours upward). Official: skill-rating, pairwise μ-toward-mean. **~half the games are 4p and 4p also updates μ.** Conclusion `similar_skill / similar_first / medium-high`; early 10–20 episodes are informative (no weak-first warmup), but noisy. See `insights.md` INS-005.
- **Identity:** `flyingfox` = harrysun2006's profile name = US (not external). Full map + join chain: `live/player_identity_map.md`.
