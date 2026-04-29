from core.ab_router import ABTestTracker, route_request


def test_route_request_deterministic():
    a = route_request("user-1", 20)
    b = route_request("user-1", 20)
    assert a == b


def test_ab_tracker_increments():
    t = ABTestTracker(redis_url="redis://127.0.0.1:6399")
    t.reset()
    t.record_request("v1", latency_ms=12.0, confidence=0.7, label=1)
    t.record_request("v1", latency_ms=20.0, confidence=0.9, label=0)
    s = t.get_summary("v1")
    assert s.n_requests == 2
    assert s.avg_latency_ms > 0
    assert s.avg_confidence > 0
