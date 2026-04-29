import os
from typing import Any, Optional

import mlflow
import mlflow.sklearn
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _client() -> MlflowClient:
    uri = _env("MLFLOW_TRACKING_URI")
    if uri:
        mlflow.set_tracking_uri(uri)
    return MlflowClient()


def register_model(run_id: str, model_name: str) -> int:
    c = _client()
    model_uri = f"runs:/{run_id}/model"
    res = mlflow.register_model(model_uri=model_uri, name=model_name)
    return int(res.version)


def promote_to_staging(model_name: str, version: int) -> None:
    c = _client()
    c.transition_model_version_stage(
        name=model_name, version=str(version), stage="Staging", archive_existing_versions=False
    )


def _get_run_metrics(run_id: str) -> dict[str, float]:
    c = _client()
    run = c.get_run(run_id)
    return {k: float(v) for k, v in run.data.metrics.items()}


def _get_production_f1(model_name: str) -> Optional[float]:
    c = _client()
    latest = c.get_latest_versions(model_name, stages=["Production"])
    if not latest:
        return None
    run_id = latest[0].run_id
    metrics = _get_run_metrics(run_id)
    v = metrics.get("f1_score")
    return float(v) if v is not None else None


def promote_to_production(model_name: str, version: int) -> bool:
    threshold = float(_env("RETRAIN_METRIC_THRESHOLD", "0.005") or "0.005")
    c = _client()
    mv: ModelVersion = c.get_model_version(name=model_name, version=str(version))
    new_metrics = _get_run_metrics(mv.run_id)
    new_f1 = float(new_metrics.get("f1_score", 0.0))

    prod_f1 = _get_production_f1(model_name)
    if prod_f1 is None or new_f1 > float(prod_f1) + threshold:
        c.transition_model_version_stage(
            name=model_name, version=str(version), stage="Production", archive_existing_versions=True
        )
        return True
    return False


def get_production_model():
    model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
    return mlflow.sklearn.load_model(f"models:/{model_name}/Production")


def get_staging_model():
    model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
    return mlflow.sklearn.load_model(f"models:/{model_name}/Staging")


def list_model_versions(model_name: str) -> list[dict[str, Any]]:
    c = _client()
    out: list[dict[str, Any]] = []
    for mv in c.search_model_versions(f"name='{model_name}'"):
        metrics: dict[str, float] = {}
        try:
            metrics = _get_run_metrics(mv.run_id)
        except Exception:
            metrics = {}
        out.append(
            {
                "version": int(mv.version),
                "stage": mv.current_stage,
                "run_id": mv.run_id,
                "metrics": metrics,
            }
        )
    out.sort(key=lambda x: x["version"])
    return out


def archive_old_versions(model_name: str, keep_n: int = 3) -> None:
    c = _client()
    versions = list_model_versions(model_name)
    to_keep = {v["version"] for v in versions[-keep_n:]}
    for v in versions:
        if v["version"] in to_keep:
            continue
        c.transition_model_version_stage(
            name=model_name, version=str(v["version"]), stage="Archived", archive_existing_versions=False
        )
