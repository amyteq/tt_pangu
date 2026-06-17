"""M9-T005 HistGradientBoosting + feature-engineering experiment.

Second local experiment for Spaceship Titanic. Mirrors the CV harness
of ``baseline_lr_spaceship.py`` (seed=42, StratifiedKFold n=5) so the
CV delta vs LR is a like-for-like comparison.

Feature engineering additions on top of the LR baseline:
  * ``Cabin`` -> ``Deck`` / ``CabinNum`` (numeric) / ``Side`` (P / S).
  * ``PassengerId`` parsed into ``GroupId`` + ``GroupSize`` (group is the
    prefix before the underscore; the same group travels together).
  * ``TotalSpend`` = sum of the five spend columns; ``HasSpend`` boolean.
  * Per-column ``log1p`` transforms on each of the spend columns +
    ``TotalSpend`` (heavy right skew).
  * ``Age`` median imputation kept; ``IsChild`` boolean (Age < 13).
  * Categoricals kept native (HomePlanet, Destination, CryoSleep, VIP,
    Deck, Side) — ``HistGradientBoostingClassifier`` consumes them
    directly via ``categorical_features=`` with pandas ``category``
    dtype, no one-hot expansion required.

Model: ``HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06,
max_leaf_nodes=31, random_state=42)`` — single fixed config, no sweep.

Usage::

    python scripts/hgb_fe_spaceship.py \\
        --data-dir data/spaceship-titanic \\
        --run-dir runs/spaceship-titanic/hgb-fe-v1

Outputs:
  - ``<run-dir>/submission.csv``  (PassengerId, Transported)
  - ``<run-dir>/cv_summary.json`` (per-fold scores, seed, folds, config)

The CV score should be recorded into the ``runs`` table via
``kca run record-metric --key cv_accuracy --value <score>``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score


SEED = 42
N_FOLDS = 5

SPEND_COLS = ["RoomService", "FoodCourt", "ShoppingMall", "Spa", "VRDeck"]
CATEGORICAL_COLS = [
    "HomePlanet",
    "CryoSleep",
    "Destination",
    "VIP",
    "Deck",
    "Side",
]


def _split_cabin(df: pd.DataFrame) -> pd.DataFrame:
    cabin = df["Cabin"].astype("string")
    parts = cabin.str.split("/", expand=True)
    deck = parts[0].fillna("Missing")
    num = pd.to_numeric(parts[1], errors="coerce") if parts.shape[1] >= 2 else np.nan
    side = parts[2].fillna("Missing") if parts.shape[1] >= 3 else pd.Series("Missing", index=df.index)
    out = df.copy()
    out["Deck"] = deck.astype("string")
    out["CabinNum"] = num
    out["Side"] = side.astype("string")
    return out.drop(columns=["Cabin"])


def _passenger_id_features(df: pd.DataFrame, group_size_map: pd.Series) -> pd.DataFrame:
    pid = df["PassengerId"].astype("string")
    group = pid.str.split("_", expand=True)[0]
    out = df.copy()
    out["GroupId"] = group
    out["GroupSize"] = group.map(group_size_map).fillna(1).astype("int64")
    return out


def _prep(df: pd.DataFrame, group_size_map: pd.Series) -> pd.DataFrame:
    df = _split_cabin(df)
    df = _passenger_id_features(df, group_size_map)

    # Spend feature engineering.
    total = df[SPEND_COLS].fillna(0).sum(axis=1)
    df["TotalSpend"] = total
    df["HasSpend"] = (total > 0).astype("int64")
    for c in SPEND_COLS + ["TotalSpend"]:
        df[f"log1p_{c}"] = np.log1p(df[c].fillna(0))

    df["IsChild"] = (df["Age"].fillna(df["Age"].median()) < 13).astype("int64")

    # Drop identifiers / free-text / raw GroupId (we kept GroupSize).
    df = df.drop(columns=["Name", "GroupId"], errors="ignore")

    # Cast categorical columns to pandas categorical dtype so
    # HistGradientBoostingClassifier consumes them directly.
    for c in CATEGORICAL_COLS:
        df[c] = df[c].astype("string").fillna("Missing").astype("category")

    return df


def _build_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=400,
        learning_rate=0.06,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=0.0,
        random_state=SEED,
        categorical_features="from_dtype",
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data/spaceship-titanic")
    p.add_argument("--run-dir", default="runs/spaceship-titanic/hgb-fe-v1")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(data_dir / "train.csv")
    test = pd.read_csv(data_dir / "test.csv")
    sample = pd.read_csv(data_dir / "sample_submission.csv")

    # Build group-size map across train + test so GroupSize is consistent.
    all_pid = pd.concat([train["PassengerId"], test["PassengerId"]], ignore_index=True)
    groups = all_pid.astype("string").str.split("_", expand=True)[0]
    group_size_map = groups.value_counts()

    y = train["Transported"].astype(int).to_numpy()
    train_feat = _prep(train.drop(columns=["Transported"]), group_size_map)
    test_feat = _prep(test, group_size_map)

    feature_cols = [c for c in train_feat.columns if c != "PassengerId"]

    # Align dtypes between train + test (categorical categories union).
    for c in CATEGORICAL_COLS:
        cats = pd.api.types.union_categoricals([train_feat[c], test_feat[c]], sort_categories=True).categories
        train_feat[c] = pd.Categorical(train_feat[c], categories=cats)
        test_feat[c] = pd.Categorical(test_feat[c], categories=cats)

    X_train = train_feat[feature_cols]
    X_test = test_feat[feature_cols]

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    model = _build_model()
    scores = cross_val_score(model, X_train, y, cv=skf, scoring="accuracy", n_jobs=1)
    cv_mean = float(np.mean(scores))
    cv_std = float(np.std(scores))

    # Refit on full train for the submission.
    final = _build_model()
    final.fit(X_train, y)
    preds = final.predict(X_test)
    preds_bool = preds.astype(bool)

    submission = pd.DataFrame(
        {
            "PassengerId": test_feat["PassengerId"].to_numpy(),
            "Transported": preds_bool,
        }
    )
    sub_path = run_dir / "submission.csv"
    submission = submission.set_index("PassengerId").loc[sample["PassengerId"]].reset_index()
    submission.to_csv(sub_path, index=False)

    summary = {
        "seed": SEED,
        "folds": N_FOLDS,
        "model": (
            "HistGradientBoostingClassifier("
            "max_iter=400, learning_rate=0.06, max_leaf_nodes=31, "
            "min_samples_leaf=20, random_state=42)"
        ),
        "cv_metric": "accuracy",
        "cv_scores": [float(s) for s in scores],
        "cv_mean": cv_mean,
        "cv_std": cv_std,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "submission_path": str(sub_path),
        "feature_cols": feature_cols,
        "categorical_cols": CATEGORICAL_COLS,
    }
    (run_dir / "cv_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps({"ok": True, **summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
