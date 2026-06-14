# Rules — Orbit Wars

> 引擎是 ground truth(`kaggle_environments/envs/orbit_wars/orbit_wars.py`);竞赛页是 JS 渲染、fetcher 不可读。
> 完整机制与行号引用见 `./README.md`「Ground truth」。

## Problem
Agent-vs-agent RTS:在 `kaggle_environments` 的 orbit_wars 引擎上,500 步内通过夺取 / 守住行星取胜。

## Data
- 无静态数据集;对局由引擎生成(self-play + 公开 agent 套件)。

## Metric
- **skill-rating (μ) 天梯**,μ0=600,**1v1(2-player)**;胜负驱动**配对 μ 更新**(赢家 μ↑、对手 μ↓,向均值靠拢)。
- 引擎同时支持 4p FFA,但**天梯只计 1v1**(`./README.md` RESOLVED 一节,基于 `kaggle competitions pages` 渲染)。

## Submission format
- **单文件 agent**(stdlib + `kaggle_environments`;或打包 tar.gz,如 kuni05 带 `orbit_lite/` + torch)。
- 每回合预算 1000 ms(我方 ~4ms/回合,崩溃安全包装返回 `[]`)。

## Constraints
- **每天最多 5 次提交**;竞赛只保留你**最新 2 个**活跃提交参与天梯。

## Deadline / schedule
- deadline **2026-06-23**;final eval ~其后 2 周。$50,000 Featured;~4137 teams;competition id **138420**。

## External data / kernel / internet / GPU rules
- 引擎纯 Python、CPU-bound(GPU 无帮助);评测端**实证可用 torch**(kuni05 torch 版上分 ~1137)。
- 公开对手 agent 来自公开 notebook(已注明出处);vendored 对手 gitignored,用 `arena/_reconstruct_pkg.py` /
  `arena/_extract_pub.py` 重建。

## Unclear rules (⚠ 待确认)
- 私有/最终榜的精确 μ 计算细节(以官网为准)。
