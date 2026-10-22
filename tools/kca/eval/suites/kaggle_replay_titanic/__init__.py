"""kaggle_replay_titanic — offline Titanic LR baseline replay (M13-T003).

Reads the synthetic ``tests/fixtures/titanic/train.csv`` and fits a deterministic
logistic-regression baseline on a fixed feature set. No real Kaggle
network. No LLM. No notebook/kernel push.

Records the following metrics into ``eval_results.metrics``:

- ``cv_accuracy_mean`` — StratifiedKFold(n_splits=5) mean accuracy
- ``cv_accuracy_std``  — stddev of the same
- ``holdout_accuracy`` — accuracy on a 20% holdout split (seed=0)
- ``fit_time_ms``      — wall-clock fit time on the full train set
- ``n_train``, ``n_holdout``, ``n_folds`` — dataset shape

The values are not LB-comparable: the fixture contains 200 invented
rows, not competition data. They are a deterministic baseline against
which future PRs can detect regressions in the platform's eval pipeline.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .._kaggle_replay import (
    fixture_path,
    register_db,
    run_suite,
)

SUITE_NAME = "kaggle-replay-titanic"
SUITE_CATEGORY = "kaggle_replay"
SUITE_VERSION = "0.2.0"
SUITE_DESCRIPTION = "Synthetic Titanic-shaped LR replay (fixture v0.2). Reads tests/fixtures/titanic/train.csv; no Kaggle network, no LLM."

_FIXTURE = "titanic"
_TARGET = "Survived"
_NUMERIC_COLS = ("Pclass", "Age", "SibSp", "Parch", "Fare")
_CATEGORICAL_COLS = ("Sex", "Embarked")
_HOLDOUT_FRAC = 0.2
_N_FOLDS = 5
_SEED = 0


def _run_case() -> dict[str, Any]:
    # Imports are local so ``kca eval list`` does not need sklearn on the
    # path until a run actually fires.
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import (
        StratifiedKFold,
        cross_val_score,
        train_test_split,
    )
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    df = pd.read_csv(fixture_path(_FIXTURE))
    y = df[_TARGET].astype(int).to_numpy()
    X = df[list(_NUMERIC_COLS) + list(_CATEGORICAL_COLS)].copy()

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
            ("num", numeric_pipe, list(_NUMERIC_COLS)),
            ("cat", categorical_pipe, list(_CATEGORICAL_COLS)),
        ]
    )
    clf = LogisticRegression(max_iter=2000, random_state=_SEED)
    pipe = Pipeline(steps=[("pre", pre), ("clf", clf)])

    # CV on the full training fixture.
    skf = StratifiedKFold(n_splits=_N_FOLDS, shuffle=True, random_state=_SEED)
    cv_scores = cross_val_score(pipe, X, y, cv=skf, scoring="accuracy", n_jobs=1)
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())

    # Holdout split for the leaderboard-shaped score.
    X_tr, X_ho, y_tr, y_ho = train_test_split(X, y, test_size=_HOLDOUT_FRAC, random_state=_SEED, stratify=y)
    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    fit_time_ms = int((time.perf_counter() - t0) * 1000)
    holdout_accuracy = float(pipe.score(X_ho, y_ho))

    return {
        "cv_accuracy_mean": round(cv_mean, 8),
        "cv_accuracy_std": round(cv_std, 8),
        "holdout_accuracy": round(holdout_accuracy, 8),
        "fit_time_ms": fit_time_ms,
        "n_train": int(len(X_tr)),
        "n_holdout": int(len(X_ho)),
        "n_folds": _N_FOLDS,
        "model": "LogisticRegression(max_iter=2000)",
        "fixture": _FIXTURE,
        "fixture_origin": "synthetic",
        "fixture_version": "synthetic-2026-10-22",
        "route": "mocked",
    }


def run(*, route: str = "mocked", audit_path: Path | None = None):
    return run_suite(
        case_name="baseline_lr",
        case_runner=_run_case,
        route=route,
        audit_path=audit_path,
    )


def register(db_module: object | None) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "name": SUITE_NAME,
        "category": SUITE_CATEGORY,
        "version": SUITE_VERSION,
        "description": SUITE_DESCRIPTION,
        "default_route": "mocked",
        "requires_db": False,
        "requires_remote": False,
        "runner": run,
        "case_count": 1,
    }
    suite_id = register_db(
        db_module,
        name=SUITE_NAME,
        category=SUITE_CATEGORY,
        version=SUITE_VERSION,
        description=SUITE_DESCRIPTION,
        metadata={
            "case_count": 1,
            "fixture": _FIXTURE,
            "fixture_origin": "synthetic",
            "fixture_version": "synthetic-2026-10-22",
            "target": _TARGET,
            "model": "LogisticRegression(max_iter=2000)",
        },
    )
    if suite_id is not None:
        spec["suite_id"] = suite_id
    return spec
