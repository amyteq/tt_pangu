# tpu-getting-started experiments

Deliberate, committed Kaggle-kernel artifacts for the **Petals to the Metal — Flower Classification on TPU** competition (`tpu-getting-started`).

## Layout

```
experiments/tpu-getting-started/
├── baseline-tl/          MobileNetV2 transfer-learning baseline (M10-T002)
│   ├── baseline.py           ← source of truth (percent-format Python)
│   ├── baseline.ipynb        ← derived from baseline.py via `kca nb to-ipynb`
│   └── kernel-metadata.json  ← Kaggle push manifest
└── alt-backbone-v1/      EfficientNetB0 single-axis variant (M10-T005)
    ├── baseline.py
    ├── baseline.ipynb
    └── kernel-metadata.json
```

## Workflow

`baseline.py` is the source of truth. Whenever you edit it, regenerate the notebook:

```bash
PYTHONPATH=tools/kca python3 tools/kca/kca.py nb to-ipynb \
  experiments/tpu-getting-started/baseline-tl/baseline.py \
  --output experiments/tpu-getting-started/baseline-tl/baseline.ipynb \
  --keep-markdown --json
```

Push to Kaggle (gated):

```bash
kca kaggle push --kernel-dir experiments/tpu-getting-started/baseline-tl --json
```

Read the public LB score back after the kernel run completes:

```bash
kca kaggle score --competition tpu-getting-started \
  --kernel-ref harrysun2006/petals-baseline-tl --json
```

## Transient run state

Local-training metrics, logs, and any non-committed artifacts live under `runs/tpu-getting-started/<run_id>/` (gitignored). Only the files in this directory are versioned.
