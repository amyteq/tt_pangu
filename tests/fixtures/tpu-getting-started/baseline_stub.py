# %% [markdown]
# # Petals to the Metal — dry-run stub notebook
#
# A *tiny* shape-only stand-in for the real M10-T002 transfer-learning
# baseline (`runs/tpu-getting-started/baseline-tl/baseline.ipynb`). The real
# notebook trains MobileNetV2 on 104-class TFRecords and cannot run in CI; this
# stub exists purely so `tests/test_m10_e2e.py` can exercise the
# `kca nb to-ipynb` / `kca nb to-py` round-trip and produce a valid
# `submission.csv` shape (`id,label`) without TensorFlow, GPU, or network.

# %%
SEED = 42
NUM_CLASSES = 104
COMPETITION = "tpu-getting-started"

# %% [markdown]
# ## Deterministic stub "predictions"
#
# Stand in for `model.predict(...).argmax(axis=1)`: a fixed id->label mapping so
# the round-trip is byte-stable and the submission shape matches Kaggle's
# `id,label` schema for Petals to the Metal.

# %%
import csv  # noqa: E402  (percent-format notebook: import follows a code cell by design)

STUB_TEST_IDS = [f"flower_{i:04d}" for i in range(8)]


def stub_predict(test_ids):
    # Deterministic pseudo-labels in [0, NUM_CLASSES).
    return [(hash(tid) % NUM_CLASSES) for tid in test_ids]


def write_submission(path, test_ids):
    preds = stub_predict(test_ids)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "label"])
        for tid, label in zip(test_ids, preds):
            w.writerow([tid, int(label)])
    return len(test_ids)


# %% [markdown]
# ## Defense-in-depth
#
# This notebook NEVER calls `kaggle kernels push` from any cell — kernel pushing
# is gated through `kca kaggle push` (M10-T004), never inline.

# %%
print("petals dry-run stub OK")
