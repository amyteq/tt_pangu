# Bugs — nemo

> 来源:`experiments/kernel/README.md`「Hard-won gotchas / Failure-prevention」与 worklogs。

| ID | Status | Severity | Area | Summary | Evidence | Next action |
|---|---|---|---|---|---|---|
| B1 | fixed | high | kernel-runtime | ptxas-blackwell 在只读挂载不可执行,bundled Triton 忽略 `TRITON_PTXAS_PATH` | kernel/README.md | 复制到 /tmp + chmod +x + 设 `TRITON_PTXAS_BLACKWELL_PATH` + monkeypatch |
| B2 | fixed | medium | data-path | Kaggle 数据挂载在 `/kaggle/input/competitions/<slug>/` | kernel/README.md | 用 glob 解析,勿硬编码 |
| B3 | fixed | medium | kernel-runtime | `apply_chat_template(return_tensors="pt")` 可能返回无 `.shape` 的 `BatchEncoding` | kernel/README.md | `return_dict=True` 并取 `["input_ids"]` |
| B4 | fixed | high | training | v6:loss 覆盖 prompt+padding(应 response-only)→ 0.44 | kernel/README.md | 改 response-only masking(v7 → 0.65) |
| B5 | fixed | high | lint | v7 `texts` NameError(F821);v8 `.shape` 运行期错误 各耗 ~2h GPU | kernel/README.md | push gate `ruff` F821 + fail-fast 单样本预检 |
| B6 | open | medium | quality | cryptarithm 类正确率偏低(瓶颈) | worklogs/nemo2.md;PR #95 | v15 cryptarithm-weighted synth 验证中 |
