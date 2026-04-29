import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.task_group import TaskGroup


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


ML_DIR = Path("/opt/airflow/ml")
DATA_DIR = ML_DIR / "data"
STREAM_DIR = DATA_DIR / "stream"


def _fail(msg: str, exc: Exception | None = None) -> None:
    if exc:
        raise RuntimeError(f"{msg}: {exc}") from exc
    raise RuntimeError(msg)


def validate_data_schema() -> None:
    try:
        expected_cols = [f"f{i}" for i in range(10)]
        if not STREAM_DIR.exists():
            _fail(f"Stream directory not found: {STREAM_DIR}")
        files = sorted(STREAM_DIR.glob("step_*.csv"))
        if not files:
            _fail(f"No stream batches found in {STREAM_DIR}")
        df = pd.read_csv(files[-1])

        if list(df.columns) != expected_cols:
            _fail(f"Schema mismatch. Expected {expected_cols}, got {list(df.columns)}")

        null_pct = df.isna().mean().max()
        if float(null_pct) > 0.01:
            _fail(f"Null percentage too high: {null_pct:.3f}")

        for c in expected_cols:
            if not pd.api.types.is_numeric_dtype(df[c]):
                _fail(f"Non-numeric dtype for column {c}: {df[c].dtype}")
            if df[c].abs().max() > 50:
                _fail(f"Range violation for {c}: max abs {df[c].abs().max():.3f}")
    except Exception as e:
        _fail("validate_data_schema failed", e)


def generate_training_data() -> str:
    try:
        from ml.drift_detector import load_reference_data
        from ml.model_registry import get_production_model

        ref = load_reference_data()
        expected_cols = [f"f{i}" for i in range(10)]
        if "target" not in ref.columns:
            _fail("Reference data missing target column")

        files = sorted(STREAM_DIR.glob("step_*.csv"))[-10:]
        recent: list[pd.DataFrame] = []
        if files:
            prod = get_production_model()
            for f in files:
                batch = pd.read_csv(f)
                x = batch[expected_cols].to_numpy()
                pseudo = prod.predict(x).astype(int)
                batch = batch.copy()
                batch["target"] = pseudo
                recent.append(batch)

        df = pd.concat([ref, *recent], ignore_index=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out = DATA_DIR / "train_latest.csv"
        df.to_csv(out, index=False)
        return str(out)
    except Exception as e:
        _fail("generate_training_data failed", e)
        raise


def train_model(ti) -> str:
    try:
        from ml.train import train_and_log

        run_id = train_and_log(
            n_estimators=250,
            max_depth=None,
            min_samples_split=2,
            model_name=_env("MODEL_NAME"),
            experiment_name=_env("MLFLOW_EXPERIMENT_NAME"),
            tracking_uri=_env("MLFLOW_TRACKING_URI"),
        )
        ti.xcom_push(key="run_id", value=run_id)
        return run_id
    except Exception as e:
        _fail("train_model failed", e)
        raise


def evaluate_model(ti) -> float:
    try:
        from ml.evaluate import evaluate_run_model

        run_id = str(ti.xcom_pull(task_ids="train_and_evaluate.train_model", key="run_id"))
        res = evaluate_run_model(run_id=run_id, min_f1=0.75)
        f1 = float(res["f1_score"])
        ti.xcom_push(key="f1_score", value=f1)
        if not res["passed"]:
            _fail(f"Model failed evaluation gate. f1_score={f1:.4f}")
        return f1
    except Exception as e:
        _fail("evaluate_model failed", e)
        raise


def register_model(ti) -> int:
    try:
        from ml.model_registry import register_model

        run_id = str(ti.xcom_pull(task_ids="train_and_evaluate.train_model", key="run_id"))
        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        version = register_model(run_id, model_name)
        ti.xcom_push(key="version", value=version)
        return version
    except Exception as e:
        _fail("register_model failed", e)
        raise


def promote_to_staging(ti) -> None:
    try:
        from ml.model_registry import promote_to_staging

        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        version = int(ti.xcom_pull(task_ids="register_and_promote.register_model", key="version"))
        promote_to_staging(model_name, version)
    except Exception as e:
        _fail("promote_to_staging failed", e)


def compare_with_production(ti) -> str:
    try:
        from ml.model_registry import list_model_versions

        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        new_f1 = float(ti.xcom_pull(task_ids="train_and_evaluate.evaluate_model", key="f1_score") or 0.0)
        threshold = float(_env("RETRAIN_METRIC_THRESHOLD", "0.005") or "0.005")

        prod_f1 = None
        for v in reversed(list_model_versions(model_name)):
            if v["stage"] == "Production":
                prod_f1 = float(v["metrics"].get("f1_score", 0.0))
                break

        if prod_f1 is None:
            return "register_and_promote.promote_to_production"
        return (
            "register_and_promote.promote_to_production"
            if new_f1 > float(prod_f1) + threshold
            else "keep_production"
        )
    except Exception as e:
        _fail("compare_with_production failed", e)
        raise


def promote_to_production(ti) -> None:
    try:
        from ml.model_registry import promote_to_production

        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        version = int(ti.xcom_pull(task_ids="register_and_promote.register_model", key="version"))
        promoted = promote_to_production(model_name, version)
        if not promoted:
            _fail("Promotion gate rejected candidate model")
    except Exception as e:
        _fail("promote_to_production failed", e)


def reload_api_models() -> None:
    try:
        url = _env("API_RELOAD_URL", "http://api:8000/admin/reload") or "http://api:8000/admin/reload"
        r = requests.post(url, timeout=10)
        if r.status_code >= 300:
            _fail(f"API reload failed with status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        _fail("reload_api_models failed", e)


def notify_completion(ti) -> None:
    try:
        model_name = _env("MODEL_NAME", "income-classifier") or "income-classifier"
        run_id = str(ti.xcom_pull(task_ids="train_and_evaluate.train_model", key="run_id"))
        new_f1 = float(ti.xcom_pull(task_ids="train_and_evaluate.evaluate_model", key="f1_score") or 0.0)
        decision = (
            "promoted"
            if ti.xcom_pull(task_ids="register_and_promote.promote_to_production") is not None
            else "kept_production"
        )
        print(
            {
                "model_name": model_name,
                "run_id": run_id,
                "new_f1": new_f1,
                "decision": decision,
            }
        )
    except Exception as e:
        _fail("notify_completion failed", e)


default_args: dict[str, Any] = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


with DAG(
    dag_id="retrain_pipeline",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    schedule="0 2 * * 1",
    catchup=False,
    default_args=default_args,
    tags=["mlops", "retrain"],
) as dag:
    t_validate_data_schema = PythonOperator(
        task_id="validate_data_schema", python_callable=validate_data_schema
    )

    t_generate_training_data = PythonOperator(
        task_id="generate_training_data", python_callable=generate_training_data
    )

    with TaskGroup(group_id="train_and_evaluate") as tg_train_eval:
        t_train_model = PythonOperator(task_id="train_model", python_callable=train_model)
        t_evaluate_model = PythonOperator(task_id="evaluate_model", python_callable=evaluate_model)
        t_train_model >> t_evaluate_model

    with TaskGroup(group_id="register_and_promote") as tg_reg_promote:
        t_register_model = PythonOperator(task_id="register_model", python_callable=register_model)
        t_promote_to_staging = PythonOperator(
            task_id="promote_to_staging", python_callable=promote_to_staging
        )
        t_promote_to_production = PythonOperator(
            task_id="promote_to_production", python_callable=promote_to_production
        )
        t_register_model >> t_promote_to_staging

    t_compare = BranchPythonOperator(
        task_id="compare_with_production", python_callable=compare_with_production
    )

    t_reload_api_models = PythonOperator(task_id="reload_api_models", python_callable=reload_api_models)
    t_keep_production = EmptyOperator(task_id="keep_production")
    t_notify_completion = PythonOperator(task_id="notify_completion", python_callable=notify_completion)

    t_validate_data_schema >> t_generate_training_data >> tg_train_eval >> tg_reg_promote
    tg_reg_promote >> t_compare
    t_compare >> t_promote_to_production >> t_reload_api_models >> t_notify_completion
    t_compare >> t_keep_production >> t_notify_completion
