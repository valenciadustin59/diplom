from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.health import build_liveness_payload, build_metrics_payload, build_readiness_payload
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
