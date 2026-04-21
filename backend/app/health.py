from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from redis import Redis
from sqlalchemy import text

from app.celery_app import AUDIT_QUEUES, celery_app
from app.config import Settings, get_settings
from app.db import engine


@dataclass(slots=True)
class ComponentHealth:
    status: str
    required: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        details = payload.pop("details")
        payload.update(details)
        return payload


def _checked_at() -> str:
    return datetime.now(UTC).isoformat()


def check_database_health(settings: Settings) -> ComponentHealth:
    del settings
    database_url = engine.url.render_as_string(hide_password=False)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ComponentHealth(
            status="ok",
            required=True,
            details={"database_url": database_url},
        )
    except Exception as exc:  # pragma: no cover - defensive around SQLAlchemy driver stack
        return ComponentHealth(
            status="error",
            required=True,
            details={"database_url": database_url, "error": str(exc)},
        )


def check_redis_health(settings: Settings) -> ComponentHealth:
    client: Redis | None = None
    try:
        client = Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        client.ping()
        return ComponentHealth(
            status="ok",
            required=True,
            details={"broker_url": settings.celery_broker_url},
        )
    except Exception as exc:  # pragma: no cover - depends on redis client implementation
        return ComponentHealth(
            status="error",
            required=True,
            details={"broker_url": settings.celery_broker_url, "error": str(exc)},
        )
    finally:
        if client is not None:
            client.close()


def check_celery_worker_health(settings: Settings) -> ComponentHealth:
    del settings
    try:
        inspector = celery_app.control.inspect(timeout=0.5)
        ping_response = inspector.ping() or {}
        active_queues_response = inspector.active_queues() or {}
    except Exception as exc:  # pragma: no cover - depends on broker availability
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": 0,
                "workers": [],
                "worker_queues": {},
                "expected_queues": list(AUDIT_QUEUES),
                "error": str(exc),
            },
        )

    workers = sorted(ping_response.keys())
    worker_queues = {
        worker_name: sorted(
            queue_info.get("name", "")
            for queue_info in active_queues_response.get(worker_name, [])
            if isinstance(queue_info, dict) and queue_info.get("name")
        )
        for worker_name in workers
    }

    if not workers:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": 0,
                "workers": [],
                "worker_queues": {},
                "expected_queues": list(AUDIT_QUEUES),
                "error": "No Celery workers responded to ping.",
            },
        )

    missing_queues = sorted(
        queue_name
        for queue_name in AUDIT_QUEUES
        if not any(queue_name in queues for queues in worker_queues.values())
    )
    if missing_queues:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": len(workers),
                "workers": workers,
                "worker_queues": worker_queues,
                "expected_queues": list(AUDIT_QUEUES),
                "missing_queues": missing_queues,
                "error": "Not all expected audit queues are served by active workers.",
            },
        )

    return ComponentHealth(
        status="ok",
        required=True,
        details={
            "worker_count": len(workers),
            "workers": workers,
            "worker_queues": worker_queues,
            "expected_queues": list(AUDIT_QUEUES),
        },
    )


def check_serp_health(settings: Settings) -> ComponentHealth:
    if settings.serp_provider != "searxng":
        return ComponentHealth(
            status="skipped",
            required=False,
            details={"provider": settings.serp_provider, "reason": "SERP provider is not searxng."},
        )

    if not settings.searxng_base_url:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": None,
                "error": "SEARXNG_BASE_URL is not configured.",
            },
        )

    base_url = settings.searxng_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=min(settings.search_timeout, 5.0), follow_redirects=True) as client:
            response = client.get(
                f"{base_url}/search",
                params={
                    "q": "healthcheck",
                    "format": "json",
                    "categories": "general",
                    "language": settings.searxng_language,
                },
            )
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results", []) if isinstance(payload, dict) else []
        results_count = len(results) if isinstance(results, list) else 0
        return ComponentHealth(
            status="ok",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": base_url,
                "results_count": results_count,
            },
        )
    except Exception as exc:  # pragma: no cover - external network dependency
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": base_url,
                "error": str(exc),
            },
        )


def build_liveness_payload(settings: Settings | None = None) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    return {
        "status": "ok",
        "app_name": runtime_settings.app_name,
        "environment": runtime_settings.app_env,
        "checked_at": _checked_at(),
    }


def build_readiness_payload(settings: Settings | None = None) -> tuple[dict[str, Any], bool]:
    runtime_settings = settings or get_settings()
    checks = {
        "database": check_database_health(runtime_settings),
        "redis": check_redis_health(runtime_settings),
        "celery_workers": check_celery_worker_health(runtime_settings),
        "serp": check_serp_health(runtime_settings),
    }
    ready = all(
        component.status == "ok"
        for component in checks.values()
        if component.required
    )

    payload = {
        "status": "ready" if ready else "not_ready",
        "app_name": runtime_settings.app_name,
        "environment": runtime_settings.app_env,
        "checked_at": _checked_at(),
        "checks": {name: component.to_dict() for name, component in checks.items()},
        "orchestration": {
            "expected_queues": list(AUDIT_QUEUES),
            "broker_url": runtime_settings.celery_broker_url,
            "result_backend": runtime_settings.celery_result_backend,
        },
    }
    return payload, ready
