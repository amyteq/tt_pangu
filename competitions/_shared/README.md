# competitions/_shared

> 跨竞赛的共享区。说明本目录用途与边界。

- `competitions/` 存放**真实竞赛**的工作区文档(每个竞赛一个 slug 目录)。
- `_shared/` 存放**跨竞赛**的洞见、复用候选与迁移记录,不属于任何单个竞赛。
- `_templates/` 存放新竞赛开工时可直接复制的模板。

## 边界(本任务范围)
- 本任务只做**文档 / 工作区组织**。
- **不**提升 / 修改 KCA skills(`.kca/skills/`)或 KCA core(`tools/kca/`、`src/`)。
- **不**执行 Kaggle 提交 / kernel push / dataset 上传等远程副作用。
- KCA skill 的提炼只在 `skill-candidates.md` 里登记为**候选**,不实现。

## 文件
- `insights.md` — 跨竞赛洞见(确认 / 候选 / 否决)。
- `common-bugs.md` — 反复出现的失败模式。
- `skill-candidates.md` — 未来可能提炼成 KCA skill 的候选(仅停车场)。
- `migration-notes.md` — 目录迁移记录与待决项。
