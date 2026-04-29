"""FastAPI application for model serving, A/B testing, and observability."""

import logging
import os
import time
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.ab_router import ABTestTracker
from core.model_loader import ModelManager
from middleware.latency_tracker import LatencyTrackerMiddleware
from routers import ab_test, health, metrics_router, predict
from routers.metrics_router import (
    ab_split_percent,
    active_model_version,
    model_drift_score,
    retrain_events_total,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mlops.api")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid4())


def _json_error(request: Request, *, status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "request_id": _request_id(request)},
    )


app = FastAPI(
    title="mlops-platform API",
    version="0.1.0",
    description="FastAPI serving layer for deterministic A/B testing, monitoring metrics, and hot-reloading MLflow registry models.",
    openapi_tags=[
        {"name": "health", "description": "Service health and uptime."},
        {"name": "predict", "description": "Prediction endpoints (single, forced version, batch)."},
        {"name": "ab-test", "description": "A/B testing controls and summaries backed by Redis."},
        {"name": "metrics", "description": "Prometheus scrape endpoint and dashboard-friendly summaries."},
        {"name": "admin", "description": "Admin-only endpoints for model reload and drift updates."},
    ],
)


app.add_middleware(LatencyTrackerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health.router)
app.include_router(predict.router)
app.include_router(ab_test.router)
app.include_router(metrics_router.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return _json_error(request, status_code=422, error="validation_error", detail=str(exc))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return _json_error(request, status_code=exc.status_code, error="http_error", detail=str(exc.detail))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"path": request.url.path, "request_id": _request_id(request)})
    return _json_error(request, status_code=500, error="internal_error", detail=str(exc))


@app.on_event("startup")
async def on_startup() -> None:
    app.state.start_time = time.time()
    app.state.version = app.version
    app.state.ab_tracker = ABTestTracker(_env("REDIS_URL"))
    app.state.drift_state = {"history": [], "features": {}, "latest_report_path": None}
    app.state.retrain_events = []

    split = int(_env("AB_SPLIT_PERCENT", "20") or "20")
    if split < 0 or split > 100:
        raise RuntimeError("AB_SPLIT_PERCENT must be between 0 and 100")
    app.state.ab_split_percent = split
    ab_split_percent.set(float(split))

    mm = ModelManager()
    mm.load_all()
    app.state.model_manager = mm
    app.state.models = mm.models

    info = mm.get_model_info()
    active_model_version.info(
        {
            "production_version": str((info.get("Production") or {}).get("version", "")),
            "staging_version": str((info.get("Staging") or {}).get("version", "")),
        }
    )

    logger.info(
        "startup_complete",
        extra={
            "ab_split_percent": split,
            "models_loaded": {"v1": mm.models.get("v1") is not None, "v2": mm.models.get("v2") is not None},
            "model_info": info,
        },
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("shutdown")


@app.post("/admin/reload", tags=["admin"])
async def admin_reload(request: Request) -> dict[str, Any]:
    mm: ModelManager = request.app.state.model_manager
    mm.reload()
    request.app.state.models = mm.models
    info = mm.get_model_info()
    active_model_version.info(
        {
            "production_version": str((info.get("Production") or {}).get("version", "")),
            "staging_version": str((info.get("Staging") or {}).get("version", "")),
        }
    )
    try:
        retrain_events_total.labels(reason="manual_reload").inc()
        request.app.state.retrain_events.insert(
            0,
            {"timestamp": int(time.time() * 1000), "reason": "manual_reload", "run_id": None},
        )
        request.app.state.retrain_events = request.app.state.retrain_events[:50]
    except Exception:
        pass
    return {"status": "ok", "model_info": info}


@app.post("/admin/drift", tags=["admin"])
async def admin_set_drift(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    model_name = str(payload.get("model_name") or _env("MODEL_NAME", "income-classifier") or "income-classifier")
    drift_score = float(payload.get("drift_score", 0.0))
    model_drift_score.labels(model_name=model_name).set(drift_score)

    ts = int(time.time() * 1000)
    drift_state: dict[str, Any] = request.app.state.drift_state
    drift_state["history"].append((ts, drift_score))
    drift_state["history"] = drift_state["history"][-24 * 30 :]

    features = payload.get("features")
    if isinstance(features, list):
        for f in features:
            if not isinstance(f, dict):
                continue
            name = str(f.get("feature", ""))
            if not name:
                continue
            psi = float(f.get("psi", 0.0))
            drifted = bool(f.get("drift_detected", psi >= 0.2))
            cur = drift_state["features"].get(name, {"trend": []})
            trend = list(cur.get("trend", []))
            trend.append(psi)
            drift_state["features"][name] = {"psi": psi, "drift_detected": drifted, "trend": trend[-168:]}

    report_path = payload.get("report_path")
    if isinstance(report_path, str) and report_path:
        drift_state["latest_report_path"] = report_path

    return {"status": "ok", "model_name": model_name, "drift_score": drift_score}


@app.post("/admin/retrain-event", tags=["admin"])
async def admin_retrain_event(payload: dict[str, Any]) -> dict[str, Any]:
    reason = str(payload.get("reason", "retrain"))
    run_id = payload.get("run_id")
    if run_id is not None:
        run_id = str(run_id)
    try:
        retrain_events_total.labels(reason=reason).inc()
    except Exception:
        pass
    request.app.state.retrain_events.insert(
        0,
        {"timestamp": int(time.time() * 1000), "reason": reason, "run_id": run_id},
    )
    request.app.state.retrain_events = request.app.state.retrain_events[:50]
    return {"status": "ok"}
