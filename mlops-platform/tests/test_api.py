import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    r = await async_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_predict_and_metrics(async_client):
    payload = {"features": [0.1] * 10, "user_id": "user-123", "return_proba": False}
    r = await async_client.post("/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] in {"v1", "v2"}
    assert body["prediction"] in {0, 1}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["latency_ms"] >= 0.0

    m = await async_client.get("/metrics")
    assert m.status_code == 200
    assert "text/plain" in m.headers["content-type"]

    s = await async_client.get("/metrics/summary")
    assert s.status_code == 200
    summary = s.json()
    assert "p95_latency_ms" in summary
