import numpy as np
import pytest

from core.ab_router import ABTestTracker, route_request


def test_same_user_id_always_routes_to_same_version():
    a = route_request("user-1", 20)
    b = route_request("user-1", 20)
    assert a == b


def test_different_user_ids_produce_both_versions_over_1000_calls():
    out = {route_request(f"user-{i}", 50) for i in range(1000)}
    assert out == {"v1", "v2"}


def test_split_0_all_v1():
    assert all(route_request(f"user-{i}", 0) == "v1" for i in range(1000))


def test_split_100_all_v2():
    assert all(route_request(f"user-{i}", 100) == "v2" for i in range(1000))


def test_split_20_approx_20_percent_v2():
    n = 2000
    v2 = sum(1 for i in range(n) if route_request(f"user-{i}", 20) == "v2")
    frac = v2 / n
    assert frac == pytest.approx(0.20, abs=0.05)


def test_record_request_stores_data_in_redis(redis_mock):
    t = ABTestTracker(redis_client=redis_mock)
    t.reset()
    t.record_request("v1", latency_ms=12.0, confidence=0.7, label=1)
    assert int(redis_mock.hget("ab_test:v1:counters", "n_requests") or 0) == 1


def test_get_summary_returns_correct_averages(redis_mock):
    t = ABTestTracker(redis_client=redis_mock)
    t.reset()
    t.record_request("v1", latency_ms=10.0, confidence=0.5, label=1)
    t.record_request("v1", latency_ms=30.0, confidence=1.0, label=0)
    s = t.get_summary("v1")
    assert s.n_requests == 2
    assert s.avg_latency_ms == pytest.approx(20.0, abs=1e-6)
    assert s.avg_confidence == pytest.approx(0.75, abs=1e-6)


def test_compute_statistical_significance_returns_p_lt_005_for_different_groups(redis_mock):
    t = ABTestTracker(redis_client=redis_mock)
    a = list(np.ones(200))
    b = list(np.zeros(200))
    p = t.compute_statistical_significance(a, b)
    assert p is not None
    assert p < 0.05
