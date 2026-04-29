import time

from fastapi import APIRouter, Request

from models.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    start = float(getattr(request.app.state, "start_time", time.time()))
    mm = getattr(request.app.state, "model_manager", None)
    models_loaded = {
        "v1": bool(mm and mm.models.get("v1") is not None),
        "v2": bool(mm and mm.models.get("v2") is not None),
    }
    return HealthResponse(
        status="ok",
        models_loaded=models_loaded,
        uptime_seconds=float(time.time() - start),
        version=str(getattr(request.app.state, "version", "0.1.0")),
    )
