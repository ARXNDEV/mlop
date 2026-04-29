"""ASGI middleware for request IDs, latency tracking, and Prometheus metrics."""

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from routers.metrics_router import http_request_duration_ms, http_requests_total


logger = logging.getLogger(__name__)


class LatencyTrackerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in {"/health", "/metrics"} or path.startswith("/metrics/"):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000.0
            http_request_duration_ms.labels(
                method=request.method, path=path, status="500"
            ).observe(latency_ms)
            http_requests_total.labels(method=request.method, path=path, status="500").inc()
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": path,
                    "status_code": 500,
                    "latency_ms": latency_ms,
                    "request_id": request_id,
                },
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000.0
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers["X-Latency-Ms"] = f"{latency_ms:.3f}"

        status = str(response.status_code)
        http_request_duration_ms.labels(method=request.method, path=path, status=status).observe(
            latency_ms
        )
        http_requests_total.labels(method=request.method, path=path, status=status).inc()

        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "request_id": request_id,
            },
        )
        return response
