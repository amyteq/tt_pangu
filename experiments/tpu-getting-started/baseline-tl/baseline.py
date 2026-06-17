# %% [markdown]
# # Petals to the Metal — baseline (transfer learning)
#
# M10-T002 baseline for the
# [Petals to the Metal — Flower Classification on TPU](https://www.kaggle.com/competitions/tpu-getting-started)
# competition.
#
# - **Backbone:** `MobileNetV2` pretrained on ImageNet (small, fast — sanity baseline, not a leaderboard chaser).
# - **Image size:** 192x192 (smallest published variant).
# - **Optimizer / epochs:** Adam (default LR), 3 epochs for local sanity (TPU kernel may train longer; see `EPOCHS` constant).
# - **Seed:** 42.
# - **Split:** Kaggle ships `train/` and `val/` TFRecord splits separately — we use them as-is (holdout accuracy on `val/`).
#
# When executed on Kaggle's kernel runner, this notebook reads TFRecords from the GCS path exposed by
# `kaggle_datasets.KaggleDatasets().get_gcs_path('tpu-getting-started')`. When executed locally
# (e.g. via `jupyter nbconvert --to notebook --execute`), it falls back to the local slice at
# `data/tpu-getting-started/local-slice/{train,val}/*.tfrec` that M10-T002 staged for sanity.
#
# **Defense-in-depth:** this notebook does NOT call `kaggle kernels push` from any cell. Kernel pushing
# happens via `kca kaggle push` in M10-T004, never from inside the notebook itself.

# %%
import collections
import random
import time
from pathlib import Path

import numpy as np
import tensorflow as tf

# %% [markdown]
# ## Configuration

# %%
SEED = 42
IMAGE_SIZE = (192, 192)
NUM_CLASSES = 104
BATCH_SIZE = 32  # small for local CPU; Kaggle kernel can override
EPOCHS = 3  # local sanity: 3; Kaggle kernel runner may bump (see KERNEL_EPOCHS)
KERNEL_EPOCHS = 5  # used when running on Kaggle infra (see strategy block below)
COMPETITION = "tpu-getting-started"

random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

# %% [markdown]
# ## Resolve data paths
#
# Try Kaggle's GCS-backed dataset path first (kernel runner). Fall back to the local M10-T002 slice.


# %%
def _resolve_gcs_path() -> str | None:
    try:
        from kaggle_datasets import KaggleDatasets  # type: ignore

        return KaggleDatasets().get_gcs_path(COMPETITION)
    except Exception as exc:
        print(f"[data-resolve] kaggle_datasets GCS path unavailable: {exc!r}")
        return None


def _resolve_kaggle_input_path() -> str | None:
    # Try the direct competition mount first, then the /competitions/<slug>/ layout
    # Kaggle uses for "official" Getting Started competitions (v3 diagnostic showed
    # /kaggle/input had only ['competitions'], not the slug directly).
    candidates = [
        Path("/kaggle/input") / COMPETITION,
        Path("/kaggle/input/competitions") / COMPETITION,
    ]
    for p in candidates:
        if p.exists():
            print(f"[data-resolve] /kaggle/input mount found at {p}")
            return str(p)
    # Diagnostic: list what IS under /kaggle/input/ so a future failure shows
    # the real layout instead of an opaque "not found".
    root = Path("/kaggle/input")
    if root.exists():
        try:
            print(f"[data-resolve] /kaggle/input contents: {sorted(p.name for p in root.iterdir())}")
            comp_root = root / "competitions"
            if comp_root.exists():
                print(
                    f"[data-resolve] /kaggle/input/competitions contents: {sorted(p.name for p in comp_root.iterdir())}"
                )
        except Exception as exc:
            print(f"[data-resolve] /kaggle/input listdir failed: {exc!r}")
    else:
        print("[data-resolve] /kaggle/input does not exist")
    return None


def _resolve_local_slice() -> str | None:
    # When this notebook is executed locally from the repo root.
    for candidate in [
        Path.cwd() / "data" / COMPETITION / "local-slice",
        Path("/home/harry/test/tt_pangu/.claude/worktrees/m10-petals-to-the-metal/data") / COMPETITION / "local-slice",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def _has_tfrecord_subdir(root: str, subdir: str) -> bool:
    # Validate that a resolver-returned `root` actually contains the expected
    # TFRecord layout. v4 errored because GCS resolver returned a path that
    # didn't contain the shards (Kaggle TPU shortcut to the wrong mount).
    try:
        check = f"{root}/{subdir}/train"
        return tf.io.gfile.exists(check)
    except Exception:
        return False


_SUBDIR = f"tfrecords-jpeg-{IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}"

# Order matters: prefer the explicit /kaggle/input/competitions/<slug>/ mount
# (validated by _has_tfrecord_subdir) over the GCS shortcut, then fall back to
# the GCS path, then a local slice for off-Kaggle execution.
DATA_ROOT, DATA_SUBDIR, RUNTIME = None, None, None
for label, candidate in (
    ("kaggle-input", _resolve_kaggle_input_path()),
    ("kaggle-tpu-gcs", _resolve_gcs_path()),
):
    if candidate and _has_tfrecord_subdir(candidate, _SUBDIR):
        DATA_ROOT, DATA_SUBDIR, RUNTIME = candidate, _SUBDIR, label
        print(f"[data-resolve] accepted {label} root={candidate}")
        break
    elif candidate:
        print(f"[data-resolve] rejected {label} root={candidate} — {_SUBDIR}/train not present")

if DATA_ROOT is None:
    local = _resolve_local_slice()
    if local:
        DATA_ROOT, DATA_SUBDIR, RUNTIME = local, "", "local-slice"

if DATA_ROOT is None:
    raise RuntimeError(
        "No data source resolved: no Kaggle mount contains "
        f"{_SUBDIR}/train, and no local slice is present. "
        "Run scripts/m10_t002_download_slice.py to stage a local slice."
    )

print(f"runtime={RUNTIME} data_root={DATA_ROOT} subdir={DATA_SUBDIR!r}")

# %% [markdown]
# ## TFRecord decoding

# %%
LABELED_TFREC_FORMAT = {
    "image": tf.io.FixedLenFeature([], tf.string),
    "class": tf.io.FixedLenFeature([], tf.int64),
}

UNLABELED_TFREC_FORMAT = {
    "image": tf.io.FixedLenFeature([], tf.string),
    "id": tf.io.FixedLenFeature([], tf.string),
}


def decode_image(image_bytes):
    image = tf.image.decode_jpeg(image_bytes, channels=3)
    image = tf.image.resize(image, IMAGE_SIZE)
    image = tf.cast(image, tf.float32) / 255.0
    image = tf.reshape(image, [*IMAGE_SIZE, 3])
    return image


def read_labeled_tfrecord(example):
    parsed = tf.io.parse_single_example(example, LABELED_TFREC_FORMAT)
    return decode_image(parsed["image"]), tf.cast(parsed["class"], tf.int32)


def read_unlabeled_tfrecord(example):
    parsed = tf.io.parse_single_example(example, UNLABELED_TFREC_FORMAT)
    return decode_image(parsed["image"]), parsed["id"]


def _split_glob(split: str) -> str:
    if DATA_SUBDIR:
        return f"{DATA_ROOT}/{DATA_SUBDIR}/{split}/*.tfrec"
    return f"{DATA_ROOT}/{split}/*.tfrec"


def load_dataset(split: str, labeled: bool):
    files = tf.io.gfile.glob(_split_glob(split))
    if not files:
        raise RuntimeError(f"No TFRecords found for split={split} glob={_split_glob(split)}")
    ds = tf.data.TFRecordDataset(files, num_parallel_reads=tf.data.AUTOTUNE)
    ds = ds.with_options(tf.data.Options())
    ds = ds.map(
        read_labeled_tfrecord if labeled else read_unlabeled_tfrecord,
        num_parallel_calls=tf.data.AUTOTUNE,
    )
    return ds


def get_training_dataset():
    ds = load_dataset("train", labeled=True)
    ds = ds.repeat()
    ds = ds.shuffle(2048, seed=SEED)
    ds = ds.batch(BATCH_SIZE, drop_remainder=True)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds


def get_validation_dataset():
    ds = load_dataset("val", labeled=True)
    ds = ds.batch(BATCH_SIZE)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds


def get_test_dataset():
    ds = load_dataset("test", labeled=False)
    ds = ds.batch(BATCH_SIZE)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds


# %% [markdown]
# ## Dataset sizing
#
# Petals to the Metal's TFRecord filenames embed the per-shard count (e.g. `00-192x192-798.tfrec` = 798 examples).
# We extract that to know `steps_per_epoch` without iterating the whole dataset.


# %%
def count_data_items(filenames):
    import re

    total = 0
    for fn in filenames:
        m = re.search(r"-(\d+)\.tfrec$", fn)
        if m:
            total += int(m.group(1))
    return total


train_files = tf.io.gfile.glob(_split_glob("train"))
val_files = tf.io.gfile.glob(_split_glob("val"))

NUM_TRAINING_IMAGES = count_data_items(train_files)
NUM_VALIDATION_IMAGES = count_data_items(val_files)
STEPS_PER_EPOCH = max(1, NUM_TRAINING_IMAGES // BATCH_SIZE)

print(
    f"train shards={len(train_files)} train_images={NUM_TRAINING_IMAGES} "
    f"val shards={len(val_files)} val_images={NUM_VALIDATION_IMAGES} "
    f"steps_per_epoch={STEPS_PER_EPOCH}"
)

# Fail loudly if the resolver pointed at an empty path — v3 silently trained on
# zero shards because we trusted the resolver's word. Catch that here.
if len(train_files) == 0 or len(val_files) == 0:
    raise RuntimeError(
        f"Zero TFRecords resolved at {DATA_ROOT}/{DATA_SUBDIR or '<root>'}/{{train,val}}/*.tfrec — "
        f"train_files={len(train_files)} val_files={len(val_files)}. "
        f"The resolver returned a path that does not contain the expected shards; "
        f"investigate the /kaggle/input layout (see earlier [data-resolve] prints) "
        f"before pushing again."
    )

# %% [markdown]
# ## Strategy (TPU vs GPU/CPU)

# %%
try:
    tpu = tf.distribute.cluster_resolver.TPUClusterResolver.connect()
    strategy = tf.distribute.TPUStrategy(tpu)
    print(f"strategy=TPU replicas={strategy.num_replicas_in_sync}")
    EPOCHS = KERNEL_EPOCHS
except (ValueError, tf.errors.NotFoundError, Exception):
    strategy = tf.distribute.get_strategy()
    print(f"strategy=default replicas={strategy.num_replicas_in_sync}")

# %% [markdown]
# ## Model


# %%
def build_model():
    base = tf.keras.applications.MobileNetV2(
        input_shape=[*IMAGE_SIZE, 3],
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False
    model = tf.keras.Sequential(
        [
            base,
            tf.keras.layers.GlobalAveragePooling2D(),
            tf.keras.layers.Dense(NUM_CLASSES, activation="softmax"),
        ],
        name="petals_baseline_mobilenetv2",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )
    return model


with strategy.scope():
    model = build_model()

model.summary()

# %% [markdown]
# ## Train

# %%
t0 = time.time()
model.fit(
    get_training_dataset(),
    steps_per_epoch=STEPS_PER_EPOCH,
    epochs=EPOCHS,
    validation_data=get_validation_dataset(),
    verbose=2,
)
train_seconds = time.time() - t0
print(f"train_seconds={train_seconds:.1f}")

# %% [markdown]
# ## Holdout accuracy

# %%
val_loss, val_acc = model.evaluate(get_validation_dataset(), verbose=0)
print(f"holdout_accuracy={val_acc:.4f} val_loss={val_loss:.4f}")

# %% [markdown]
# ## Macro F1 on holdout
#
# Petals to the Metal scores submissions on macro F1; we record both holdout accuracy AND macro F1 locally.

# %%
per_class_tp = collections.Counter()
per_class_fp = collections.Counter()
per_class_fn = collections.Counter()

for batch_images, batch_labels in get_validation_dataset():
    preds = model.predict(batch_images, verbose=0).argmax(axis=1)
    labels = batch_labels.numpy()
    for y, p in zip(labels, preds):
        if y == p:
            per_class_tp[int(y)] += 1
        else:
            per_class_fp[int(p)] += 1
            per_class_fn[int(y)] += 1

f1s = []
for cls in range(NUM_CLASSES):
    tp = per_class_tp[cls]
    fp = per_class_fp[cls]
    fn = per_class_fn[cls]
    if tp + fp == 0 or tp + fn == 0:
        f1s.append(0.0)
        continue
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    if precision + recall == 0:
        f1s.append(0.0)
    else:
        f1s.append(2 * precision * recall / (precision + recall))

macro_f1 = float(np.mean(f1s))
print(f"macro_f1={macro_f1:.4f}")

# %% [markdown]
# ## Test-set inference + submission.csv
#
# On Kaggle's kernel runner this writes `/kaggle/working/submission.csv` (the kernel push artifact).
# Locally we skip test-set inference unless the local slice contains a `test/` directory (it does not by default).

# %%
try:
    test_files = tf.io.gfile.glob(_split_glob("test"))
except Exception:
    test_files = []

if test_files:
    test_ds = get_test_dataset()
    test_images_ds = test_ds.map(lambda image, idnum: image)
    test_ids_ds = test_ds.map(lambda image, idnum: idnum).unbatch()
    probs = model.predict(test_images_ds, verbose=0)
    preds = probs.argmax(axis=1)
    ids = [b.decode("utf-8") for b in next(iter(test_ids_ds.batch(1_000_000))).numpy()]
    out_path = "submission.csv"
    if Path("/kaggle/working").exists():
        out_path = "/kaggle/working/submission.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("id,label\n")
        for i, p in zip(ids, preds):
            f.write(f"{i},{int(p)}\n")
    print(f"submission written to {out_path} (n={len(ids)})")
else:
    print("no test/ split available locally — skipping submission.csv (Kaggle kernel will produce it)")

# %% [markdown]
# ## Done.
#
# Local sanity metrics are surfaced as the last two stdout lines (`holdout_accuracy=` and `macro_f1=`),
# which `scripts/m10_t002_local_train.py` parses to record into `experiment_runs` via `kca run record-metric`.
