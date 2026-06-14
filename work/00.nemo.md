# Q1:
请帮我一起进行 https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge 这个比赛：
- 阅读比赛 Overview, Data, Code, Models, Discussion 中的内容和热门话题/讨论
- 理解这个比赛的要求并给我详细的解释
- train.csv, test.csv 数据我已经放到 sources 中了，你可以查看
- demo.py, tinker.py, lb-score-0-86.py 是3个公开的 code，也在sources 中
- tinker.py 和 lb-score-0-86.py 本质上是一样的代码吧，都是引用别人已经训练好的模型提交评估，对吧
- 请做你认为必要的research，并给出3个你认为更好的版本(py 文件)
谢谢!

# A1:
已完成研究和脚本产出。3 个版本在这里：

* [nemotron_v1_answer_only_sft.py](sandbox:/mnt/data/nemotron_v1_answer_only_sft.py)
* [nemotron_v2_cot_rule_augmented_sft.py](sandbox:/mnt/data/nemotron_v2_cot_rule_augmented_sft.py)
* [nemotron_v3_merge_svd_submit.py](sandbox:/mnt/data/nemotron_v3_merge_svd_submit.py)
* [三个文件打包 zip](sandbox:/mnt/data/nemotron_3_versions.zip)

我已对 3 个脚本做了 Python 语法检查；没有在这里实际跑完整 30B 训练或提交 LB，所以不能保证分数，但它们比“直接打包别人 adapter”的 notebook 更适合继续迭代。

## 1. 这个比赛的本质

这是一个 **让 NVIDIA Nemotron-3-Nano-30B 推理能力变强** 的 Kaggle 竞赛。官方页面描述目标是改进 NVIDIA Nemotron open models 在新推理 benchmark 上的表现，允许探索 prompting、data pipeline、synthetic data、RL、lightweight fine-tuning 等方法。([Kaggle][1])

关键点是：**你提交的不是 `submission.csv`，而是一个 `submission.zip`，里面是兼容 NVIDIA Nemotron-3-Nano-30B 的 LoRA adapter，rank 最大 32**。官方 evaluation 页面明确要求提交 rank ≤ 32 的 LoRA adapter，并打包进 `submission.zip`。([Kaggle][2])

数据本身是一组“看例子、找隐藏规则、套用到目标”的逻辑推理题。Kaggle Data 页说数据是需要识别并应用底层 transformation rules 的 logical reasoning puzzles。([Kaggle][3]) 你给的 `train.csv` 也能看到这些任务类型：bit manipulation、unit conversion、gravity formula、encryption/decryption、Wonderland numeral、equation transformation 等。

评估方式也很重要：模型生成完整回答，metric 会抽取最终答案；官方/metric 页面显示答案如果字符串完全匹配，或数值在相对误差 `10^-2` 内，就算正确。([Kaggle][2]) 公开页面还显示评估推理参数包括 `max_tokens=7680`、`top_p=1.0`、`temperature=0.0`、`max_num_seqs=64`。([Kaggle][1]) 这说明训练时最好让 adapter 学会稳定输出 `\boxed{answer}`，而不是随意输出长文本。

截至今天，Kaggle 搜索结果显示比赛最终截止日期是 **2026-06-15 23:59 UTC**。([Kaggle][1])

## 2. 你给的数据：非常关键的发现

我直接检查了你放在 sources 里的文件：

`train.csv` 有 **9500 行**，列是 `id,prompt,answer`。`test.csv` 只有 **3 行**，列是 `id,prompt`。更重要的是，`test.csv` 的 3 个 ID：

```text
00066667
000b53cf
00189f6a
```

刚好就是 `train.csv` 的前 3 行 ID，对应答案分别是：

```text
10010111
01000011
cat imagines book
```

这一点从 `test.csv` 前三行和 `train.csv` 前三行可以直接对应起来：`test.csv` 只有这 3 个 prompt，`train.csv` 同 ID 行包含对应 answer。 

我的分类统计如下：

| 类型               |   行数 | 说明                          |
| ---------------- | ---: | --------------------------- |
| bit_manipulation | 1602 | 8-bit binary transformation |
| gravity          | 1597 | 从示例估计改过的 g，再算 `0.5*g*t^2`   |
| unit_conversion  | 1594 | 单位换算，通常近似乘法比例               |
| cipher           | 1576 | 词级替换/加密文本解码                 |
| numeral          | 1576 | 基本就是 Roman numeral          |
| equation         | 1555 | 数字/符号表达式的隐藏 transformation  |

这说明 public `test.csv` 更像是 sanity check，不应认为最终 hidden evaluation 只有这 3 条。真正目标还是训练一个能泛化到 hidden benchmark 的 LoRA adapter。

## 3. 你问的 tinker.py 和 lb-score-0-86.py：是，本质一样

你的判断是对的：**`tinker.py` 和 `lb-score-0-86.py` 本质上都是“拿别人已经训练好的 adapter/model 路径，打包成 submission.zip”，不是在 notebook 内训练。**

`lb-score-0-86.py` 里定义了一堆版本路径，例如 `version_1` 到 `version_14`，最后选择：

```python
model_path = version_14
zip_name = "submission.zip"
os.system(f'zip -r {zip_name} "{model_path}"')
```

也就是把 `/kaggle/input/models/kienngx/.../tinker-adapter/1` 打包提交。

`tinker.py` 更长，是因为它前面有 markdown 说明多个版本的训练配置，例如不同 sample 数、LoRA rank、LR、batch size、target modules 等；但最后核心逻辑仍然是选择 `version_14` 并 zip。 所以它不是“在当前 notebook 里训练”，而是“提交作者在别处训练好的 adapter”。

公开 Kaggle code 搜索结果也印证了这个方向：`Nvidia Nemotron Trained Models Submission` 显示 public/best score 0.86、V14；`[LB] [SCORE] [0.86]` 也显示打包 `kienngx/nemotron.../tinker-adapter/1`。([Kaggle][4])

## 4. demo.py 的定位

`demo.py` 是官方/公开 demo 风格的最小 LoRA adapter 示例：它下载 `metric/nemotron-3-nano-30b-a3b-bf16/transformers/default`，初始化 rank 32 的 LoRA，然后留了一个 `# model.train()` 占位，最后保存 adapter 并 zip。

所以 `demo.py` 是“提交格式/LoRA 初始化范例”，不是一个完整高分训练方案。

## 5. Discussion / 热门方向总结

我能访问到的公开讨论和 notebook 信息里，有几个重点方向：

第一，**Tinker adapter 转换、兼容性、lm_head 问题**是热门技术点。有讨论提到 Tinker 会训练 `lm_head` LoRA，而 reference adapter 不包含这个部分，需要做转换或处理；还提到要把 fused expert 权重拆到 per-expert `up_proj` 等目标模块。([Kaggle][5]) 这就是为什么我给的第 3 个脚本默认会 `drop_lm_head`，避免提交 adapter 结构和官方 evaluation loader 不兼容。

第二，**Nemotron 是 MoE/hybrid 模型，LoRA target module 的选择很关键**。讨论里有人指出 Nemotron 是 Mixture of Experts，标准 LoRA 如果训练所有 128 experts，会很重；因此大家在 target modules、专家层、训练循环上做优化。([Kaggle][6])

第三，**CoT / reasoning trace / rule solver / synthetic data 是强方向**。公开的 Progress Prize winning repo 说明它有 `reasoning.py`、`augmentation.py`、`corpus.py`、`train_sft.py`、`upload_adapter.py` 流程，还维护 Base/Synthetic/Corpus/Training/Metrics 页面来分析每题、每类、每次训练 run。([GitHub][7]) 另一个讨论片段提到目标 score 约 0.877，winning solution 训练 token 约 27,850,703。([Kaggle][5])

第四，公开 notebook 中已经有 `0.85~0.86` 的 adapter submission；再往上走，靠的通常不是单纯改 zip，而是：更好的训练语料、更一致的 `\boxed{}` 格式、更稳定的 reasoning trace、更好的 adapter merge/压缩。

## 6. 我给你的 3 个更好版本

### v1：`nemotron_v1_answer_only_sft.py`

这是最稳的 baseline：用 `train.csv` 直接做 answer-only SFT，让模型学会：

```text
prompt + “Please put your final answer inside \boxed{}”
assistant: \boxed{answer}
```

特点：

* 不依赖别人训练好的 public adapter。
* 训练时 mask prompt，只对 answer 部分算 loss。
* LoRA rank 默认 32，符合比赛限制。
* 输出 zip 根目录就是 adapter 文件，避免常见 zip 嵌套错误。
* 适合作为 sanity baseline，也适合先跑小样本确认环境。

建议先用：

```bash
MAX_TRAIN_ROWS=500 EPOCHS=1 python nemotron_v1_answer_only_sft.py
```

确认能正常生成 `submission.zip` 后，再跑全量。

### v2：`nemotron_v2_cot_rule_augmented_sft.py`

这是我最推荐你优先尝试的版本。它在 v1 基础上做了 deterministic CoT / rule-aware augmentation。

它会自动识别 6 类题：

```text
bit_manipulation
gravity
unit_conversion
cipher
numeral
equation
```

然后为不同类别生成简短 reasoning trace。例如：

* numeral：说明 Roman numeral 规则。
* gravity：从示例估算 `g`，再计算 `0.5*g*t^2`。
* unit conversion：估计比例系数。
* cipher：从示例建立词级 substitution table。
* bit/equation：生成简短“从例子归纳规则再应用”的 trace。

每条样本会有 CoT target，也会保留 answer-only target，避免模型只学会长篇废话。这个方向和 Progress Prize repo 的 reasoning/corpus/SFT 思路更接近。([GitHub][7])

推荐优先跑：

```bash
EPOCHS=1 LR=3e-5 MAX_LENGTH=1536 python nemotron_v2_cot_rule_augmented_sft.py
```

然后尝试不同 seed / LR：

```bash
SEED=1 LR=1e-5 python nemotron_v2_cot_rule_augmented_sft.py
SEED=2 LR=3e-5 python nemotron_v2_cot_rule_augmented_sft.py
SEED=3 LR=5e-5 python nemotron_v2_cot_rule_augmented_sft.py
```

### v3：`nemotron_v3_merge_svd_submit.py`

这个不是训练脚本，而是 **adapter 合并 + SVD rank 压缩 + clean packaging** 脚本。用途是：

* 你训练多个 v1/v2 adapter 后，用 v3 merge。
* 在遵守比赛规则/许可的前提下，把 public 0.86 adapter 和你自己的 adapter 做 weighted merge。
* 把合并后的 LoRA delta 用 SVD 压缩回 rank ≤ 32。
* 默认丢掉 `lm_head/modules_to_save`，规避 Tinker adapter 兼容性讨论中提到的问题。([Kaggle][5])

示例：

```bash
python nemotron_v3_merge_svd_submit.py \
  --adapters /kaggle/input/public-tinker-adapter/1 /kaggle/input/my-v2-adapter/1 \
  --weights 0.6 0.4 \
  --rank 32
```

如果你只有一个 public adapter，它也能做 clean packaging：

```bash
python nemotron_v3_merge_svd_submit.py \
  --adapters /kaggle/input/models/kienngx/nemotron-nano-30b-trained/triton/tinker-adapter/1 \
  --rank 32
```

## 7. 我的建议路线

第一步，先用 `v1` 跑 500 行，确认 Kaggle 环境、base model、Mamba/CUTLASS/PEFT 依赖都正常。

第二步，用 `v2` 全量训练。因为这个比赛的 public discussion 和 Progress Prize 方向都表明，单纯 answer-only 很难继续突破，带格式化 reasoning trace / rule-aware corpus 的 SFT 更有希望。([GitHub][7])

第三步，训练 3 到 5 个不同 seed/LR 的 `v2` adapter，用 `v3` 做 merge/SVD。优先试这些权重：

```text
0.50 / 0.30 / 0.20
uniform average
best-public 0.60 + private 0.40
best-public 0.75 + private 0.25
```

第四步，检查 `submission.zip` 根目录必须直接包含：

```text
adapter_config.json
adapter_model.safetensors
README.md  # 可有可无
```

不要出现：

```text
submission.zip/some_folder/adapter_config.json
```

这种多包一层的问题。

## 8. 最终判断

你现在给的 `tinker.py` / `lb-score-0-86.py` 可以作为 public 0.86 baseline，但它们没有真正训练，只是复用别人 adapter。想往上做，应该走这条线：

```text
规则理解数据增强
→ 带 \boxed{} 的 CoT/answer SFT
→ 多 seed / 多 LR 训练
→ adapter merge + SVD rank 32
→ clean zip 提交
```

我给你的 3 个脚本正好对应这三个阶段：baseline SFT、CoT augmented SFT、adapter merge/SVD 提交。

[1]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[2]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/overview/evaluation?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[3]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/data?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[4]: https://www.kaggle.com/code/kienngx/nvidia-nemotron-trained-models-submission/log?scriptVersionId=312218988&utm_source=chatgpt.com "Nvidia Nemotron Trained Models Submission"
[5]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[6]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/694710?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[7]: https://github.com/tonghuikang/nemotron?utm_source=chatgpt.com "Progress Prize winning submission for NVIDIA Nemotron ..."

---

# Q2:
请给我详细介绍一下[NVIDIA Nemotron Model Reasoning Challenge](https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/overview)这个比赛，你的ideas，你认为存在的挑战，以及可以提高成绩的技术和技巧!

# A2:
下面是我对 **NVIDIA Nemotron Model Reasoning Challenge** 的完整理解和参赛思路。我的总体判断是：这个比赛不是传统“预测 `test.csv` 然后交 `submission.csv`”的 Kaggle 竞赛，而是一个 **把“看例子归纳隐藏规则”的能力蒸馏进 Nemotron-3-Nano-30B LoRA adapter** 的后训练竞赛。真正的难点不是 public test 里的几行，而是 hidden evaluation 上模型能不能稳定识别规则、算对答案、并用评测器可抽取的格式输出。

## 1. 比赛本质：提交的是模型 adapter，不是答案文件

官方目标是让参赛者开发能提升 **NVIDIA Nemotron models reasoning accuracy** 的技术，可以探索 prompting、data pipeline、lightweight fine-tuning 等方法。比赛提交物是一个 `submission.zip`，其中必须包含针对 **NVIDIA Nemotron-3-Nano-30B** 的 **LoRA adapter**，而且 **LoRA rank 最大为 32**。这决定了它更像一个“受限参数预算下的推理能力后训练 / adapter compression”比赛。([Kaggle][1])

底座模型是 **Nemotron-3-Nano-30B-A3B**，NVIDIA 模型卡称它是一个 hybrid MoE 模型，能在回答前生成 reasoning trace，并且 reasoning trace 对较难问题有助于提升准确率；模型约 30B 总参数、约 3.5B active parameters。这个背景很关键：比赛天然鼓励你做“让模型学会短而准的推理轨迹 + 最终答案格式”的训练，而不只是记答案。([NVIDIA NIM APIs][2])

一句话概括：

> 你要提交的不是 solver，也不是 CSV，而是一个 rank≤32 的 LoRA，让官方评测环境里的 Nemotron 在 hidden reasoning puzzles 上答得更准。

## 2. 数据形式：看例子、找规则、套用到目标

官方 Data 页面把数据描述为 logical reasoning puzzles，需要识别并应用隐藏 transformation rules。你上传的 `train.csv` 也非常符合这个设定：每行有 `id,prompt,answer`，prompt 中给若干示例，然后要求对新的输入应用同一规则。([Kaggle][3]) 

从你给的数据和样例看，核心题型大约是 6 类：

| 题型                               | 例子                             | 本质                                   |
| -------------------------------- | ------------------------------ | ------------------------------------ |
| 8-bit bit manipulation           | `10100100 -> ?`                | 从输入输出例子归纳位运算、移位、旋转、XOR、mask、组合函数     |
| Unit conversion                  | `23.13 m becomes 33.32`        | 从示例估计比例系数，再换算目标值                     |
| Gravity                          | `d = 0.5*g*t^2`                | 从多个 `(t,d)` 反推 Wonderland 的 `g`，再算目标 |
| Cipher / decryption              | `encoded words -> plain words` | 从示例建立词级映射或字母变换，解密目标短句                |
| Wonderland numeral               | `47 -> XLVII`                  | 基本是 Roman numeral conversion         |
| Equation / symbol transformation | `81*83 = 486` 或符号串变换           | 可能是算术、拼接、逆序、替换、局部规则                  |

你上传的 `test.csv` 只有 3 行，分别是两个 bit manipulation 和一个 decryption prompt。它更像 sanity check，而不是决定成绩的真实测试集。hidden evaluation 才是核心。

## 3. 评估方式：最终答案格式非常重要

Kaggle metric 相关代码显示，评测会抽取模型输出中的 `\boxed{...}`，如果是数值答案，允许大约 `1e-2` 的相对误差；否则会做字符串匹配。另一个官方讨论/更新还提到，binary answer 的 bug 已修复，二进制答案现在按字符串匹配，而不是被误当成浮点数。([Kaggle][4])

这带来几个直接策略：

1. **训练时必须固定最终答案格式**：最后一行最好永远是 `Final answer: \boxed{...}`。
2. **二进制答案必须保留前导零**，例如 `01000011` 不能输出成 `1000011`。
3. **数值答案要按训练集风格保留两位小数**，尤其 unit conversion 和 gravity。
4. **字符串答案不要加多余引号、解释或多个候选**，因为多余输出可能影响抽取或匹配。
5. **reasoning 可以有，但最终答案必须清晰、唯一、可抽取**。

这也是为什么单纯让模型“自由解释”不安全。你要让它“可以思考，但最后必须规整落到 boxed answer”。

## 4. 公开代码的定位：demo、tinker、0.86 baseline 分别是什么

你上传的 `demo.py` 是官方/公开 demo 风格的提交骨架：它下载 `metric/nemotron-3-nano-30b-a3b-bf16/transformers/default`，设置 `LORA_RANK = 32`，构建 LoRA，留了 `# model.train()` 占位，然后保存 adapter 并 zip。也就是说，它展示的是 **如何加载底座、创建 LoRA、保存提交**，不是一个完整训练方案。

`tinker.py` 和 `lb-score-0-86.py` 的本质确实接近：它们列出多个别人已经训练好的 adapter 路径，最终选中 `version_14 = ".../tinker-adapter/1"`，然后直接 `zip -r submission.zip`。`tinker.py` 前面的 markdown 记录了不同训练版本的配置，但该 notebook 本身最后做的是“打包已有 adapter”，不是现场训练。  

公开 Kaggle code 里已经有 public/best score 约 **0.86** 的 adapter submission，所以 0.86 可以看作一个强 public baseline，但不是终点。它对我们有两个价值：第一，可以作为参照；第二，可以在规则允许和 license 合规的前提下，作为 adapter merge 的 anchor。([Kaggle][5])

## 5. 热门讨论和强方向

我看到的公开讨论里，有几个非常关键的方向。

第一，**Tinker adapter 转换和兼容性** 是重要坑点。有讨论提到 Tinker 会训练 reference adapter 没有的 `lm_head` LoRA，转换时需要处理；还涉及 MoE expert 权重从 fused 形式拆到 per-expert 形式。这说明“能在自己 notebook 里跑”的 adapter，不一定能被官方评测 loader 正确加载。([Kaggle][6])

第二，**rank≤32 是核心限制**。有讨论提到更高 rank 会让训练更稳定，但比赛限制 rank 约 32，因此挑战包括如何在很小 adapter 容量下避免 forgetting、让模型保留通用推理能力并学到这些任务格式。([Kaggle][7])

第三，**Progress Prize winning repo 的思路很像标准答案方向**：它不是只做一个 SFT notebook，而是做了 `reasoning.py → augmentation.py → corpus.py → train_sft.py → upload_adapter.py` 的完整流水线，并且有 Base/Synthetic/Corpus/Training/Metrics 页面来分析每道题、每类题、每次训练 run、token 数、loss/logprob 等。这个很重要：高分更像“数据工程 + 可验证推理轨迹 + 训练监控 + 多次实验”的结果，而不是只改一个 learning rate。([GitHub][8])

第四，NVIDIA NeMo Evaluator 文档也提醒，reasoning model 的输出可能包含 reasoning trace 和 final answer；评测或 benchmark 通常只需要 final answer，因此生成长度、reasoning trace、最终答案抽取之间要平衡。([NVIDIA Docs][9])

## 6. 我认为这个比赛真正的挑战

### 挑战 1：hidden rule generalization，而不是 train memorization

训练集里很多题是“同一大类、不同具体规则”。比如 bit manipulation 不是一个固定函数，而是每行 prompt 中有新的隐藏规则。模型必须学会“从本行示例推断规则”，而不是记住某个输入输出。随机切 train/valid 得分可能很虚，因为相似分布过强；hidden eval 可能会换参数、换符号、换组合。

### 挑战 2：bit manipulation 和 equation 类最难

Roman numeral、unit conversion、gravity、word substitution 相对容易程序化；真正拉开差距的大概率是：

* bit operation rule search；
* symbolic equation/string transformation；
* 混合规则；
* 例子数量少、规则歧义高的样本；
* 输出中有前导零、特殊字符、引号、反斜杠等容易格式错的样本。

这些类别需要更强的“从少量输入输出对中枚举/验证候选规则”的能力。

### 挑战 3：LoRA rank 32 容量有限

Nemotron 是大模型，但你只能提交低 rank adapter。训练太多样本、太多长 CoT、太高 LR，都可能让 adapter 容量被格式、废话或某些类别吃掉，导致泛化变差。低 rank 下最怕的是：训练 loss 降了，但 hidden reasoning 不涨，甚至 base model 原本会的能力被破坏。

### 挑战 4：MoE/hybrid 架构的 target modules 选择复杂

demo 里用了 `.*\.(in_proj|out_proj|up_proj|down_proj)$` 作为 target modules。公开 notebook 中又有人尝试 `all-linear`、attention/qkv/o/gate/up/down 等不同组合。Nemotron 这种 hybrid Mamba + Attention + MoE 架构，不同 target module 对训练稳定性、显存、泛化影响很大。 

### 挑战 5：public LB 容易误导

本地 `test.csv` 只有 3 行，public leaderboard 也可能不足以代表 private hidden。尤其这个比赛可以打包公开 adapter，public 0.86 baseline 很强，但你如果只围着 public LB 调，可能会过拟合公开集或别人 adapter 的行为。真正要做的是 per-category hidden robustness。

### 挑战 6：提交格式和 adapter 兼容性容易出错

很多失败不是模型能力问题，而是：

* zip 多包了一层目录；
* adapter config 路径不对；
* safetensors key 和官方 loader 不匹配；
* Tinker adapter 包含不兼容 `lm_head`；
* rank 超限；
* target module 名称和 base model 不匹配。

这类错误一旦发生，分数可能直接归零。

## 7. 我的核心 ideas

### Idea A：把比赛拆成“可程序化规则求解 → 蒸馏给模型”

这类题大量是可程序化求解的。最强思路不是直接让大模型从 9500 条里硬学，而是先写 deterministic solvers / parsers：

```text
prompt
  → 识别题型
  → 提取 examples 和 target
  → 枚举/拟合候选规则
  → 验证候选规则是否能解释 examples
  → 得到 answer
  → 生成简短 verified reasoning trace
  → 用于 SFT / RL
```

这相当于用程序生成“老师答案”和“老师推理轨迹”，再把它蒸馏进 rank≤32 adapter。Progress Prize repo 的 `reasoning.py`、`augmentation.py`、`corpus.py` 路线也支持这个方向。([GitHub][8])

### Idea B：不要只做 answer-only，也不要只做长 CoT

我建议训练语料混合三种格式：

```text
1. answer-only:
   \boxed{answer}

2. short reasoning:
   Identify the rule ...
   Apply it to target ...
   Final answer: \boxed{answer}

3. category-specific reasoning:
   For gravity/unit conversion/cipher/Roman numeral，用非常短的固定模板解释。
```

比例上可以从：

```text
40% answer-only
50% short verified reasoning
10% noisy/robust formatting examples
```

开始试。answer-only 保证格式；reasoning trace 提高 hidden generalization；少量 noisy examples 让模型在 prompt 变化时不崩。

### Idea C：每个题型单独做 solver 和 synthetic generator

最值得投入的是生成高质量 synthetic data，而不是盲目扩充相似文本。

建议这样做：

| 题型               | 可做增强                                                                                      |
| ---------------- | ----------------------------------------------------------------------------------------- |
| Roman numeral    | 覆盖 1–3999，但比赛里多为 1–100；训练时重点 1–100                                                        |
| Unit conversion  | 随机比例系数，3–6 个 examples，目标值，统一两位小数                                                          |
| Gravity          | 随机 g，采样 t，生成 d，加入少量四舍五入误差                                                                 |
| Cipher           | 从固定词表生成句子，随机 substitution，确保 examples 覆盖 target 词                                         |
| Bit manipulation | 枚举操作库：shift、rotate、xor const、and/or mask、not、bit reverse、nibble swap、majority/choice、组合两步 |
| Equation/symbol  | 枚举算术/拼接/逆序/符号替换/局部 rewrite templates                                                      |

关键是 **synthetic 必须可验证**：每个样本生成后，用 solver 反跑一遍，只有 solver 能稳定得到 answer 的样本才进训练集。

### Idea D：bit manipulation 要做候选函数枚举

bit 类可以程序化做得很强。构造一个函数库：

```text
identity(x)
not(x)
x << k
x >> k
rotl(x,k)
rotr(x,k)
x xor c
x and c
x or c
reverse_bits(x)
swap_nibbles(x)
popcount-derived masks
majority(x, rotl(x,a), rotr(x,b))
choice(x, a, b)
两步组合：f(g(x))
```

对每行 prompt：

```text
给定 examples: xi -> yi
枚举候选函数 f
保留所有满足 f(xi)=yi 的函数
如果唯一，直接得到 target answer
如果多个，按简单度排序，生成 explanation
```

这个 solver 的输出可以成为 bit 类的 verified reasoning data。hidden eval 如果题型同源，这会明显提高模型归纳能力。

### Idea E：equation/symbol transformation 要分两套处理

Equation 类有两种明显形态：

1. **数字 + 运算符**：例如 `81*83 = 486`、`98^14 = 9814`。这里可能是加减乘、差值、拼接、逆序、取绝对值、组合等。
2. **纯符号串 rewrite**：例如奇怪符号序列映射。这里更像局部替换、删除、重排、字符级规则。

数字类可以做 arithmetic template search；符号类可以做 string transduction / rewrite rule search，例如：

```text
- 删除某个位置
- 交换位置
- 反转
- 替换某些字符
- 保留某些字符
- n-gram rewrite
- 输入输出字符对齐
```

训练时最好把这两类显式标注成不同 reasoning 模板，而不是都叫 equation。

### Idea F：用 local CV 做 per-category scoreboard

不要只看总体 loss，也不要只看 public LB。建议建立本地验证：

```text
split by category
split by prompt template / generated rule
split by answer type: binary / numeric / string / symbol
```

每次训练记录：

```text
overall exact match
bit exact match
equation exact match
cipher exact match
numeric tolerance accuracy
boxed extraction success rate
average output tokens
invalid format rate
```

其中 **boxed extraction success rate** 非常关键。如果模型答对但格式错，Kaggle 仍然可能判错。

## 8. 可以提高成绩的具体技术和技巧

### 8.1 训练数据技巧

第一，做 **category balancing**。训练集各类数量接近，但难度不一样。Roman numeral 很容易，过多训练会浪费 adapter 容量；bit/equation 更难，应该适当 oversample。我的初始建议：

```text
bit: 1.5x–2.0x
equation: 1.5x–2.0x
cipher: 1.0x
gravity: 0.7x
unit conversion: 0.7x
Roman numeral: 0.3x–0.5x
```

第二，做 **answer format augmentation**，但最终格式统一。例如训练中可以有不同 prompt instruction，但 completion 永远统一：

```text
Final answer: \boxed{...}
```

第三，做 **verified CoT filtering**。不要让 LLM 自己胡编 reasoning trace。每条 reasoning trace 必须由 solver 或规则验证过，否则会教坏模型。

第四，做 **hard negative / ambiguity examples**。尤其 bit/equation：如果有多个候选规则能解释 examples，训练 trace 里要强调“choose the simplest consistent rule”或“use the rule implied by all examples”。这能减少模型过度复杂化。

### 8.2 LoRA 训练技巧

我会从以下配置区间试起：

```text
rank: 32
alpha: 32 或 64
dropout: 0.03–0.05
LR: 1e-5, 3e-5, 5e-5 三档
epochs: 1–2
max_length: 1536 / 2048 / 4096 对比
batch size: 1–2
grad accumulation: 8–16
dtype: bf16
```

公开代码里有人记录过 `lr=1e-5/5e-5/1e-4`、batch size、grad accumulation、target modules 等版本，所以这些区间是合理的实验起点。

target modules 我会做三组 ablation：

```text
A. demo-style:
   .*\.(in_proj|out_proj|up_proj|down_proj)$

B. MLP/attention broader:
   q/k/v/o + gate/up/down 或 all-linear

C. conservative:
   attention + shared/common projections only，少碰 expert-heavy modules
```

目标不是 train loss 最低，而是 hidden-like validation 最好、输出格式最稳、adapter 兼容性最高。

### 8.3 Loss 和格式技巧

训练时应该 **mask prompt loss，只对 assistant completion 算 loss**。否则模型会浪费容量学习复述 prompt。

可以考虑对 completion 做 token weighting：

```text
reasoning tokens: normal weight
final answer tokens: higher weight
boxed answer delimiters: higher weight
```

如果实现复杂，至少保证每条 completion 最后都有完全一致的 final answer 模板。

对于数值答案：

```text
gravity/unit conversion:
  round to 2 decimals
  不要输出单位，除非 answer 本身带单位
```

对于 binary：

```text
永远 8 位
保留 leading zeros
不要解释成 decimal
```

对于 cipher：

```text
全小写
单词间单空格
不要加句号
```

对于 symbol equation：

```text
严格原样输出
保留引号、反斜杠、特殊符号
避免 markdown escape 改写
```

### 8.4 Adapter merge / SVD 技巧

由于 rank≤32，单个训练 run 很容易偏科。更好的路线是训练多个 adapter：

```text
adapter A: answer-only / format strong
adapter B: verified CoT / reasoning strong
adapter C: bit+equation oversampled
adapter D: synthetic-heavy
adapter E: public 0.86 adapter anchor，若规则和许可允许
```

然后做 LoRA delta merge，再 SVD 压回 rank 32。权重可以试：

```text
uniform average
0.5 reasoning + 0.3 format + 0.2 hard-category
0.6 public anchor + 0.4 own adapter
0.75 public anchor + 0.25 own adapter
```

这类方法的核心是让不同 adapter 的强项互补，同时不违反 rank 限制。注意 Tinker adapter 可能有 `lm_head` 或 fused expert key 的兼容性问题，merge 前要清理不兼容权重。([Kaggle][6])

### 8.5 RL / GRPO 技巧

这个比赛很适合做小规模 RL，因为 reward 可验证：

```text
reward = exact_match_or_numeric_tolerance
format_reward = boxed answer exists
length_penalty = 避免过长输出
invalid_penalty = 多个 boxed / 无 boxed / 改掉 leading zeros
```

但我不建议一开始就 RL。正确顺序是：

```text
strong SFT
→ local metric 稳定
→ small synthetic RL
→ merge/SVD
```

如果 SFT 还不稳，RL 很可能只是放大错误格式或让模型过拟合 synthetic generator。

## 9. 我推荐的参赛路线

### 阶段 1：建立可靠 local metric 和分类器

先写一个本地 evaluator，复制官方 boxed extraction 和 numeric tolerance 逻辑。每个样本先分类为：

```text
bit / unit / gravity / cipher / numeral / equation_numeric / equation_symbol
```

输出 per-category score。这个阶段的目标不是训练，而是能判断每次实验到底哪里涨、哪里跌。

### 阶段 2：answer-only SFT baseline

用 train.csv 做最小训练：

```text
Prompt: 原 prompt + “Put final answer in \boxed{}.”
Target: Final answer: \boxed{answer}
```

这会让模型先学会提交格式和答案风格。分数不一定最高，但它是所有后续实验的 sanity baseline。

### 阶段 3：verified short reasoning SFT

对每类题生成短推理轨迹：

```text
Gravity:
Estimate g from examples, then compute 0.5*g*t^2.
Final answer: \boxed{...}

Unit:
Estimate conversion factor from examples, apply to target.
Final answer: \boxed{...}

Cipher:
Build word mapping from examples, decode target phrase.
Final answer: \boxed{...}
```

bit/equation 则使用 solver 枚举出的规则描述，无法验证的样本只做 answer-only，不要硬编 trace。

### 阶段 4：synthetic hard-category augmentation

重点扩充 bit 和 equation。我的建议是先做小规模：

```text
20k synthetic bit
20k synthetic equation
10k cipher
5k gravity
5k unit
2k numeral
```

训练后看 per-category validation。如果 bit/equation 涨而其他类掉，再调采样权重和 merge。

### 阶段 5：多 seed / 多 LR / 多数据配比训练

至少跑：

```text
seed 1, LR 1e-5
seed 2, LR 3e-5
seed 3, LR 5e-5
hard-category oversample
answer-only-heavy
reasoning-heavy
```

每个 adapter 保留 validation report，不要只看 LB。

### 阶段 6：adapter merge + rank 32 SVD

把表现互补的 adapter 合并，再压回 rank 32。最后做提交包检查：

```text
submission.zip
  adapter_config.json
  adapter_model.safetensors
  README.md  # optional
```

不要让 zip 里出现：

```text
some/path/adapter_config.json
```

这种多嵌套路径。

## 10. 我最看好的 5 个提分点

**第一，verified CoT 比纯 answer-only 更可能涨 hidden。** 因为 hidden 题本质要求 rule induction，而不是记忆 answer style。

**第二，bit/equation solver-generated synthetic data 是最大杠杆。** Roman/unit/gravity/cipher 都相对容易，真正差距大概率来自 bit/equation。

**第三，输出格式训练会带来“白捡”的分数。** `\boxed{}`、leading zeros、两位小数、无多余解释，这些很容易被忽视，但对 metric 非常关键。

**第四，adapter merge 可能比单次训练更稳。** rank 32 限制下，单 adapter 容量有限，多 adapter 的 delta merge + SVD 是值得做的。

**第五，per-category validation 比 public LB 更重要。** public 0.86 baseline 很强，但 public signal 可能有限；真正要优化 hidden robustness。

## 11. 一个具体实验矩阵

我会按这个顺序跑：

| 实验 | 数据                                 | 训练                    | 目的              |
| -- | ---------------------------------- | --------------------- | --------------- |
| E0 | public 0.86 adapter                | 不训练                   | 建立 baseline     |
| E1 | train answer-only                  | LoRA rank 32, LR 3e-5 | 格式和 sanity      |
| E2 | train + verified short reasoning   | LR 1e-5 / 3e-5        | 看 reasoning 是否涨 |
| E3 | E2 + bit synthetic                 | oversample bit        | 攻 bit 类         |
| E4 | E2 + equation synthetic            | oversample equation   | 攻 equation 类    |
| E5 | E3 + E4 balanced                   | 多 seed                | 综合 adapter      |
| E6 | public adapter + own adapter merge | SVD rank 32           | 冲 LB            |
| E7 | small RL on verified synthetic     | reward exact match    | 最后冲刺            |

最终提交我倾向于：

```text
best_public_anchor 0.5–0.7
own_verified_cot_adapter 0.2–0.4
own_hard_category_adapter 0.1–0.2
→ merge
→ SVD rank 32
→ clean zip
```

前提是公开 adapter 的使用符合比赛规则和作者 license。

## 12. 最终策略总结

这个比赛的最佳路线不是“找一个公开 notebook 改几个参数”，而是：

```text
理解 6 类 puzzle
→ 写 parser/solver
→ 生成 verified answers 和 short reasoning traces
→ category-balanced SFT
→ hard-category synthetic augmentation
→ 严格 final-answer formatting
→ 多 seed / 多 LR adapter
→ merge + SVD rank 32
→ clean submission.zip
```

我认为最有希望超过普通 public baseline 的方向是：

> **规则求解器 + verified reasoning corpus + hard-category synthetic data + adapter merge。**

如果只提交 `tinker.py` / `lb-score-0-86.py` 那类已有 adapter，能得到一个不错起点；但想继续提高，关键在于让自己的 adapter 在 hidden bit/equation/cipher 规则归纳上真正更强，同时不破坏 `\boxed{}` 输出稳定性。

[1]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[2]: https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b/modelcard "nemotron-3-nano-30b-a3b Model by NVIDIA | NVIDIA NIM"
[3]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/data?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[4]: https://www.kaggle.com/code/metric/nvidia-nemotron-metric?utm_source=chatgpt.com "NVIDIA Nemotron Metric"
[5]: https://www.kaggle.com/code/safar1/lb-score-0-86?utm_source=chatgpt.com "[LB] [SCORE] [0.86]"
[6]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[7]: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/703240?utm_source=chatgpt.com "NVIDIA Nemotron Model Reasoning Challenge"
[8]: https://github.com/tonghuikang/nemotron "GitHub - tonghuikang/nemotron: Progress Prize winning submission for NVIDIA Nemotron Model Reasoning Challenge · GitHub"
[9]: https://docs.nvidia.com/nemo/evaluator/latest/evaluation/run-evals/reasoning.html "Evaluation of Reasoning Models — NeMo Evaluator SDK"
