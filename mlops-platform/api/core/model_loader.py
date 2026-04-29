"""Model loading utilities for MLflow registry and local fallbacks."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.tracking import MlflowClient


logger = logging.getLogger(__name__)

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def load_model_from_registry(stage: str):
    tracking_uri = _env("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
    try:
        if os.getenv("SKIP_REGISTRY_LOAD") == "1":
            raise RuntimeError("Registry load skipped")
        return mlflow.sklearn.load_model(f"models:/{model_name}/{stage}")
    except Exception:
        candidates = [
            Path("/app/ml/models/current/model.pkl"),
            Path(__file__).resolve().parents[2] / "ml" / "models" / "current" / "model.pkl",
            Path(__file__).resolve().parents[1] / "ml" / "models" / "current" / "model.pkl",
        ]
        for p in candidates:
            if p.exists():
                return pd.read_pickle(p)
        raise


class ModelManager:
    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def load_all(self) -> dict[str, Any]:
        v1 = load_model_from_registry("Production")
        try:
            v2 = load_model_from_registry("Staging")
        except Exception:
            v2 = v1
        self.models = {"v1": v1, "v2": v2}
        return self.models

    def reload(self) -> dict[str, Any]:
        new_v1 = load_model_from_registry("Production")
        try:
            new_v2 = load_model_from_registry("Staging")
        except Exception:
            new_v2 = new_v1
        self.models = {"v1": new_v1, "v2": new_v2}
        return self.models

    def get_model(self, version: str):
        if version not in self.models:
            raise KeyError(f"Unknown model version: {version}")
        return self.models[version]

    def get_model_info(self) -> dict[str, Any]:
        tracking_uri = _env("MLFLOW_TRACKING_URI")
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        try:
            c = MlflowClient()
        except Exception:
            return {"Production": None, "Staging": None}

        def _latest(stage: str) -> Optional[dict[str, Any]]:
            try:
                vs = c.get_latest_versions(model_name, stages=[stage])
                if not vs:
                    return None
                v = vs[0]
                metrics = {}
                try:
                    run = c.get_run(v.run_id)
                    metrics = {k: float(val) for k, val in run.data.metrics.items()}
                except Exception:
                    metrics = {}
                return {"version": int(v.version), "run_id": v.run_id, "metrics": metrics}
            except Exception:
                return None

        return {"Production": _latest("Production"), "Staging": _latest("Staging")}
