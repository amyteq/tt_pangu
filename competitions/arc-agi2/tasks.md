# Tasks — ARC-AGI-2

> Concrete next actions. Status: `todo` / `doing` / `done` / `blocked`. None started — research phase.
> Discipline: one meaningful change at a time; log hypothesis→change→seed→local pass@2→decision in `tracking.md`.

## Phase 0 — orient (no compute)
- [x] **T0.1** Live 2026 public-LB confirmed (API): top **nvbanana 50.56**, ~33–35 pack, **967 teams**,
      account entered. (See `tracking.md`.) `done`
- [x] **T0.2a** `submission.json` schema confirmed from `sample_submission.json`:
      `{task_id: [{"attempt_1": grid, "attempt_2": grid}, ...]}`. `done`
- [ ] **T0.2b** Confirm per-submission GPU-hour **quota** (beyond the 12h wall-clock) on the Code page. `todo`
- [ ] **T0.3** Read ARC Prize 2025 Technical Report (arXiv:2601.10904) + NVIDIA NVARC blog for the
      reference recipe. `todo` ← **next**
- [ ] **T0.4** Decide Kaggle account + create `kca-arc.yaml` (per-comp config + autonomy screen) before
      any push. `todo`

## Phase 1 — local foundation (prereq for all experiments)
- [x] **T1.1** Public train (1000) + eval (120) downloaded into `data/ARC-AGI-2` (gitignored);
      `eval/fetch_data.py` repopulates. `done`
- [x] **T1.2** Dataset loader (`eval/arc_io.py`, both GitHub + Kaggle layouts) + terminal viewer
      (`eval/viewer.py`). `done`
- [x] **T1.3** Local **pass@2 scorer** (`eval/metric.py`) matching official exact-match scoring;
      **validated** (oracle→100%, corruption→<100%, baselines→0%, 8/8 unit tests). `done`
- [ ] **T1.4** Catalog task families on public eval (symbolic / compositional / contextual / sequential)
      to know where the gaps are. `todo`

## Phase 2 — baseline
- [ ] **T2.1** Reproduce a **TTT baseline** (NVARC/ARChitects family) on a ≤4B base; target ≈ 2025 floor
      (~20–24%) on the 120 public-eval tasks, offline. `todo`
- [ ] **T2.2** Add **augmentation + inverted-vote candidate selection** for pass@2; measure delta. `todo`
- [ ] **T2.3** Confirm the kernel runs inside **12h / no-internet / L4x4** with a single-task preflight. `todo`

## Phase 3 — levers (one at a time, gated on T1.3 harness)
- [ ] **T3.1** Synthetic ARC-2-like data generator (multi-rule / contextual / sequential); pretrain + measure
      per-family delta (avoid single-family over-dose — nemo H2). `todo`
- [ ] **T3.2** Neural-guided DSL search + exact verifier on the executable subset; measure tasks it adds
      over TTT. `todo`
- [ ] **T3.3** Per-task-family routing / specialization (detect family → best solver/adapter). `todo`
- [ ] **T3.4** Recursive-refinement (TRM-style) efficiency experiment; score-vs-cost knee. `todo`

## Phase 4 — submission & writeup (Nov)
- [ ] **T4.1** Submission-strategy schedule (target ~2h before daily roll-over; per CLAUDE.md table).
      Final-week promotion is **human-gated**. `todo`
- [ ] **T4.2** Keep `tracking.md` paper-grade — the **Grand Prize is writeup-scored** ($275K, guaranteed). `todo`
- [ ] **T4.3** Open-source prep (CC0/MIT-0) + one-click reproduction before private scoring. `todo`

## Open decisions for the human
- Compute: local snorlax (RTX 4090) for dev vs Kaggle L4x4 for the scored run vs external GPU (#83)?
- Which prize to optimize: accuracy/rank (Progress) vs the writeup (Grand, guaranteed)?
- How much effort budget to allocate now vs holding until closer to the Nov deadline?
