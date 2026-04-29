"""Minimal fakeredis-compatible in-memory Redis for local tests.

Implements a subset of the fakeredis API used by this repository's test suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class _PipelineOp:
    name: str
    args: tuple


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: List[_PipelineOp] = []

    def hincrby(self, key: str, field: str, amount: int):
        self._ops.append(_PipelineOp("hincrby", (key, field, amount)))
        return self

    def hincrbyfloat(self, key: str, field: str, amount: float):
        self._ops.append(_PipelineOp("hincrbyfloat", (key, field, amount)))
        return self

    def rpush(self, key: str, value: Any):
        self._ops.append(_PipelineOp("rpush", (key, value)))
        return self

    def ltrim(self, key: str, start: int, end: int):
        self._ops.append(_PipelineOp("ltrim", (key, start, end)))
        return self

    def execute(self):
        for op in self._ops:
            getattr(self._redis, op.name)(*op.args)
        self._ops.clear()
        return True


class FakeRedis:
    def __init__(self, decode_responses: bool = True) -> None:
        self._store: Dict[str, Any] = {}
        self._decode_responses = decode_responses

    def ping(self) -> bool:
        return True

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                n += 1
        return n

    def hincrby(self, key: str, field: str, amount: int) -> int:
        h = self._store.setdefault(key, {})
        if not isinstance(h, dict):
            h = {}
            self._store[key] = h
        h[field] = int(h.get(field, 0)) + int(amount)
        return int(h[field])

    def hincrbyfloat(self, key: str, field: str, amount: float) -> float:
        h = self._store.setdefault(key, {})
        if not isinstance(h, dict):
            h = {}
            self._store[key] = h
        h[field] = float(h.get(field, 0.0)) + float(amount)
        return float(h[field])

    def hgetall(self, key: str) -> Dict[str, str]:
        v = self._store.get(key, {})
        if not isinstance(v, dict):
            return {}
        return {str(k): str(val) for k, val in v.items()}

    def hget(self, key: str, field: str) -> Optional[str]:
        v = self._store.get(key, {})
        if not isinstance(v, dict):
            return None
        if field not in v:
            return None
        return str(v[field])

    def rpush(self, key: str, value: Any) -> int:
        lst = self._store.setdefault(key, [])
        if not isinstance(lst, list):
            lst = []
            self._store[key] = lst
        lst.append(value)
        return len(lst)

    def ltrim(self, key: str, start: int, end: int) -> bool:
        lst = self._store.get(key, [])
        if not isinstance(lst, list):
            return True
        if end == -1:
            self._store[key] = lst[start:]
        else:
            self._store[key] = lst[start : end + 1]
        return True

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        lst = self._store.get(key, [])
        if not isinstance(lst, list):
            return []
        if end == -1:
            out = lst[start:]
        else:
            out = lst[start : end + 1]
        return [str(x) for x in out]
