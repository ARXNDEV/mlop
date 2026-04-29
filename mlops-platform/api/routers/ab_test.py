"""A/B test management endpoints backed by Redis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.ab_router import ABTestTracker
from models.schemas import ABTestSummary
from routers.metrics_router import ab_split_percent


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ab-test", tags=["ab-test"])

class SplitUpdateRequest(BaseModel):
    split_percent: int = Field(ge=0, le=100)


@router.get("/summary", response_model=list[ABTestSummary])
def summary(request: Request) -> list[ABTestSummary]:
    tracker: ABTestTracker = request.app.state.ab_tracker
    return [tracker.get_summary("v1"), tracker.get_summary("v2")]


@router.get("/winner")
def winner(request: Request) -> dict:
    tracker: ABTestTracker = request.app.state.ab_tracker
    w = tracker.get_winner()
    p = tracker.compute_statistical_significance(
        tracker._get_list("ab_test:v1:accuracies"),
        tracker._get_list("ab_test:v2:accuracies"),
    )
    return {"winner": w, "p_value": p}


@router.post("/reset")
def reset(request: Request) -> dict:
    tracker: ABTestTracker = request.app.state.ab_tracker
    tracker.reset()
    return {"status": "ok"}


@router.post("/split")
def set_split(
    request: Request,
    body: SplitUpdateRequest,
) -> dict:
    try:
        split_percent = int(body.split_percent)
        request.app.state.ab_split_percent = split_percent
        ab_split_percent.set(float(split_percent))
        return {"split_percent": split_percent}
    except Exception as e:
        logger.exception("split_update_failed")
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/history")
def history(request: Request) -> dict:
    tracker: ABTestTracker = request.app.state.ab_tracker
    now = datetime.now(timezone.utc)
    hours = [(now - timedelta(hours=i)).strftime("%Y%m%d%H") for i in range(0, 24)]
    hours = list(reversed(hours))

    def _series(version: str) -> list[dict]:
        raw = tracker.redis.hgetall(f"ab_test:{version}:history")
        out = []
        for h in hours:
            out.append({"hour": h, "count": int(float(raw.get(h, 0)))})
        return out

    return {"v1": _series("v1"), "v2": _series("v2")}
