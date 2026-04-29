import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

import numpy as np
import pandas as pd

from ml.train import generate_dataset


REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def load_reference_data() -> pd.DataFrame:
    data_path = Path(__file__).resolve().parent / "data" / "reference.csv"
    if data_path.exists():
        return pd.read_csv(data_path)
    return generate_dataset(n_samples=5000, random_state=42)


def load_current_data(batch_path: Union[str, Path]) -> pd.DataFrame:
    return pd.read_csv(batch_path)


def _extract_drift_summary(report_dict: dict[str, Any]) -> tuple[float, list[str], float]:
    drifted_features: list[str] = []
    share_drifted = 0.0
    drift_score = 0.0

    metrics = report_dict.get("metrics", [])
    for m in metrics:
        result = m.get("result", {})
        if isinstance(result, dict):
            if "share_drifted_columns" in result:
                share_drifted = float(result["share_drifted_columns"])
            if "dataset_drift" in result:
                drift_score = float(1.0 if result["dataset_drift"] else 0.0)
            if "drift_by_columns" in result and isinstance(result["drift_by_columns"], dict):
                for col, col_res in result["drift_by_columns"].items():
                    if isinstance(col_res, dict) and col_res.get("drift_detected") is True:
                        drifted_features.append(str(col))

    if drift_score == 0.0 and share_drifted > 0.0:
        drift_score = share_drifted

    drifted_features = sorted(set(drifted_features))
    return drift_score, drifted_features, share_drifted


def run_drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame) -> dict[str, Any]:
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    from evidently.report import Report

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = Report(metrics=[DataDriftPreset(), DataQualityPreset()])
    report.run(reference_data=reference_df, current_data=current_df)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = REPORTS_DIR / f"drift_{ts}.html"
    report.save_html(str(out_path))

    d = report.as_dict()
    drift_score, drifted_features, share_drifted = _extract_drift_summary(d)
    return {
        "drift_score": float(drift_score),
        "drifted_features": drifted_features,
        "share_drifted": float(share_drifted),
        "report_path": str(out_path),
        "timestamp": ts,
    }


def run_target_drift_report(
    reference_df: pd.DataFrame, current_df: pd.DataFrame, target_col: str
) -> dict[str, Any]:
    from evidently.metric_preset import TargetDriftPreset
    from evidently.report import Report

    report = Report(metrics=[TargetDriftPreset()])
    ref = reference_df.copy()
    cur = current_df.copy()
    if target_col != "target":
        if target_col in ref.columns and "target" not in ref.columns:
            ref = ref.rename(columns={target_col: "target"})
        if target_col in cur.columns and "target" not in cur.columns:
            cur = cur.rename(columns={target_col: "target"})
    report.run(reference_data=ref, current_data=cur)
    d = report.as_dict()
    score = 0.0
    for m in d.get("metrics", []):
        result = m.get("result", {})
        if isinstance(result, dict) and "drift_score" in result:
            score = float(result["drift_score"])
    return {"target_drift_score": float(score)}


def get_psi_score(reference_series: pd.Series, current_series: pd.Series, bins: int = 10) -> float:
    ref = reference_series.dropna().astype(float).to_numpy()
    cur = current_series.dropna().astype(float).to_numpy()
    if ref.size == 0 or cur.size == 0:
        return 0.0

    quantiles = np.linspace(0.0, 1.0, bins + 1)
    cuts = np.quantile(ref, quantiles)
    cuts = np.unique(cuts)
    if cuts.size < 3:
        return 0.0

    ref_counts, _ = np.histogram(ref, bins=cuts)
    cur_counts, _ = np.histogram(cur, bins=cuts)

    ref_pct = ref_counts / max(ref_counts.sum(), 1)
    cur_pct = cur_counts / max(cur_counts.sum(), 1)

    eps = 1e-6
    psi = 0.0
    for r, c in zip(ref_pct, cur_pct):
        r_ = max(float(r), eps)
        c_ = max(float(c), eps)
        psi += (r_ - c_) * math.log(r_ / c_)
    return float(psi)


def is_drift_detected(drift_score: float, threshold: float = 0.15) -> bool:
    return float(drift_score) > float(threshold)
