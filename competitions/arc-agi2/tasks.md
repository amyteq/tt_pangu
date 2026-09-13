# Tasks — ARC-AGI-2

> Concrete next actions. Status: `todo` / `doing` / `done` / `blocked`. None started — research phase.
> Discipline: one meaningful change at a time; log hypothesis→change→seed→local pass@2→decision in `tracking.md`.

## Phase 0 — orient (no compute)
- [x] **T0.1** Live 2026 public-LB confirmed (API): top **nvbanana 50.56**, ~33–35 pack, **967 teams**,
      account entered. (See `tracking.md`.) `done`
- [x] **T0.2a** `submission.json` schema confirmed from `sample_submission.json`:
      `{task_id: [{"attempt_1": grid, "attempt_2": grid}, ...]}`. `done`
- [ ] **T0.2b** Confirm per-submission GPU-hour **quota** (beyond the 12h wall-clock) on the Code page. `todo`
- [x] **T0.3** Read ARC Prize 2025 Tech Report + NVARC + ARChitects 2024 + MindsAI/TRM papers; concrete
      reproducible recipe distilled into `ttt-recipe.md`. `done`
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
- [~] **T2.1** Reproduce a **TTT baseline** (NVARC/ARChitects family). `doing`
  - [x] **T2.1a** Model-agnostic CPU core (`solver/`): D8+color augmentation w/ exact inverse, grid
        serialization, leave-one-out TTT-data builder, PoE/vote selection, `solve_task` orchestration.
        **Validated** (oracle decode→100%, dummy→0% over 120 eval; 23 unit tests). `done`
  - [x] **T2.1b** GPU/model layer (`solver/model.py` + `run_eval.py`): `DecodeFn` w/ per-task LoRA TTT
        (rank 32, 64 steps, leave-one-out) + greedy decode + AIRV de-aug/PoE. Ran on snorlax 4090; fixed
        OOM (bs1+grad-ckpt+seq-filter) + ragged-grid parse. End-to-end works. `done`
  - [x] **T2.1c** Offline pretrain (`solver/pretrain.py`): 0.5B LoRA on 1000 train tasks, loss 0.69→0.29.
        **But eval WITH it still = 0/20 (0%).** Decode = structured-but-wrong grids. **Finding: rung-1 (0.5B)
        ceiling on ARC-2 eval ≈ 0% — capacity limit, not a bug** (oracle harness=100%). `done`
- **Rung-1 verdict:** the full TTT pipeline is built + validated end-to-end, but a 0.5B base is too weak for
  ARC-AGI-2 (lit: 8B→16.5%, NVARC 4B+synth+TRM→24%). **Next: rung-2** (T2.4) or pivot to the writeup angle.

## Phase 2b — rung-2 (the score lever)
- [x] **T2.4** Escalate base model to **Qwen3-4B-Base** on snorlax (fits 24GB bf16). Pretrained on the 1000
      train tasks (loss 0.16) + per-task TTT + 8-aug AIRV. **Eval = 0/20 (0%).** `done`
- **Rung-2 verdict:** model size is NOT the bottleneck. 4B fits the training distribution (loss 0.16) but
  scores 0% on eval — ARC-2 needs rule *generalization*, which our 1000-task pretrain doesn't teach. **The
  real lever is the DATA pipeline**, not scale.
- [~] **T2.5** **RE-ARC data pipeline** (the actual winning lever). `doing`
  - [x] **T2.5a** Integrate Michael Hodel's re-arc (MIT): `solver/fetch_rearc.py` (clone), `solver/rearc.py`
        (load 400 generators/verifiers via a matplotlib stub; generate verified, non-degenerate, de-duped
        examples → assemble ARC-format tasks), `solver/gen_rearc.py` (CLI). `arc_io.load_tasks_dir` +
        `pretrain.py --tasks-dir/--mix-arc2` consume it. **CPU-only generation; 5 unit tests; sample run validated.** `done`
  - [x] **T2.5b** Full corpus (4800 tasks) + Qwen3-4B RE-ARC pretrain (38min, loss ~0.29) + eval on snorlax.
        **Eval = 0/20 (0%).** Pipeline runs clean end-to-end; the RE-ARC lever is correct but the **dose is
        ~100× under the winning recipe** (1 epoch / 6206 ex / greedy / 4090 vs 256×-aug / ~98 H100-h / DFS / 8B). `done`
  - **T2.5 verdict:** the remaining gap to a non-zero score is **compute scale, not engineering.** The full
    pipeline (data gen → pretrain → per-task TTT → AIRV → eval) is built + validated. Closing the gap needs:
  - [ ] **T2.5c** scale the RE-ARC pretrain (raise --max-seq-len so 4-demo tasks aren't dropped; many epochs /
        256× aug; ideally 8B) + add **DFS decode + PoE** to `model.py` decode. **Multi-day, multi-GPU (rent
        H100s).** This is the 16–24% recipe; only worth it with that compute committed. `todo`
- [x] **T2.2** Augmentation + de-augmented vote/PoE selection for pass@2 — built in `solver/select.py`
      (the AIRV invariant is unit-tested). Measure real delta once T2.1b lands. `done (core)`
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
