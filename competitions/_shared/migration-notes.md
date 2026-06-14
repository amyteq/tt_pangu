# Migration notes (KCT-001)

> 记录 `competitions/` 整理过程中的移动决策、已完成项与待决项。任务 = 仅文档 / 工作区组织。

## 已完成的移动 (done)

### nvidia-nemotron(别名 nemo / nemotron)— 已 `git mv`
- `experiments/nvidia-nemotron-model-reasoning-challenge/` → `competitions/nvidia-nemotron/experiments/`
- 依据:任务明确规定「将 `experiments/nvidia-nemotron-model-reasoning-challenge` 缩短为 `nvidia-nemotron`,别名 nemo / nemotron」,且这是**真实 Kaggle 竞赛**(slug `nvidia-nemotron-model-reasoning-challenge`)。
- 安全性核查:迁移前 `git grep` 仅发现 **1 处**仓库内引用(`kernels/nemo-merge-t7/nemo-merge-t7.py` 的注释指向 `…/merge/svd_merge.py`),且该引用**位于被移动子树内部**,相对结构保持不变 → 安全。其余引用只在 `worklogs/`、`logs/`(历史记录,不影响)。
- `kernel-metadata.json` 使用相对 `code_file` + Kaggle slug(`competition_sources`、`id`),与本地路径无关,移动不影响 Kaggle push。
- ⚠ 小遗留:`competitions/nvidia-nemotron/experiments/kernels/nemo-merge-t7/nemo-merge-t7.py` 顶部注释仍写旧路径 `experiments/nvidia-nemotron-model-reasoning-challenge/merge/svd_merge.py`。仅注释,**未改动代码**(本任务不修改竞赛代码)。建议后续顺手更正。

## 待决 / 受阻的移动 (proposed but blocked)

### tpu-getting-started(Petals to the Metal — Flower Classification on TPU)— **不移动,仅登记**
- 现状:`experiments/tpu-getting-started/`(M10 竞赛 + M14 goal-loop 目标;`goal.md` 标 `status: active`,target LB 0.85)。这是**真实 Kaggle 竞赛**,按规则本应进 `competitions/`。
- **为何不移动**:迁移会破坏多处**禁止修改**的路径里的**承重引用**(stop condition)——
  - `scripts/m10_t002_local_train.py`、`scripts/m10_t003_drive_reviewer_gate.py`(运行期读取 `experiments/tpu-getting-started/baseline-tl/baseline.ipynb` 与 `kernel-metadata.json`)
  - `tests/fixtures/tpu-getting-started/search-space*.yaml`(`seed_template: experiments/tpu-getting-started/baseline-tl/baseline.py`,测试承重)
  - `.claude/skills/kaggle-tooling-integration/SKILL.md`(引用 baseline.py 作为路径解析范例)
  - `docs/evidence/m14/…`、`docs/milestones/m14/loop-prompts.md`、`docs/tasks/m14/M14-T003-kca-explore.md`
  - 这些路径(`scripts/`、`tests/`、`.claude/skills/`、`docs/`)均**不在本任务 allowed_paths**(仅 `competitions/**` + `README.md`),无法同步更新 → 移动将留下断链 / 破坏测试与脚本。
- **建议(后续任务)**:将 `experiments/tpu-getting-started/` 迁入 `competitions/petals-to-the-metal/experiments/`,并在**同一 PR** 内更新上述 `scripts/`、`tests/`、`.claude/skills/`、`docs/` 引用;同时补全 `competitions/petals-to-the-metal/` 文档集。状态:archived/recent(M10 已 close,M14 goal-loop 曾以其为目标)。证据:`experiments/tpu-getting-started/README.md`、`goal.md`、`docs/milestones/README.md`(M10)。

## 其它

- **`experiements/` 拼写错误目录**:仓库中**不存在**该拼写;只有正确的 `experiments/`。无需更正。
- **`experiments/` 残留**:移走 nemo 后,`experiments/` 仅剩 `tpu-getting-started/`(见上,真实竞赛,受阻待迁)。其余无 KCA 平台实验目录。
- **orbit-wars**:迁移前已位于 `competitions/orbit-wars/`(含 `agent/`、`arena/`、原 `README.md` 详细日志等)。本任务**保留原有文件不动**,仅在其上**新增**标准文档集(`competition.yaml`、`rules.md`、`strategy.md`、`tasks.md`、`submissions.md`、`bugs.md`、`references.md`、`insights.md`、`postmortems/`)。原 `README.md`(含 TL;DR 状态快照 + 详细日志)作为该竞赛主文档与证据保留。

## KCT-002 (2026-06-14) — nemo English consolidation

- `competitions/nvidia-nemotron/` 文档由 KCT-001 的中文**临时版**改写为**英文规范版**(canonical English),
  并新增 `tracking.md`(issue #86 三表英文化 + current status)与 `_zh` sidecars(`tracking_zh.md` 逐字保留
  issue #86 中文正文、`notes_zh.md` 中文来源指引+关键摘录)。
- 来源:GitHub issue #86(body + 5 comments)、`work/00.nemo.md`、`work/00.nemotron_3_versions.zip`、
  `worklogs/nemo*.md`、PR #90/#94/#95。
- 远程刷新:已于 **2026-06-14** 用 read-only Kaggle API(`kaggle competitions submissions`,双账号,creds 仅 read-for-use 不打印)完成刷新,回填 `submissions.md` / `tracking.md`:own 最好 0.85(v14)、账号原始公开最大 0.86(2026-05-15 public-fork,非自训)、榜首 ~0.90、private LB 未发布;Kaggle submissions API 不暴露数字 submission ID。未做任何 submit/push/upload。
- issue #86 保持**开放**作历史;后续状态更新改在 `competitions/nvidia-nemotron/`。

## KCT-003 (2026-06-14) — orbit-wars English consolidation

- `competitions/orbit-wars/` 文档由 KCT-001 的中文**临时版**改写为**英文规范版**(canonical English),
  并新增 `tracking.md`(issue #87 表格英文化:D1–D5 / T1–T14 / §9 / levers / 版本演进 + 刷新后天梯)与
  `_zh` sidecars(`tracking_zh.md` 逐字保留 issue #87 中文正文、`notes_zh.md` 中文来源指引+摘录)。
  既有英文 `README.md`(详细日志)、`EPISODES.md` / `LEAGUE.md` / `VALIDATION.md` / `agent/` / `arena/`
  保留不动;README 顶部加了一段「Current status (2026-06-14)」紧凑状态块。
  KCT-001 postmortem 译成英文保留为 `postmortems/2026-06-14-kct-001-initial-consolidation.md`。
- 来源:GitHub issue #87(body + 15 comments)、`work/00.orbit.md`(A1/A2 分析)、`worklogs/orbit*.md`、PR #80/#89/#92。
- 远程刷新:已于 **2026-06-14** 用 read-only Kaggle API(`kaggle competitions submissions orbit-wars` 双账号 +
  `leaderboard`,creds 仅 read-for-use 不打印)完成:harry latest-2 = kuni05 1085.4 / v3.2 660.0;may latest-2 =
  v3_2_coarr 648.8 / v3.2 636.7;峰值 kuni05 1151.0 / v3 686.1;榜首 ~1746;private LB 未发布。未做任何 submit/push/upload。
- issue #87 保持**开放**作历史;后续状态更新改在 `competitions/orbit-wars/`。
