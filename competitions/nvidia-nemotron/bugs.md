# Bugs — nemo

> Sources: issue #86 (Table 2 / comments), `kernels/README.md`.

| ID | Status | Severity | Area | Summary | Evidence | Next action |
|---|---|---|---|---|---|---|
| B1 | fixed | high | data/truncation | seq2048 **right-truncation** removed the trailing `</think>\n\boxed{}` supervision → model "thinks but never closes" → LB 0.42 (below base) | issue #86 T2 / comment 0 | truncation cap must cover corpus length (seq8192); or filter long / keep-tail-trunc |
| B2 | fixed | high | training | v6 loss over prompt+padding (no response-only masking) → 0.44 | issue #86; kernel README | response-only masking (labels=-100 on prompt) |
| B3 | fixed | high | kernel-runtime | v14 v1 fail-fast: `apply_chat_template(tokenize=True)` returned `BatchEncoding` → len() compared dict keys → 0 samples (public 0.87 notebook may never have run) | issue #86 T10 | unpack `input_ids` + first-row diagnostic |
| B4 | fixed | high | eval | held-out eval truncated generations (`EVAL_MAX_NEW=512`) → misleading local scores | issue #86 T13 | EVAL_MAX_NEW→7680 (match official) + EVAL_TIME_CAP=1800s |
| B5 | fixed | high | kernel-runtime | ptxas-blackwell non-executable on read-only mount; bundled Triton ignores `TRITON_PTXAS_PATH` | kernel README | copy to /tmp + chmod +x + `TRITON_PTXAS_BLACKWELL_PATH` + monkeypatch |
| B6 | fixed | medium | data-path | Kaggle data mounts at `/kaggle/input/competitions/<slug>/` | kernel README | resolve with a glob; never hardcode |
| B7 | fixed | medium | timeout | v9 wall-clock overrun threatened session budget | issue #86 T8 | TrainerCallback wall-clock stop + bounded eval + guaranteed save/zip |
| B8 | wontfix | medium | quality | cryptarithm single-category gains ≠ total-score gains (forum: 8%→71% single, total still ~0.86) | issue #86 T11 / comment 4 | category-weighted synth dilutes other classes; route de-prioritized |
| B9 | obsolete | low | lint | v7 `texts` NameError (F821); v8 `.shape` runtime — each cost ~2h GPU | kernel README | push gate ruff F821 + fail-fast single-example preflight (now standard) |
