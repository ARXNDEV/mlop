import os
import sys
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import MagicMock

import fakeredis
import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
ML_DIR = ROOT / "ml"

sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(ML_DIR))


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    os.environ["MODEL_NAME"] = "income-classifier"
    os.environ["AB_SPLIT_PERCENT"] = "20"
    os.environ["DRIFT_THRESHOLD"] = "0.15"
    os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5999"
    os.environ["MLFLOW_EXPERIMENT_NAME"] = "mlops-platform"
    os.environ["SKIP_REGISTRY_LOAD"] = "1"
    os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "0"


@pytest.fixture
def mock_model_v1() -> MagicMock:
    m = MagicMock()
    m.predict.return_value = np.array([0])
    m.predict_proba.return_value = np.array([[0.8, 0.2]])
    return m


@pytest.fixture
def mock_model_v2() -> MagicMock:
    m = MagicMock()
    m.predict.return_value = np.array([1])
    m.predict_proba.return_value = np.array([[0.3, 0.7]])
    return m


@pytest.fixture
def sample_predict_request() -> dict:
    return {"features": [0.1] * 10, "user_id": "test-user", "return_proba": False}


@pytest.fixture
def redis_mock():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def reference_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    x = rng.normal(loc=0.0, scale=1.0, size=(100, 10))
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(10)])
    df["target"] = rng.integers(0, 2, size=(100,))
    return df


@pytest.fixture
def current_df_drifted() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    x = rng.normal(loc=1.5, scale=1.0, size=(100, 10))
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(10)])
    df["target"] = rng.integers(0, 2, size=(100,))
    return df


@pytest_asyncio.fixture
async def client(
    mock_model_v1: MagicMock, mock_model_v2: MagicMock, redis_mock
) -> AsyncIterator[AsyncClient]:
    from main import app

    await app.router.startup()

    app.state.model_manager.models = {"v1": mock_model_v1, "v2": mock_model_v2}
    app.state.models = app.state.model_manager.models
    app.state.ab_tracker.redis = redis_mock
    app.state.drift_state = {"history": [], "features": {}, "latest_report_path": None}
    app.state.retrain_events = []

    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield ac
    finally:
        await ac.aclose()
        await app.router.shutdown()
