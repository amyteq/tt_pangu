# Orbit Wars — 本地 test/validation 清单(T10)

> 规则(Harry,issue #87 2026-06-12):**本地测试通过、并且相对当前最佳有确认提高,才提交**。
> 每个候选版本走完下表再谈提交;结果记入 `README.md` 实验日志 + issue #87 工作日志。

## 提交前必过门(全部 PASS 才有提交资格)

| # | 检查 | 命令 | 通过标准 |
|---|---|---|---|
| 1 | **崩溃安全** | `python arena/validate.py <agent>`(或任一 h2h 跑 ≥10 局) | 500 步全程零异常;裸 `_agent`(不带 try/except 包装)自博弈 ≥4 局无异常 |
| 2 | **弱档无回退** | `python arena/suite_gate.py <agent> --games 12` | random 100%;starter ≥ 85%;adilshamim / pub_tactical 不低于基线 −7pt |
| 3 | **强档有提高(功效协议)** | `python arena/t8_ab.py` 同款 A/B:候选 vs 基线,各 ≥150 配对种子(300 局)/对手,**全新种子块** | vs evogen(或目标强档)差值 ≥ +7pt(300 局的 95% CI ≈ ±3.5pt/边);<7pt 视为不可判定,**加倍样本或放弃** |
| 4 | **4p 鲁棒性** | `python -c "import pool; print(pool.fmt4('cand', pool.ffa(<agent>, [starter, pub_tactical, adilshamim], range(7000,7030))))"` | avg_rank 不差于基线 +0.2;不固定垫底(设计原则:2p/4p 同一套算法) |
| 5 | **运行时预算** | 任一局带计时(对局 500 步) | 单回合 p99 < 50ms 本地(Kaggle 限 1000ms/回合,留 20× 余量);无超时步 |
| 6 | **单文件可部署** | `python -c "import ast; ast.parse(open('agent/main.py').read())"` + 确认无第三方 import(stdlib only) | 通过;提交文件 = 烘焙后的 `agent/main.py`(env 旋钮全部取默认值)。**注:** main.py 仍是单文件可解析 + stdlib-only(`core/` import 受 guard 保护,缺失则 no-op) |
| 7 | **FlightOracle 执行门(OW-P0-FLIGHT-ORACLE-001)** | `python tests_orbit/test_action_sanitizer.py` + `OW_SANITIZE_LOG=<f>` 跑一局 | final 动作经 `core.action_sanitizer` 门控:零 strict-sun / oob 发射;v3.2 上 blocked=0(纯安全网,无回退)。**要在天梯激活**:`main.py + core/` 打成 tar.gz 提交(单文件提交时门为 no-op) |

## 方法论红线(从 T2 负结果固化,违者结论无效)

- **禁止用自博弈胜率做提交决策** —— v3 自博弈 91% 上天梯只值 +0(556→561)。一切对比走 suite/强档。
- **种子纪律**:每轮对比用全新种子块(已烧:7000-7100 suite 门、8000-8300 T2、9000-9300 T2 终局、9500-9650 / 9700-9999 T8);同配置批间波动 8-27%(24-60 局批),小样本"惊喜"默认是噪声。
- **配对种子 + 双座位**:`pool.h2h` 自动双座位;不同配置必须同种子块。
- **一次只动一个杠杆**:多杠杆同时变更无法归因;每个杠杆独立 env-gate(`OW_*`),默认 OFF,A/B 确认后才烘焙进默认值。

## 提交流程(D2 已确认,2026-06-12)

1. 上表 6 门全 PASS 且第 3 门确认提高 → 有资格提交。
2. 提交前在 issue #87 记录:版本、A/B 数据、预期天梯分、占用哪个 latest-2 槽位。
3. **最后 3 天(2026-06-20)前**:好版本尽量提交试天梯;**最后 3 天起**:冻结,选定最终 2 个最佳版本重复提交锁槽。
4. 每日 5 次提交限额;latest-2 计分 —— 提交任何版本都会挤掉现役两条目(kuni05 ~1137 / Forecast v3 ~686,分数已稳定)之一,先想清楚挤掉哪个。

## 大样本算力

- 本地 24 核:300 局 ≈ 65-75s(`--procs 22`)。
- snorlax 24 核(`ssh snorlax`,见 `docs/tooling/remote-compute-snorlax.md`):跑 ≥600 局确认轮或全 suite 大样本;纯 CPU 负载,不必动 GPU/vllm。
