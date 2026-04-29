import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


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
    from ml.drift_detector import load_reference_data, load_current_data, run_drift_report

    batch_path = ti.xcom_pull(task_ids="load_latest_batch")
    ref = load_reference_data()
    cur = load_current_data(batch_path)
    res = run_drift_report(ref, cur)
    drift_score = float(res["drift_score"])
    ti.xcom_push(key="drift_score", value=drift_score)
    return drift_score


def check_threshold(ti) -> str:
    drift_score = float(ti.xcom_pull(task_ids="compute_drift_score", key="drift_score") or 0.0)
    threshold = float(_env("DRIFT_THRESHOLD", "0.15") or "0.15")
    return "trigger_retrain" if drift_score > threshold else "skip_retrain"


def update_prometheus_metric(ti) -> None:
    pushgateway = _env("PUSHGATEWAY_URL")
    model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
    drift_score = float(ti.xcom_pull(task_ids="compute_drift_score", key="drift_score") or 0.0)

    if not pushgateway:
        api_url = _env("API_DRIFT_URL", "http://api:8000/admin/drift") or "http://api:8000/admin/drift"
        import requests

        requests.post(api_url, json={"model_name": model_name, "drift_score": drift_score}, timeout=10)
        return

    from prometheus_client import CollectorRegistry, Gauge
    from prometheus_client.exposition import push_to_gateway

    reg = CollectorRegistry()
    g = Gauge("model_drift_score", "Latest drift score", labelnames=["model_name"], registry=reg)
    g.labels(model_name=model_name).set(drift_score)
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
