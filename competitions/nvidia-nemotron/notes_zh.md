# Notes (中文存档 / zh sidecar)

> 重要中文原始材料的存档与指引。英文规范结论已并入 `strategy.md` / `insights.md` / `bugs.md`。
> 原始长文档不改写,仅链接(见 `references.md`)。

## 原始来源(请勿在此改写,链接见 references.md)
- GitHub issue #86 — 策略与追踪 Hub(三表 inline 更新)。
- `worklogs/nemo.md`、`worklogs/nemo2.md` — 中文工作日志镜像。
- `work/00.nemo.md` — ChatGPT 比赛分析 Q&A(中文):比赛本质、数据发现(test.csv≈train 前 3 行)、
  6 大挑战(hidden-rule 泛化 / bit & equation 最难 / rank32 容量 / MoE target 选择 / public LB 误导 /
  adapter 兼容)、ideas A–F(规则求解蒸馏 / answer+CoT 混合 / 逐题型 solver / bit 枚举 /
  equation 双套 / per-category local CV)、训练与 LoRA 技巧。
- `work/00.nemotron_3_versions.zip` — 3 个 ChatGPT 脚本(v1 answer-only / v2 cot-rule / v3 merge-svd)。

## 关键中文结论摘录(issue #86 comments,逐字)
> v14 replay = LB 0.85(comment 2):
「公开 0.86/0.87 "replay" 配方**成功复刻**(真实训练 fresh rank-32 LoRA,非 repack,合规)。
关键技术:Cut Cross-Entropy + MoE 128 专家权重 tying + target 含 lm_head/in_proj/out_proj(Mamba)+
seq8192 + huikang 录制顺序语料 + replay-math 2M answer tokens;254/254 步,final loss ~0.05。」

> 两次冲 0.85+ 的总结(comment 4):
「T7 多 adapter SVD merge = 0.82(−0.03);T11 cryptarithm 合成数据 = 0.84(−0.01)。
规律一致:**任何对 v14 干净 replay 配方的「增补」都在稀释它**。建议:守住 0.85 收官。」

## 合规红线(issue #86)
rank≤32;真实训练(不 repack);双账号 = 真实注册队友(只买并发 session,提交共享 per-team/day);
不打印/提交 credentials。
