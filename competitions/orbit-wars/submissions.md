# Submissions — Orbit Wars

> 天梯分(μ0=600 起);精确历史见 `./README.md`、`./LEAGUE.md`、`worklogs/orbit2.md`。
> 竞赛只保留**最新 2 个**活跃提交。

| Date | Version | Run/Experiment | Local CV | Public LB | Private LB | Submit/push type | Artifact | Notes |
|---|---|---|---:|---:|---:|---|---|---|
| 2026-06 | adapted-kuni05 | 公开 LB-1240.5 重建(已注明出处) | suite 89.6% | ~1137 ↑ | — | agent (tar.gz+torch) | versions/kuni05/ | 竞争性条目,向 ~1240 爬升 |
| 2026-06 | Forecast v3 | 自研前向模拟规划器 | suite 54.2% | ~686 | — | agent (single-file) | agent/main.py(曾) | 自研线;离线赢 v2.1 91% 但天梯≈v2.1 |
| 2026-06 | v2.1 | Phase-Scaled 启发式 | suite 54.8% | 556 (retired) | — | agent (single-file) | versions/v2_1.py | μ0=600 基线;已退役 |

## Submission checklist
- [ ] local validation passed (arena/suite_gate.py 套件门控,decisive W-L)
- [ ] submission shape checked (单文件 stdlib-only 或 tar.gz;每回合 < 1000ms;崩溃安全)
- [ ] no secrets
- [ ] runtime acceptable
- [ ] approval obtained (Kaggle 提交需人工批准;先在官网接受规则)
- [ ] result recorded (回填本表 + LEAGUE.md)
