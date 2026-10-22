"""kaggle_replay_house_prices — offline Ridge baseline replay (M13-T003).

Mirrors the M5-T008 House Prices RMSLE pipeline but reads original
synthetic examples from ``tests/fixtures/house-prices/train.csv``. Uses Ridge
(a strict LR-equivalent for regression) rather than LinearRegression to
keep the metric stable across versions of sklearn's default solver.

Records:

- ``cv_rmsle_mean`` / ``cv_rmsle_std``
- ``holdout_rmsle``
- ``fit_time_ms``
- ``n_train``, ``n_holdout``, ``n_folds``

No Kaggle CLI. No LLM.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from .._kaggle_replay import (
    fixture_path,
    register_db,
    run_suite,
)

SUITE_NAME = "kaggle-replay-house-prices"
SUITE_CATEGORY = "kaggle_replay"
SUITE_VERSION = "0.2.0"
SUITE_DESCRIPTION = (
    "Synthetic House Prices-shaped Ridge replay (fixture v0.2). Records "
    "RMSLE on a 5-fold CV + holdout against tests/fixtures/house-prices/."
)

_FIXTURE = "house-prices"
_TARGET = "SalePrice"
_NUMERIC_COLS = (
    "MSSubClass",
    "LotFrontage",
    "LotArea",
    "OverallQual",
    "OverallCond",
    "YearBuilt",
    "YearRemodAdd",
    "GrLivArea",
    "FullBath",
    "HalfBath",
    "BedroomAbvGr",
    "TotRmsAbvGrd",
    "GarageCars",
    "GarageArea",
)
_CATEGORICAL_COLS = ("MSZoning", "Street", "LotShape", "Neighborhood")
_HOLDOUT_FRAC = 0.2
_N_FOLDS = 5
_SEED = 0


def _rmsle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Squared Log Error, the canonical House Prices metric.

    Clips predictions at 1e-6 to avoid log(<=0) on bad fits.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    y_pred = np.clip(y_pred, 1e-6, None)
    return float(np.sqrt(np.mean((np.log1p(y_true) - np.log1p(y_pred)) ** 2)))


def _run_case() -> dict[str, Any]:
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import KFold, train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    df = pd.read_csv(fixture_path(_FIXTURE))
    y = df[_TARGET].astype(float).to_numpy()
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
    # Ridge with a fixed alpha + explicit solver. ``random_state`` is
    # only used by stochastic solvers (sag / saga / svd) — we pin to
    # ``cholesky`` so the result is deterministic regardless of sklearn
    # default-solver drift across versions.
    clf = Ridge(alpha=1.0, solver="cholesky", random_state=_SEED)
    pipe = Pipeline(steps=[("pre", pre), ("clf", clf)])

    kf = KFold(n_splits=_N_FOLDS, shuffle=True, random_state=_SEED)
    fold_scores: list[float] = []
    for tr_idx, va_idx in kf.split(X):
        pipe.fit(X.iloc[tr_idx], y[tr_idx])
        pred = pipe.predict(X.iloc[va_idx])
        fold_scores.append(_rmsle(y[va_idx], pred))
    cv_arr = np.array(fold_scores)
    cv_mean = float(cv_arr.mean())
    cv_std = float(cv_arr.std())

    X_tr, X_ho, y_tr, y_ho = train_test_split(X, y, test_size=_HOLDOUT_FRAC, random_state=_SEED)
    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    fit_time_ms = int((time.perf_counter() - t0) * 1000)
    holdout_pred = pipe.predict(X_ho)
    holdout_rmsle = _rmsle(y_ho, holdout_pred)

    return {
        "cv_rmsle_mean": round(cv_mean, 8),
        "cv_rmsle_std": round(cv_std, 8),
        "holdout_rmsle": round(holdout_rmsle, 8),
        "fit_time_ms": fit_time_ms,
        "n_train": int(len(X_tr)),
        "n_holdout": int(len(X_ho)),
        "n_folds": _N_FOLDS,
        "model": "Ridge(alpha=1.0)",
        "fixture": _FIXTURE,
        "fixture_origin": "synthetic",
        "fixture_version": "synthetic-2026-10-22",
        "route": "mocked",
    }


def run(*, route: str = "mocked", audit_path: Path | None = None):
    return run_suite(
        case_name="baseline_ridge",
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
            "model": "Ridge(alpha=1.0)",
            "metric": "rmsle",
        },
    )
    if suite_id is not None:
        spec["suite_id"] = suite_id
    return spec
