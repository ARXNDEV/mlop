from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.drift_detector import (
    get_psi_score,
    is_drift_detected,
    load_reference_data,
    run_drift_report,
)


def test_is_drift_detected_returns_false_for_identical_distributions(reference_df):
    res = run_drift_report(reference_df, reference_df.copy())
    assert is_drift_detected(float(res["drift_score"]), threshold=0.15) is False


def test_is_drift_detected_returns_true_for_severely_drifted_data(reference_df, current_df_drifted):
    res = run_drift_report(reference_df, current_df_drifted)
    assert is_drift_detected(float(res["drift_score"]), threshold=0.001) is True


def test_get_psi_score_returns_0_for_identical_series():
    s = pd.Series([0.0, 1.0, 2.0, 3.0] * 100)
    assert get_psi_score(s, s) == pytest.approx(0.0, abs=1e-6)


def test_get_psi_score_returns_gt_02_for_different_series():
    rng = np.random.default_rng(1)
    ref = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    cur = pd.Series(rng.normal(loc=3.0, scale=1.0, size=2000))
    assert get_psi_score(ref, cur) > 0.2


def test_run_drift_report_returns_required_keys(reference_df, current_df_drifted):
    res = run_drift_report(reference_df, current_df_drifted)
    assert {"drift_score", "drifted_features", "share_drifted", "report_path", "timestamp"} <= set(res.keys())


def test_run_drift_report_saves_html_report(reference_df, current_df_drifted):
    res = run_drift_report(reference_df, current_df_drifted)
    p = Path(res["report_path"])
    assert p.exists()
    assert p.suffix == ".html"


def test_load_reference_data_raises_if_missing(tmp_path):
    ref_path = Path(__file__).resolve().parents[1] / "ml" / "data" / "reference.csv"
    backup = None
    if ref_path.exists():
        backup = tmp_path / "reference_backup.csv"
        backup.write_bytes(ref_path.read_bytes())
        ref_path.unlink()
    try:
        with pytest.raises(FileNotFoundError):
            load_reference_data()
    finally:
        if backup is not None:
            ref_path.parent.mkdir(parents=True, exist_ok=True)
            ref_path.write_bytes(backup.read_bytes())


def test_psi_score_is_symmetric():
    rng = np.random.default_rng(2)
    a = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    b = pd.Series(rng.normal(loc=1.0, scale=1.0, size=2000))
    psi_ab = get_psi_score(a, b)
    psi_ba = get_psi_score(b, a)
    assert psi_ab == pytest.approx(psi_ba, rel=0.05, abs=0.01)
