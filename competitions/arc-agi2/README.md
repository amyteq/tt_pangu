# ARC Prize 2026 — ARC-AGI-2 (arc)

> Canonical language: **English** for facts/strategy; the human-facing 详细介绍 lives in
> `overview_zh.md`. Aliases: `arc`, `arc-agi2`, `arcprize`.
> Kaggle slug: `arc-prize-2026-arc-agi-2`.
> Status: **research / prep** — local env + eval harness built (2026-06-26); no TTT baseline or submission yet.
> Numbers are from the 2026-06-26 research scan + a read-only Kaggle API refresh (`references.md` / `tracking.md`).

## Status snapshot
- status: **research** (prep phase) — competition launched **2026-03-25**, final submission **2026-11-02**
- one-liner: infer the hidden input→output transformation of a visual grid puzzle from 2–5 demo pairs,
  then produce the test output. **2 guesses per test input (pass@2)**, exact pixel match.
- metric: **pass@2**, mean over private-eval test inputs (exact grid match)
- prize pool: **$700,000** (Progress $275K + Grand/writeup $275K + Bonus $150K if any team hits **85%**)
- **live 2026 public LB: top = nvbanana 50.56**, ~33–35 pack behind; **967 teams**; our account is entered
- Kaggle-constrained SOTA (2025 inaugural run): **NVARC 24.03%** (TTT on a ~4B model + synthetic data)
- human baseline: **66%** individual avg on public eval; calibration panel solves **100%**
- frontier-LLM-via-API SOTA (NOT Kaggle-eligible — internet off): ~37–85% but at $2–30/task
- done: live LB confirmed · public data downloaded (1000+120, gitignored) · submission schema confirmed ·
  **local pass@2 harness built + validated** (oracle 100%, baselines 0%, 8/8 tests). next: TTT baseline (T2).

## What's in this folder
| File | Purpose |
|---|---|
| `overview_zh.md` | **详细中文介绍 + ideas + 挑战 + 提分技术**（本任务的主交付物） |
| `competition.yaml` | machine-readable config (dates, metric, constraints, SoT) |
| `rules.md` | evidence-cited rules / data / metric / submission / constraints (⚠ on unverified) |
| `research.md` | literature & SOTA scan: 2024/2025 winners, approach families, what maps to ARC-AGI-2 |
| `strategy.md` | candidate directions, hypotheses, ideas-to-try, what to avoid |
| `references.md` | every source with URL + trust label |
| `tasks.md` | concrete next actions (data, baseline, eval harness) |
| `tracking.md` | experiment / submission log + live-LB snapshot |
| `eval/` | **local pass@2 harness** (loader, metric, baselines, viewer, CLI) + `eval/README.md` |
| `tests/` | unit tests for the metric (`python -m pytest tests/`) |
| `data/` | gitignored local data (`python eval/fetch_data.py` to repopulate) |

## Key facts (cite `references.md`)
- **Code competition**, notebook-only. **12-hour** wall-clock, **internet off** during Kaggle scoring,
  **$10K** compute ceiling per verification run, hardware **L4x4 (96 GB)** or T4x2.
- Data: **1,000** public train tasks + **120** public eval + **120** semi-private (live LB) + **120**
  private (final). Grids are 1×1…30×30 of integers 0–9 (colors). JSON `{"train":[...],"test":[...]}`.
- Winning solution must be **open-sourced (CC0/MIT-0)** before receiving private scores.
- ARC-AGI-2 deliberately removes brute-force-solvable tasks and adds **symbolic interpretation,
  compositional multi-rule, contextual rule application, and sequential-dependency** tasks. The same
  o3-medium that got ~53% on ARC-AGI-1 gets **~3%** here. Efficiency (cost/task) is a first-class constraint.

## Suggested first moves (see `tasks.md`)
1. Confirm the **live 2026 public leaderboard** standing in a browser (research couldn't render it).
2. Download public train/eval from `github.com/arcprize/ARC-AGI-2`; build a local task viewer + scorer.
3. Reproduce a **TTT baseline** (the NVARC/ARChitects family) as the competitive floor (~24%).
4. Build a local pass@2 eval harness on the 120 public-eval tasks before any Kaggle submit.

## Links
- competition: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2
- data + format: https://github.com/arcprize/ARC-AGI-2
- benchmark page: https://arcprize.org/arc-agi/2
- 2025 results analysis: https://arcprize.org/blog/arc-prize-2025-results-analysis
- _shared insights: ../_shared/
