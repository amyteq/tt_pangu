"""M9-T002 baseline logistic-regression experiment for Spaceship Titanic.

Trains a single LR baseline with a small, deterministic preprocessing
pipeline and reports a stratified k-fold CV accuracy. Writes a Kaggle
``submission.csv`` for the test set into the run artifact directory.

This script is intentionally minimal and reproducible:

  * seed = 42, folds = 5 (StratifiedKFold).
  * Features: existing numeric columns + Cabin-derived deck/side, plus
    one-hot encoded low-cardinality categoricals. Names and PassengerId
    are dropped as identifiers.
  * Model: ``sklearn.linear_model.LogisticRegression(max_iter=2000)``.

Usage::

    python scripts/baseline_lr_spaceship.py \
        --data-dir data/spaceship-titanic \
        --run-dir runs/spaceship-titanic/baseline-lr

Outputs:
  - ``<run-dir>/submission.csv``  (PassengerId, Transported)
  - ``<run-dir>/cv_summary.json`` (per-fold scores, seed, folds)

The CV score should be recorded into the ``runs`` table via
``kca run record-metric --key cv_accuracy --value <score>``; this script
prints the score to stdout for that step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SEED = 42
N_FOLDS = 5


def _split_cabin(df: pd.DataFrame) -> pd.DataFrame:
    """Cabin is 'Deck/Num/Side'. Split into Deck and Side; drop Num."""
    cabin = df["Cabin"].astype("string")
    parts = cabin.str.split("/", expand=True)
    deck = parts[0].fillna("Missing")
    side = parts[2].fillna("Missing") if parts.shape[1] >= 3 else pd.Series("Missing", index=df.index)
    out = df.copy()
    out["Deck"] = deck.astype("string")
    out["Side"] = side.astype("string")
    return out.drop(columns=["Cabin"])


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = _split_cabin(df)
    # Drop identifiers / free-text columns.
    df = df.drop(columns=["Name"], errors="ignore")
    return df


def _build_pipeline(numeric_cols: list[str], categorical_cols: list[str]) -> Pipeline:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    pre = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_cols),
            ("cat", categorical_pipe, categorical_cols),
        ]
    )
    clf = LogisticRegression(max_iter=2000, random_state=SEED)
    return Pipeline(steps=[("pre", pre), ("clf", clf)])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data/spaceship-titanic")
    p.add_argument("--run-dir", default="runs/spaceship-titanic/baseline-lr")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(data_dir / "train.csv")
    test = pd.read_csv(data_dir / "test.csv")
    sample = pd.read_csv(data_dir / "sample_submission.csv")

    y = train["Transported"].astype(int).to_numpy()
    train_feat = _prep(train.drop(columns=["Transported"]))
    test_feat = _prep(test)

    # Choose columns AFTER prep so Deck/Side are picked up.
    numeric_cols = [c for c in train_feat.columns if train_feat[c].dtype.kind in {"f", "i"} and c != "PassengerId"]
    categorical_cols = [c for c in train_feat.columns if c not in numeric_cols and c != "PassengerId"]

    pipe = _build_pipeline(numeric_cols, categorical_cols)

    X_train = train_feat.drop(columns=["PassengerId"])
    X_test = test_feat.drop(columns=["PassengerId"])

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    scores = cross_val_score(pipe, X_train, y, cv=skf, scoring="accuracy", n_jobs=1)
    cv_mean = float(np.mean(scores))
    cv_std = float(np.std(scores))

    pipe.fit(X_train, y)
    preds = pipe.predict(X_test)
    preds_bool = preds.astype(bool)

    submission = pd.DataFrame(
        {
            "PassengerId": test_feat["PassengerId"].to_numpy(),
            "Transported": preds_bool,
        }
    )
    # Preserve sample_submission ordering for safety.
    sub_path = run_dir / "submission.csv"
    submission = submission.set_index("PassengerId").loc[sample["PassengerId"]].reset_index()
    submission.to_csv(sub_path, index=False)

    summary = {
        "seed": SEED,
        "folds": N_FOLDS,
        "model": "LogisticRegression(max_iter=2000)",
        "cv_metric": "accuracy",
        "cv_scores": [float(s) for s in scores],
        "cv_mean": cv_mean,
        "cv_std": cv_std,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "submission_path": str(sub_path),
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
    }
    (run_dir / "cv_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps({"ok": True, **summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
