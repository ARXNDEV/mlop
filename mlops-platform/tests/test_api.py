import pytest


@pytest.mark.asyncio
async def test_post_predict_returns_200_with_schema(client, sample_predict_request):
    r = await client.post("/predict", json=sample_predict_request)
    assert r.status_code == 200
    body = r.json()
    assert body["prediction"] in [0, 1]
    assert 0.0 <= float(body["confidence"]) <= 1.0
    assert body["model_version"] in ["v1", "v2"]
    assert float(body["latency_ms"]) >= 0.0
    assert "request_id" in body


@pytest.mark.asyncio
async def test_post_predict_wrong_feature_count_returns_422(client, sample_predict_request):
    bad = dict(sample_predict_request)
    bad["features"] = [0.1] * 9
    r = await client.post("/predict", json=bad)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_predict_v1_always_uses_v1_model(client, sample_predict_request, mock_model_v1):
    r = await client.post("/predict/v1", json=sample_predict_request)
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "v1"
    assert body["prediction"] == 0
    mock_model_v1.predict.assert_called()


@pytest.mark.asyncio
async def test_post_predict_v2_always_uses_v2_model(client, sample_predict_request, mock_model_v2):
    r = await client.post("/predict/v2", json=sample_predict_request)
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "v2"
    assert body["prediction"] == 1
    mock_model_v2.predict.assert_called()


@pytest.mark.asyncio
async def test_post_predict_batch_with_5_returns_5(client, sample_predict_request):
    r = await client.post("/predict/batch", json=[sample_predict_request] * 5)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 5


@pytest.mark.asyncio
async def test_post_predict_batch_101_returns_422(client, sample_predict_request):
    r = await client.post("/predict/batch", json=[sample_predict_request] * 101)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_health_returns_200(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "models_loaded" in body


@pytest.mark.asyncio
async def test_get_metrics_returns_text_plain(client):
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_get_ab_summary_returns_both_versions(client):
    r = await client.get("/ab-test/summary")
    assert r.status_code == 200
    body = r.json()
    versions = {b["version"] for b in body}
    assert versions == {"v1", "v2"}


@pytest.mark.asyncio
async def test_post_ab_split_50_updates_split(client):
    r = await client.post("/ab-test/split", json={"split_percent": 50})
    assert r.status_code == 200
    assert r.json()["split_percent"] == 50


@pytest.mark.asyncio
async def test_post_ab_split_101_returns_422(client):
    r = await client.post("/ab-test/split", json={"split_percent": 101})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_ab_reset_clears_counters(client, sample_predict_request):
    await client.post("/predict/v1", json=sample_predict_request)
    await client.post("/predict/v2", json=sample_predict_request)
    r = await client.post("/ab-test/reset")
    assert r.status_code == 200
    r2 = await client.get("/ab-test/summary")
    assert r2.status_code == 200
    body = r2.json()
    assert all(int(b["n_requests"]) == 0 for b in body)
