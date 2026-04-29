import numpy as np
import pandas as pd

from ml.drift_detector import get_psi_score, is_drift_detected


def test_psi_score_detects_shift():
    rng = np.random.default_rng(42)
    ref = pd.Series(rng.normal(loc=0.0, scale=1.0, size=2000))
    cur = pd.Series(rng.normal(loc=1.0, scale=1.0, size=2000))
    psi = get_psi_score(ref, cur)
    assert psi > 0.1


def test_is_drift_detected_threshold():
    assert is_drift_detected(0.2, threshold=0.15) is True
    assert is_drift_detected(0.1, threshold=0.15) is False
