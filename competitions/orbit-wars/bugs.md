# Bugs — Orbit Wars

> 多为「方法论陷阱」而非崩溃;详见 `./README.md` / `./VALIDATION.md`。

| ID | Status | Severity | Area | Summary | Evidence | Next action |
|---|---|---|---|---|---|---|
| B1 | fixed | high | eval-methodology | 自博弈离线胜率**不预测天梯**(v3 离线赢 v2.1 91% 却天梯≈) | README.md(self-play 一节) | 改用 `arena/suite_gate.py` 强弱跨度套件门控 |
| B2 | fixed | medium | eval-methodology | identical-mirror 平局多 → 「no-edge」win% ~39%(2p)/ ~57.5%(4p),非 50% | README.md(calibration notes) | 读 decisive W-L / avg_rank,勿读裸 win% |
| B3 | fixed | high | value-fn | 对所有 k 计净舰值惩罚在途舰(发射看似亏)→ 近被动(2.5% vs v2.1) | README.md(Forecast key bug) | 改**终局 k=H** 差分(守恒正确) |
| B4 | fixed | medium | agent-robustness | 任何异常返回 `[]`(被动但不崩,不弃权) | README.md(v1) | 全 agent 用崩溃安全包装 |
| B5 | open | high | strength-gap | 对强档(evogen1093/multifocus/kuni05)0-15% 的硬 cliff | README.md(incremental path exhausted) | v4 集合规划整体重构,套件门控 |
