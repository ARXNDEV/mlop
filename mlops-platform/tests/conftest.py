import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
import pytest_asyncio


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
ML_DIR = ROOT / "ml"

sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(ML_DIR))


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    os.environ.setdefault("MODEL_NAME", "income-classifier")
    os.environ.setdefault("AB_SPLIT_PERCENT", "20")
    os.environ.setdefault("DRIFT_THRESHOLD", "0.15")
    os.environ.setdefault("MLFLOW_TRACKING_URI", "http://127.0.0.1:5999")
    os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", "mlops-platform")
    os.environ.setdefault("SKIP_REGISTRY_LOAD", "1")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "0")
    yield


@pytest.fixture(scope="session", autouse=True)
def _ensure_local_model():
    from sklearn.ensemble import RandomForestClassifier

    from ml.train import generate_dataset, split_dataset

    df = generate_dataset(n_samples=800, random_state=42)
    train_df, _, _ = split_dataset(df, random_state=42)
    x_train = train_df.drop(columns=["target"]).to_numpy()
    y_train = train_df["target"].to_numpy()

    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(x_train, y_train)

    out = ML_DIR / "models" / "current" / "model.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    pd.to_pickle(model, out)
    return out


@pytest_asyncio.fixture
async def async_client():
    from main import app

    await app.router.startup()
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await app.router.shutdown()
