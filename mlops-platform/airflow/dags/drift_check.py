"""Airflow DAG that checks drift hourly and conditionally triggers retraining."""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


logger = logging.getLogger(__name__)

def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


STREAM_DIR = Path("/opt/airflow/ml/data/stream")


def load_latest_batch() -> str:
    if not STREAM_DIR.exists():
        raise FileNotFoundError(f"Stream directory not found: {STREAM_DIR}")
    files = sorted(STREAM_DIR.glob("step_*.csv"))
    if not files:
        raise FileNotFoundError(f"No stream batches found in {STREAM_DIR}")
    return str(files[-1])


def compute_drift_score(ti) -> float:
    from ml.drift_detector import (
        get_psi_score,
        load_current_data,
        load_reference_data,
        run_drift_report,
    )

    batch_path = ti.xcom_pull(task_ids="load_latest_batch")
    ref = load_reference_data()
    cur = load_current_data(batch_path)
    res = run_drift_report(ref, cur)
    drift_score = float(res["drift_score"])
    features = []
    for i in range(10):
        col = f"f{i}"
        if col not in ref.columns or col not in cur.columns:
            continue
        psi = float(get_psi_score(ref[col], cur[col]))
        features.append({"feature": col, "psi": psi, "drift_detected": psi >= 0.2})

    ti.xcom_push(key="drift_score", value=drift_score)
    ti.xcom_push(key="drift_features", value=features)
    ti.xcom_push(key="drift_report_path", value=str(res.get("report_path", "")))
    return drift_score


def check_threshold(ti) -> str:
    drift_score = float(ti.xcom_pull(task_ids="compute_drift_score", key="drift_score") or 0.0)
    threshold = float(_env("DRIFT_THRESHOLD", "0.15") or "0.15")
    return "trigger_retrain" if drift_score > threshold else "skip_retrain"


def update_prometheus_metric(ti) -> None:
    pushgateway = _env("PUSHGATEWAY_URL")
    model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
    drift_score = float(ti.xcom_pull(task_ids="compute_drift_score", key="drift_score") or 0.0)
    drift_features = ti.xcom_pull(task_ids="compute_drift_score", key="drift_features") or []
    report_path = str(ti.xcom_pull(task_ids="compute_drift_score", key="drift_report_path") or "")

    api_drift_url = _env("API_DRIFT_URL", "http://api:8000/admin/drift") or "http://api:8000/admin/drift"
    api_event_url = _env("API_RETRAIN_EVENT_URL", "http://api:8000/admin/retrain-event") or "http://api:8000/admin/retrain-event"
    threshold = float(_env("DRIFT_THRESHOLD", "0.15") or "0.15")

    import requests

    requests.post(
        api_drift_url,
        json={
            "model_name": model_name,
            "drift_score": drift_score,
            "features": drift_features,
            "report_path": report_path,
        },
        timeout=10,
    )

    if drift_score > threshold:
        requests.post(api_event_url, json={"reason": "drift_threshold_exceeded", "run_id": None}, timeout=10)

    from prometheus_client import CollectorRegistry, Gauge
    from prometheus_client.exposition import push_to_gateway

    reg = CollectorRegistry()
    g = Gauge("model_drift_score", "Latest drift score", labelnames=["model_name"], registry=reg)
    g.labels(model_name=model_name).set(drift_score)
    if pushgateway:
        push_to_gateway(pushgateway, job="drift_check", registry=reg)


default_args: dict[str, Any] = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


with DAG(
    dag_id="drift_check_hourly",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    schedule="@hourly",
    catchup=False,
    default_args=default_args,
    tags=["mlops", "drift"],
) as dag:
    t_load_latest_batch = PythonOperator(task_id="load_latest_batch", python_callable=load_latest_batch)

    t_compute_drift_score = PythonOperator(
        task_id="compute_drift_score", python_callable=compute_drift_score
    )

    t_check_threshold = BranchPythonOperator(task_id="check_threshold", python_callable=check_threshold)

    t_trigger_retrain = TriggerDagRunOperator(
        task_id="trigger_retrain", trigger_dag_id="retrain_pipeline"
    )

    t_skip_retrain = EmptyOperator(task_id="skip_retrain")

    t_update_prom_metric = PythonOperator(
        task_id="update_prometheus_metric", python_callable=update_prometheus_metric
    )

    t_load_latest_batch >> t_compute_drift_score >> t_check_threshold
    t_check_threshold >> t_trigger_retrain >> t_update_prom_metric
    t_check_threshold >> t_skip_retrain >> t_update_prom_metric
