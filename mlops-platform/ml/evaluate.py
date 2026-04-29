"""Model evaluation utilities for production/staged MLflow runs."""

import logging
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import mlflow
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    roc_curve,
)

from ml.model_registry import get_production_model
from ml.train import generate_dataset, split_dataset


logger = logging.getLogger(__name__)

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _load_test_data() -> tuple[np.ndarray, np.ndarray]:
    data_path = Path(__file__).resolve().parent / "data" / "test.csv"
    if data_path.exists():
        df = pd.read_csv(data_path)
    else:
        df = generate_dataset(n_samples=5000, random_state=42)
        _, _, df = split_dataset(df, random_state=42)
    x = df.drop(columns=["target"]).to_numpy()
    y = df["target"].to_numpy()
    return x, y


def _setup_mlflow() -> None:
    tracking_uri = _env("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    exp = _env("MLFLOW_EXPERIMENT_NAME")
    if exp:
        mlflow.set_experiment(exp)


def _evaluate_model(model, x_test: np.ndarray, y_test: np.ndarray) -> tuple[float, Path]:
    y_pred = model.predict(x_test)
    y_proba = model.predict_proba(x_test)[:, 1]

    f1 = float(f1_score(y_test, y_pred))
    report_txt = classification_report(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred).tolist()

    fpr, tpr, thresholds = roc_curve(y_test, y_proba)
    prob_true, prob_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy="quantile")

    artifacts_dir = Path("evaluation_artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    (artifacts_dir / "classification_report.txt").write_text(report_txt)
    (artifacts_dir / "confusion_matrix.json").write_text(json.dumps({"confusion_matrix": cm}))
    (artifacts_dir / "roc_curve.json").write_text(
        json.dumps({"fpr": fpr.tolist(), "tpr": tpr.tolist(), "thresholds": thresholds.tolist()})
    )
    (artifacts_dir / "calibration_curve.json").write_text(
        json.dumps({"prob_true": prob_true.tolist(), "prob_pred": prob_pred.tolist()})
    )

    return f1, artifacts_dir


def evaluate_run_model(*, run_id: str, min_f1: float = 0.75) -> dict[str, Any]:
    _setup_mlflow()
    model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
    x_test, y_test = _load_test_data()

    f1, artifacts_dir = _evaluate_model(model, x_test, y_test)

    with mlflow.start_run(run_id=run_id):
        mlflow.set_tags({"evaluation_date": datetime.now(timezone.utc).isoformat(), "stage": "Candidate"})
        mlflow.log_metric("f1_score_test", f1)
        for p in artifacts_dir.iterdir():
            mlflow.log_artifact(str(p), artifact_path="evaluation")

    passed = f1 >= float(min_f1)
    return {"passed": bool(passed), "f1_score": f1}


def evaluate_production_model(*, min_f1: float = 0.75) -> dict[str, Any]:
    _setup_mlflow()
    model = get_production_model()
    x_test, y_test = _load_test_data()

    f1, artifacts_dir = _evaluate_model(model, x_test, y_test)

    with mlflow.start_run(run_name="evaluation"):
        mlflow.set_tags({"evaluation_date": datetime.now(timezone.utc).isoformat(), "stage": "Production"})
        mlflow.log_metric("f1_score", f1)
        for p in artifacts_dir.iterdir():
            mlflow.log_artifact(str(p))

    passed = f1 >= float(min_f1)
    return {"passed": bool(passed), "f1_score": f1}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--min-f1", type=float, default=0.75)
    p.add_argument("--run-id", type=str, default="")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.run_id:
        res = evaluate_run_model(run_id=args.run_id, min_f1=args.min_f1)
    else:
        res = evaluate_production_model(min_f1=args.min_f1)
    print(json.dumps(res))
    if not res["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
