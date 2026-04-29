"""Pydantic schemas used by the FastAPI application."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    features: list[float] = Field(min_length=10, max_length=10)
    user_id: str
    return_proba: bool = False


class PredictResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prediction: int = Field(ge=0, le=1)
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str = Field(pattern="^(v1|v2)$")
    latency_ms: float
    request_id: UUID


class ABTestSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    version: str = Field(pattern="^(v1|v2)$")
    n_requests: int
    avg_latency_ms: float
    avg_confidence: float
    accuracy: Optional[float]
    p_value: Optional[float]


class DriftReport(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    timestamp: datetime
    drift_score: float
    share_drifted: float
    drifted_features: list[str]
    is_drift_detected: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    status: str
    models_loaded: dict[str, bool]
    uptime_seconds: float
    version: str
