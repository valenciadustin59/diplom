from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.health import build_liveness_payload, build_readiness_payload

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
