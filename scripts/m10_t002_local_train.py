#!/usr/bin/env python
"""M10-T002 local sanity training driver.

Runs the same logic as ``experiments/tpu-getting-started/baseline-tl/baseline.py``
against the small local slice staged under
``data/tpu-getting-started/local-slice/{train,val}/*.tfrec`` and records the
resulting ``holdout_accuracy`` and ``macro_f1`` into ``experiment_runs`` via
``kca run record-metric``.

This is the LOCAL CV/holdout sanity gate — not the Kaggle kernel run.

Usage::

    SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres \\
    KCA_DB_TARGET=local \\
    python scripts/m10_t002_local_train.py --epochs 3

The script is LOCAL_WRITE (writes ``runs/tpu-getting-started/baseline-tl/metrics.json``,
``cv_summary.json``, and `experiment_runs` rows). No Kaggle network calls.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--image-size", type=int, default=192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--run-dir", default="runs/tpu-getting-started/baseline-tl")
    args = ap.parse_args()

    _seed_everything(args.seed)

    # Suppress TF spam.
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")

    import tensorflow as tf  # noqa: E402

    tf.random.set_seed(args.seed)

    image_size = (args.image_size, args.image_size)
    num_classes = 104

    slice_root = Path("data") / "tpu-getting-started" / "local-slice"
    if not slice_root.exists():
        print(f"ERROR: local slice missing at {slice_root}", file=sys.stderr)
        return 2

    train_files = sorted(str(p) for p in (slice_root / "train").glob("*.tfrec"))
    val_files = sorted(str(p) for p in (slice_root / "val").glob("*.tfrec"))
    if not train_files or not val_files:
        print(
            f"ERROR: empty train/val slice under {slice_root} (train={len(train_files)}, val={len(val_files)})",
            file=sys.stderr,
        )
        return 2

    labeled_format = {
        "image": tf.io.FixedLenFeature([], tf.string),
        "class": tf.io.FixedLenFeature([], tf.int64),
    }

    def decode_image(image_bytes):
        image = tf.image.decode_jpeg(image_bytes, channels=3)
        image = tf.image.resize(image, image_size)
        image = tf.cast(image, tf.float32) / 255.0
        image = tf.reshape(image, [*image_size, 3])
        return image

    def read_labeled(example):
        parsed = tf.io.parse_single_example(example, labeled_format)
        return decode_image(parsed["image"]), tf.cast(parsed["class"], tf.int32)

    def load(files, training: bool):
        ds = tf.data.TFRecordDataset(files, num_parallel_reads=tf.data.AUTOTUNE)
        ds = ds.map(read_labeled, num_parallel_calls=tf.data.AUTOTUNE)
        if training:
            ds = ds.shuffle(2048, seed=args.seed)
        ds = ds.batch(args.batch_size, drop_remainder=training)
        ds = ds.prefetch(tf.data.AUTOTUNE)
        return ds

    train_ds = load(train_files, training=True)
    val_ds = load(val_files, training=False)

    import re

    def count_items(files: list[str]) -> int:
        n = 0
        for f in files:
            m = re.search(r"-(\d+)\.tfrec$", f)
            if m:
                n += int(m.group(1))
        return n

    n_train = count_items(train_files)
    n_val = count_items(val_files)
    steps_per_epoch = max(1, n_train // args.batch_size)
    print(
        f"local slice: train_files={len(train_files)} train_images={n_train} "
        f"val_files={len(val_files)} val_images={n_val} steps_per_epoch={steps_per_epoch}"
    )

    base = tf.keras.applications.MobileNetV2(
        input_shape=[*image_size, 3],
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False
    model = tf.keras.Sequential(
        [
            base,
            tf.keras.layers.GlobalAveragePooling2D(),
            tf.keras.layers.Dense(num_classes, activation="softmax"),
        ],
        name="petals_baseline_mobilenetv2_local",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )

    t0 = time.time()
    model.fit(
        train_ds.repeat(),
        steps_per_epoch=steps_per_epoch,
        epochs=args.epochs,
        validation_data=val_ds,
        verbose=2,
    )
    train_seconds = time.time() - t0
    print(f"train_seconds={train_seconds:.1f}")

    val_loss, val_acc = model.evaluate(val_ds, verbose=0)
    print(f"holdout_accuracy={float(val_acc):.4f} val_loss={float(val_loss):.4f}")

    # Macro F1 (per-class).
    tp = np.zeros(num_classes, dtype=np.int64)
    fp = np.zeros(num_classes, dtype=np.int64)
    fn = np.zeros(num_classes, dtype=np.int64)
    for batch_images, batch_labels in val_ds:
        preds = model.predict(batch_images, verbose=0).argmax(axis=1)
        labels = batch_labels.numpy()
        for y, p in zip(labels, preds):
            if y == p:
                tp[int(y)] += 1
            else:
                fp[int(p)] += 1
                fn[int(y)] += 1

    f1s = []
    for c in range(num_classes):
        denom_p = tp[c] + fp[c]
        denom_r = tp[c] + fn[c]
        if denom_p == 0 or denom_r == 0:
            f1s.append(0.0)
            continue
        precision = tp[c] / denom_p
        recall = tp[c] / denom_r
        if precision + recall == 0:
            f1s.append(0.0)
        else:
            f1s.append(float(2 * precision * recall / (precision + recall)))
    macro_f1 = float(np.mean(f1s))
    print(f"macro_f1={macro_f1:.4f}")

    holdout_accuracy = float(val_acc)
    metrics = {
        "holdout_accuracy": holdout_accuracy,
        "val_loss": float(val_loss),
        "macro_f1": macro_f1,
        "n_val_images_seen": int(n_val),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "image_size": args.image_size,
        "seed": args.seed,
        "backbone": "MobileNetV2",
        "train_seconds": train_seconds,
        "data_source": "local-slice (1 train shard, 1 val shard)",
    }

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    cv_summary = {
        "method": "fixed-holdout (Kaggle-published train/val split, single-shard slice)",
        "holdout_accuracy": holdout_accuracy,
        "macro_f1": macro_f1,
        "seed": args.seed,
        "epochs": args.epochs,
        "backbone": "MobileNetV2",
    }
    (run_dir / "cv_summary.json").write_text(json.dumps(cv_summary, indent=2), encoding="utf-8")

    # Sanity guards from the task spec.
    if holdout_accuracy >= 0.99:
        print(
            f"WARN: holdout_accuracy={holdout_accuracy:.4f} is suspiciously high (>= 0.99); "
            "investigate for leakage before pushing to Kaggle.",
            file=sys.stderr,
        )
    if holdout_accuracy <= 0.30:
        print(
            f"WARN: holdout_accuracy={holdout_accuracy:.4f} is suspiciously low (<= 0.30); "
            "a trivially-trained backbone should clear 0.30 on 104-class.",
            file=sys.stderr,
        )

    # Record into experiment_runs via kca CLI (DB-first).
    if os.environ.get("SUPABASE_DB_URL"):
        for k, v in (
            ("holdout_accuracy", holdout_accuracy),
            ("macro_f1", macro_f1),
            ("val_loss", float(val_loss)),
        ):
            subprocess.run(
                [
                    sys.executable,
                    "tools/kca/kca.py",
                    "run",
                    "record-metric",
                    "--run-dir",
                    str(run_dir),
                    "--key",
                    k,
                    "--value",
                    str(v),
                    "--json",
                ],
                check=True,
            )
    else:
        print("SUPABASE_DB_URL unset — metrics recorded only in metrics.json, not in experiment_runs.")

    print(json.dumps({"ok": True, **metrics}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
