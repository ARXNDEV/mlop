"""Deterministic A/B routing and Redis-backed A/B aggregation."""

import logging
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import redis
from scipy.stats import ttest_ind

from models.schemas import ABTestSummary


logger = logging.getLogger(__name__)

def route_request(user_id: str, split_percent: int) -> str:
    h = hashlib.md5(user_id.encode("utf-8")).hexdigest()
    bucket = int(h, 16) % 100
    return "v2" if bucket < int(split_percent) else "v1"


class _InMemoryPipeline:
    def __init__(self, store: dict) -> None:
        self._store = store
        self._ops: list[tuple[str, tuple]] = []

    def hincrby(self, key: str, field: str, amount: int):
        self._ops.append(("hincrby", (key, field, amount)))
        return self

    def hincrbyfloat(self, key: str, field: str, amount: float):
        self._ops.append(("hincrbyfloat", (key, field, amount)))
        return self

    def rpush(self, key: str, value: int):
        self._ops.append(("rpush", (key, value)))
        return self

    def ltrim(self, key: str, start: int, end: int):
        self._ops.append(("ltrim", (key, start, end)))
        return self

    def execute(self):
        for op, args in self._ops:
            getattr(_InMemoryRedis(self._store), op)(*args)
        self._ops.clear()
        return True


class _InMemoryRedis:
    def __init__(self, store: dict) -> None:
        self._store = store

    def pipeline(self):
        return _InMemoryPipeline(self._store)

    def hincrby(self, key: str, field: str, amount: int):
        h = self._store.setdefault(key, {})
        h[field] = int(h.get(field, 0)) + int(amount)
        return h[field]

    def hincrbyfloat(self, key: str, field: str, amount: float):
        h = self._store.setdefault(key, {})
        h[field] = float(h.get(field, 0.0)) + float(amount)
        return h[field]

    def hgetall(self, key: str):
        return dict(self._store.get(key, {}))

    def rpush(self, key: str, value: int):
        lst = self._store.setdefault(key, [])
        lst.append(value)
        return len(lst)

    def ltrim(self, key: str, start: int, end: int):
        lst = self._store.get(key, [])
        if end == -1:
            self._store[key] = lst[start:]
        else:
            self._store[key] = lst[start : end + 1]
        return True

    def lrange(self, key: str, start: int, end: int):
        lst = self._store.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)
        return True


class ABTestTracker:
    def __init__(self, redis_url: Optional[str] = None, redis_client=None) -> None:
        if redis_client is not None:
            self.redis = redis_client
            return

        url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379")
        try:
            r = redis.Redis.from_url(url, decode_responses=True)
            r.ping()
            self.redis = r
        except Exception:
            self.redis = _InMemoryRedis({})

    def record_request(
        self,
        version: str,
        latency_ms: float,
        confidence: float,
        label: Optional[int] = None,
    ) -> None:
        version = str(version)
        counters_key = f"ab_test:{version}:counters"
        pipe = self.redis.pipeline()
        pipe.hincrby(counters_key, "n_requests", 1)
        pipe.hincrbyfloat(counters_key, "sum_latency_ms", float(latency_ms))
        pipe.hincrbyfloat(counters_key, "sum_confidence", float(confidence))

        hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        pipe.hincrby(f"ab_test:{version}:history", hour, 1)

        if label is not None:
            pipe.rpush(f"ab_test:{version}:accuracies", int(label))
            pipe.ltrim(f"ab_test:{version}:accuracies", -5000, -1)

        pipe.execute()

    def _get_list(self, key: str) -> list[float]:
        vals = self.redis.lrange(key, 0, -1)
        out: list[float] = []
        for v in vals:
            try:
                out.append(float(v))
            except Exception:
                continue
        return out

    def compute_statistical_significance(
        self, v1_accuracies: list[float], v2_accuracies: list[float]
    ) -> Optional[float]:
        if len(v1_accuracies) < 30 or len(v2_accuracies) < 30:
            return None
        a = np.asarray(v1_accuracies, dtype=float)
        b = np.asarray(v2_accuracies, dtype=float)
        _, p = ttest_ind(a, b, equal_var=False)
        return float(p)

    def get_summary(self, version: str) -> ABTestSummary:
        version = str(version)
        counters_key = f"ab_test:{version}:counters"
        counters = self.redis.hgetall(counters_key)

        n = int(float(counters.get("n_requests", 0)))
        sum_latency = float(counters.get("sum_latency_ms", 0.0))
        sum_conf = float(counters.get("sum_confidence", 0.0))

        avg_latency = (sum_latency / n) if n else 0.0
        avg_conf = (sum_conf / n) if n else 0.0

        acc_list = self._get_list(f"ab_test:{version}:accuracies")
        accuracy = float(np.mean(acc_list)) if acc_list else None

        p_value: Optional[float] = None
        if version == "v1":
            p_value = self.compute_statistical_significance(
                acc_list, self._get_list("ab_test:v2:accuracies")
            )
        if version == "v2":
            p_value = self.compute_statistical_significance(
                self._get_list("ab_test:v1:accuracies"), acc_list
            )

        return ABTestSummary(
            version=version,
            n_requests=n,
            avg_latency_ms=float(avg_latency),
            avg_confidence=float(avg_conf),
            accuracy=accuracy,
            p_value=p_value,
        )

    def get_winner(self) -> str:
        s1 = self.get_summary("v1")
        s2 = self.get_summary("v2")
        if s1.accuracy is None or s2.accuracy is None:
            return "inconclusive"
        p = self.compute_statistical_significance(
            self._get_list("ab_test:v1:accuracies"),
            self._get_list("ab_test:v2:accuracies"),
        )
        if p is None or p >= 0.05:
            return "inconclusive"
        return "v2" if float(s2.accuracy) > float(s1.accuracy) else "v1"

    def reset(self) -> None:
        keys = [
            "ab_test:v1:counters",
            "ab_test:v2:counters",
            "ab_test:v1:accuracies",
            "ab_test:v2:accuracies",
            "ab_test:v1:history",
            "ab_test:v2:history",
        ]
        self.redis.delete(*keys)
