import logging
import os
import time
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.ab_router import ABTestTracker
from core.model_loader import ModelManager
from middleware.latency_tracker import LatencyTrackerMiddleware
from routers import ab_test, health, metrics_router, predict
from routers.metrics_router import ab_split_percent, active_model_version, model_drift_score


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mlops.api")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


app = FastAPI(
    title="mlops-platform API",
    version="0.1.0",
    description="FastAPI serving layer for deterministic A/B testing, monitoring metrics, and hot-reloading MLflow registry models.",
    openapi_tags=[
        {"name": "health", "description": "Service health and uptime."},
        {"name": "predict", "description": "Prediction endpoints (single, forced version, batch)."},
        {"name": "ab-test", "description": "A/B testing controls and summaries backed by Redis."},
        {"name": "metrics", "description": "Prometheus scrape endpoint and dashboard-friendly summaries."},
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"path": request.url.path})
    status_code = 500
    if isinstance(exc, ValueError):
        status_code = 400
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "path": request.url.path,
            }
        },
    )


@app.on_event("startup")
async def on_startup() -> None:
    app.state.start_time = time.time()
    app.state.version = app.version
    app.state.ab_tracker = ABTestTracker(_env("REDIS_URL"))

    split = int(_env("AB_SPLIT_PERCENT", "20") or "20")
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
    return {"status": "ok", "model_info": info}


@app.post("/admin/drift", tags=["admin"])
async def admin_set_drift(payload: dict[str, Any]) -> dict[str, Any]:
    model_name = str(_env("MODEL_NAME", "income-classifier") or "income-classifier")
    drift_score = float(payload.get("drift_score", 0.0))
    model_drift_score.labels(model_name=model_name).set(drift_score)
    return {"status": "ok", "model_name": model_name, "drift_score": drift_score}
