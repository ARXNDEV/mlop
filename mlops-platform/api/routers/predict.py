"""Prediction endpoints (single, forced version, and batch)."""

import logging
import asyncio
import time
from typing import Optional
from uuid import UUID, uuid4

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from core.ab_router import ABTestTracker, route_request
from models.schemas import PredictRequest, PredictResponse
from routers.metrics_router import prediction_confidence, prediction_requests_total


logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])


def _predict_with_model(model, features: list[float]) -> tuple[int, float]:
    x = np.asarray(features, dtype=float).reshape(1, -1)
    pred = int(model.predict(x)[0])
    proba = float(model.predict_proba(x)[0][1])
    confidence = proba if pred == 1 else 1.0 - proba
    return pred, confidence


async def _predict_one(
    request: Request, payload: PredictRequest, forced_version: Optional[str]
) -> PredictResponse:
    split = int(getattr(request.app.state, "ab_split_percent", 20))
    version = forced_version or route_request(payload.user_id, split)

    mm = request.app.state.model_manager
    model = mm.get_model(version)

    request_id = UUID(request.headers.get("X-Request-ID") or str(uuid4()))

    start = time.perf_counter()
    pred, conf = await asyncio.to_thread(_predict_with_model, model, payload.features)
    latency_ms = (time.perf_counter() - start) * 1000.0

    tracker: ABTestTracker = request.app.state.ab_tracker
    tracker.record_request(version=version, latency_ms=latency_ms, confidence=conf, label=None)

    prediction_requests_total.labels(model_version=version).inc()
    prediction_confidence.labels(model_version=version).observe(conf)

    return PredictResponse(
        prediction=pred,
        confidence=float(conf),
        model_version=version,
        latency_ms=float(latency_ms),
        request_id=request_id,
    )


@router.post("/predict", response_model=PredictResponse)
async def predict(request: Request, payload: PredictRequest) -> PredictResponse:
    return await _predict_one(request, payload, forced_version=None)


@router.post("/predict/v1", response_model=PredictResponse)
async def predict_v1(request: Request, payload: PredictRequest) -> PredictResponse:
    return await _predict_one(request, payload, forced_version="v1")


@router.post("/predict/v2", response_model=PredictResponse)
async def predict_v2(request: Request, payload: PredictRequest) -> PredictResponse:
    return await _predict_one(request, payload, forced_version="v2")


@router.post("/predict/batch", response_model=list[PredictResponse])
async def predict_batch(request: Request, payloads: list[PredictRequest]) -> list[PredictResponse]:
    if len(payloads) > 100:
        raise HTTPException(status_code=422, detail="batch size exceeds max=100")
    tasks = [_predict_one(request, p, forced_version=None) for p in payloads]
    return await asyncio.gather(*tasks)
