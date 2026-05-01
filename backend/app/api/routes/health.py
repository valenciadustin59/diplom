from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.health import build_liveness_payload, build_metrics_payload, build_readiness_payload
from app.model_monitoring import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS, MIN_WINDOW_DAYS, build_model_monitoring_payload
from app.model_status import build_model_status_payload

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness_endpoint() -> dict[str, Any]:
    return build_liveness_payload()


@router.get("/health/ready")
def readiness_endpoint() -> JSONResponse:
    payload, is_ready = build_readiness_payload()
    return JSONResponse(status_code=200 if is_ready else 503, content=payload)


@router.get("/health/metrics")
def metrics_endpoint() -> dict[str, Any]:
    return build_metrics_payload()


@router.get("/health/model")
def model_status_endpoint() -> dict[str, Any]:
    return build_model_status_payload()


@router.get("/health/model/monitoring")
def model_monitoring_endpoint(
    window_days: int = Query(DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    return build_model_monitoring_payload(
        db,
        window_days=window_days,
        active_model_status=build_model_status_payload(),
    )
