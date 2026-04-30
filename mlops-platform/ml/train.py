"""Model training script for the mlops-platform synthetic classification model."""

import logging
import argparse
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split


logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class TrainMetrics:
    accuracy: float
    f1_score: float
    roc_auc: float
    precision: float
    recall: float


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def generate_dataset(n_samples: int = 5000, random_state: int = 42) -> pd.DataFrame:
    x, y = make_classification(
        n_samples=n_samples,
        n_features=10,
        n_informative=6,
        n_redundant=2,
        n_repeated=0,
        n_clusters_per_class=2,
        weights=None,
        flip_y=0.01,
        class_sep=1.0,
        random_state=random_state,
    )
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(10)])
    df["target"] = y.astype(int)
    return df


def split_dataset(
    df: pd.DataFrame, random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_df, temp_df = train_test_split(
        df, test_size=0.30, random_state=random_state, stratify=df["target"]
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, random_state=random_state, stratify=temp_df["target"]
    )
    return train_df, val_df, test_df


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> TrainMetrics:
    return TrainMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        f1_score=float(f1_score(y_true, y_pred)),
        roc_auc=float(roc_auc_score(y_true, y_proba)),
        precision=float(precision_score(y_true, y_pred)),
        recall=float(recall_score(y_true, y_pred)),
    )


def train_and_log(
    *,
    n_estimators: int,
    max_depth: Optional[int],
    min_samples_split: int,
    model_name: Optional[str] = None,
    experiment_name: Optional[str] = None,
    tracking_uri: Optional[str] = None,
) -> str:
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    if experiment_name:
        mlflow.set_experiment(experiment_name)

    model_name = model_name or _env("MODEL_NAME", "income-classifier") or "income-classifier"

    df = generate_dataset(n_samples=5000, random_state=42)
    train_df, val_df, test_df = split_dataset(df, random_state=42)

    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_dir / "reference.csv", index=False)
    test_df.to_csv(data_dir / "test.csv", index=False)

    x_train = train_df.drop(columns=["target"]).to_numpy()
    y_train = train_df["target"].to_numpy()
    x_val = val_df.drop(columns=["target"]).to_numpy()
    y_val = val_df["target"].to_numpy()

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=min_samples_split,
        random_state=42,
        n_jobs=-1,
    )

    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "n_estimators": n_estimators,
                "max_depth": -1 if max_depth is None else max_depth,
                "min_samples_split": min_samples_split,
            }
        )

        clf.fit(x_train, y_train)
        val_pred = clf.predict(x_val)
        val_proba = clf.predict_proba(x_val)[:, 1]
        metrics = compute_metrics(y_val, val_pred, val_proba)

        mlflow.log_metrics(asdict(metrics))
        mlflow.set_tags(
            {
                "model_type": "RandomForestClassifier",
                "dataset_version": "synthetic_v1",
                "training_date": datetime.now(timezone.utc).isoformat(),
            }
        )

        mlflow.sklearn.log_model(
            sk_model=clf,
            artifact_path="model",
            registered_model_name=None,
        )

        fi = pd.DataFrame(
            {
                "feature": [f"f{i}" for i in range(10)],
                "importance": clf.feature_importances_.astype(float),
            }
        ).sort_values("importance", ascending=False)
        fi_path = Path("feature_importance.csv")
        fi.to_csv(fi_path, index=False)
        mlflow.log_artifact(str(fi_path))
        fi_path.unlink(missing_ok=True)

        models_dir = Path(__file__).resolve().parent / "models" / "current"
        models_dir.mkdir(parents=True, exist_ok=True)
        out_path = models_dir / "model.pkl"
        pd.to_pickle(clf, out_path)

        _print_summary(metrics, run.info.run_id)
        return run.info.run_id


def train() -> str:
    run_id = train_and_log(n_estimators=200, max_depth=None, min_samples_split=2)
    try:
        from ml.model_registry import promote_to_production, promote_to_staging, register_model

        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        version = register_model(run_id, model_name=model_name)
        promote_to_staging(model_name=model_name, version=version)
        promote_to_production(model_name=model_name, version=version)
    except Exception as e:
        logger.warning("model_registry_seed_failed", extra={"error": str(e)})
    return run_id


def _print_summary(metrics: TrainMetrics, run_id: str) -> None:
    rows: list[tuple[str, Any]] = [
        ("run_id", run_id),
        ("accuracy", f"{metrics.accuracy:.4f}"),
        ("f1_score", f"{metrics.f1_score:.4f}"),
        ("roc_auc", f"{metrics.roc_auc:.4f}"),
        ("precision", f"{metrics.precision:.4f}"),
        ("recall", f"{metrics.recall:.4f}"),
    ]
    width = max(len(k) for k, _ in rows)
    print("\nTraining Summary")
    print("-" * (width + 20))
    for k, v in rows:
        print(f"{k:<{width}} : {v}")
    print("-" * (width + 20))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--max-depth", type=int, default=-1)
    p.add_argument("--min-samples-split", type=int, default=2)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    run_id = train_and_log(
        n_estimators=args.n_estimators,
        max_depth=None if args.max_depth <= 0 else args.max_depth,
        min_samples_split=args.min_samples_split,
        model_name=_env("MODEL_NAME"),
        experiment_name=_env("MLFLOW_EXPERIMENT_NAME"),
        tracking_uri=_env("MLFLOW_TRACKING_URI"),
    )
    print(run_id)


if __name__ == "__main__":
    main()
