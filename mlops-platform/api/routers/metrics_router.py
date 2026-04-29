"""Prometheus scrape endpoint and dashboard-friendly metric APIs."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest
from prometheus_client.registry import REGISTRY
from starlette.responses import Response


logger = logging.getLogger(__name__)


def _get_or_create(name: str, factory):
    existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
    if existing is not None:
        return existing
    return factory()


router = APIRouter(tags=["metrics"])


model_drift_score: Gauge = _get_or_create(
    "model_drift_score",
    lambda: Gauge("model_drift_score", "Model drift score", labelnames=["model_name"]),
)
model_accuracy: Gauge = _get_or_create(
    "model_accuracy",
    lambda: Gauge("model_accuracy", "Model accuracy", labelnames=["model_version"]),
)
ab_split_percent: Gauge = _get_or_create(
    "ab_split_percent",
    lambda: Gauge("ab_split_percent", "A/B split percent routed to v2"),
)
active_model_version: Info = _get_or_create(
    "active_model_version",
    lambda: Info("active_model_version", "Active model versions and metadata"),
)

http_request_duration_ms: Histogram = _get_or_create(
    "http_request_duration_ms",
    lambda: Histogram(
        "http_request_duration_ms",
        "HTTP request duration in milliseconds",
        labelnames=["method", "path", "status"],
        buckets=(5, 10, 25, 50, 75, 100, 150, 250, 500, 1000, 2500, 5000, float("inf")),
    ),
)
http_requests_total: Counter = _get_or_create(
    "http_requests_total",
    lambda: Counter(
        "http_requests_total", "HTTP requests total", labelnames=["method", "path", "status"]
    ),
)

prediction_requests_total: Counter = _get_or_create(
    "prediction_requests_total",
    lambda: Counter(
        "prediction_requests_total",
        "Prediction requests total",
        labelnames=["model_version"],
    ),
)
prediction_confidence: Histogram = _get_or_create(
    "prediction_confidence",
    lambda: Histogram(
        "prediction_confidence",
        "Prediction confidence distribution",
        labelnames=["model_version"],
        buckets=(0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.0),
    ),
)

retrain_events_total: Counter = _get_or_create(
    "retrain_events_total",
    lambda: Counter("retrain_events_total", "Retrain events total", labelnames=["reason"]),
)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _histogram_p95(h: Histogram) -> float:
    try:
        samples = h.collect()[0].samples
    except Exception:
        return 0.0

    counts: dict[float, float] = {}
    total = 0.0
    for s in samples:
        if not s.name.endswith("_bucket"):
            continue
        le = float(s.labels.get("le", "inf"))
        counts[le] = counts.get(le, 0.0) + float(s.value)
        if le == float("inf"):
            total = float(s.value)

    if total <= 0:
        return 0.0

    target = 0.95 * total
    running = 0.0
    for le in sorted(counts.keys()):
        running = counts[le]
        if running >= target:
            return float(le if le != float("inf") else 0.0)
    return 0.0


@router.get("/metrics/summary")
def metrics_summary() -> dict[str, Any]:
    drift: dict[str, float] = {}
    for s in model_drift_score.collect()[0].samples:
        if s.name == "model_drift_score":
            drift[s.labels.get("model_name", "")] = float(s.value)

    acc: dict[str, float] = {}
    for s in model_accuracy.collect()[0].samples:
        if s.name == "model_accuracy":
            acc[s.labels.get("model_version", "")] = float(s.value)

    split = 0.0
    for s in ab_split_percent.collect()[0].samples:
        if s.name == "ab_split_percent":
            split = float(s.value)

    active_info: dict[str, str] = {}
    for s in active_model_version.collect()[0].samples:
        if s.name == "active_model_version_info":
            active_info = {k: str(v) for k, v in s.labels.items()}

    p95 = _histogram_p95(http_request_duration_ms)

    return {
        "model_accuracy": acc,
        "model_drift_score": drift,
        "p95_latency_ms": float(p95),
        "ab_split_percent": float(split),
        "active_model_version": active_info,
    }


def _drift_state(request: Request) -> dict[str, Any]:
    state = getattr(request.app, "state", None)
    if not state:
        return {"history": [], "features": {}, "latest_report_path": None}
    ds = getattr(state, "drift_state", None)
    if not isinstance(ds, dict):
        return {"history": [], "features": {}, "latest_report_path": None}
    ds.setdefault("history", [])
    ds.setdefault("features", {})
    ds.setdefault("latest_report_path", None)
    return ds


def _retrain_events(request: Request) -> list[dict[str, Any]]:
    state = getattr(request.app, "state", None)
    events = getattr(state, "retrain_events", None) if state else None
    if not isinstance(events, list):
        return []
    return events


@router.get("/metrics/drift/history")
def drift_history(request: Request, hours: int = 24) -> list[dict[str, Any]]:
    if hours <= 0 or hours > 24 * 30:
        raise HTTPException(status_code=422, detail="hours must be within (0, 720]")

    ds = _drift_state(request)
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - int(hours) * 3600 * 1000
    history: list[tuple[int, float]] = ds.get("history", [])

    out: list[dict[str, Any]] = []
    for ts, score in history:
        if ts >= cutoff:
            out.append({"timestamp": int(ts), "drift_score": float(score)})
    return out


@router.get("/metrics/drift/features")
def drift_features(request: Request) -> list[dict[str, Any]]:
    ds = _drift_state(request)
    features: dict[str, dict[str, Any]] = ds.get("features", {})
    out: list[dict[str, Any]] = []
    for name, info in features.items():
        out.append(
            {
                "feature": str(name),
                "psi": float(info.get("psi", 0.0)),
                "drift_detected": bool(info.get("drift_detected", False)),
                "trend": list(info.get("trend", [])),
            }
        )
    out.sort(key=lambda x: float(x["psi"]), reverse=True)
    return out


@router.get("/metrics/retrain/events")
def retrain_events(request: Request) -> list[dict[str, Any]]:
    return _retrain_events(request)[:5]


@router.get("/metrics/drift/report/latest", include_in_schema=False)
def latest_drift_report(request: Request) -> Response:
    ds = _drift_state(request)
    p: Optional[str] = ds.get("latest_report_path")

    candidate_paths: list[Path] = []
    if p:
        candidate_paths.append(Path(p))
    candidate_paths.append(Path("/app/ml/reports"))
    candidate_paths.append(Path(__file__).resolve().parents[2] / "ml" / "reports")

    html_path: Optional[Path] = None
    for base in candidate_paths:
        if base.is_dir():
            files = sorted(base.glob("drift_*.html"))
            if files:
                html_path = files[-1]
                break
        elif base.is_file() and base.suffix == ".html":
            html_path = base
            break

    if not html_path or not html_path.exists():
        raise HTTPException(status_code=404, detail="No drift report available")

    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.exception("drift_report_read_failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return Response(content=html, media_type="text/html")
