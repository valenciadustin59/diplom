import pytest

from app.celery_app import AUDIT_QUEUES
from app.config import Settings
from app.health import ComponentHealth, build_readiness_payload


def test_health_endpoint_returns_legacy_ok_payload(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_live_health_endpoint_returns_runtime_metadata(client):
    response = client.get("/health/live")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["app_name"]
    assert payload["environment"]
    assert payload["checked_at"]


def test_ready_health_endpoint_returns_200_when_dependencies_are_ready(client, monkeypatch: pytest.MonkeyPatch):
    payload = {
        "status": "ready",
        "app_name": "Site Audit API",
        "environment": "test",
        "checked_at": "2026-04-21T10:00:00+00:00",
        "checks": {
            "database": {"status": "ok", "required": True},
            "redis": {"status": "ok", "required": True},
            "celery_workers": {"status": "ok", "required": True},
            "serp": {"status": "ok", "required": True},
        },
        "orchestration": {
            "expected_queues": list(AUDIT_QUEUES),
            "broker_url": "redis://localhost:6379/0",
            "result_backend": "redis://localhost:6379/0",
        },
    }
    monkeypatch.setattr("app.api.routes.health.build_readiness_payload", lambda: (payload, True))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == payload


def test_ready_health_endpoint_returns_503_when_required_dependency_is_unavailable(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    payload = {
        "status": "not_ready",
        "app_name": "Site Audit API",
        "environment": "test",
        "checked_at": "2026-04-21T10:00:00+00:00",
        "checks": {
            "database": {"status": "ok", "required": True},
            "redis": {"status": "error", "required": True, "error": "redis unavailable"},
            "celery_workers": {"status": "ok", "required": True},
            "serp": {"status": "ok", "required": True},
        },
        "orchestration": {
            "expected_queues": list(AUDIT_QUEUES),
            "broker_url": "redis://localhost:6379/0",
            "result_backend": "redis://localhost:6379/0",
        },
    }
    monkeypatch.setattr("app.api.routes.health.build_readiness_payload", lambda: (payload, False))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == payload


def test_build_readiness_payload_includes_expected_queues(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        app_name="Site Audit API",
        app_env="test",
        celery_broker_url="redis://localhost:6379/0",
        celery_result_backend="redis://localhost:6379/0",
        serp_provider="searxng",
        searxng_base_url="http://127.0.0.1:8888",
    )
    monkeypatch.setattr(
        "app.health.check_database_health",
        lambda runtime_settings: ComponentHealth("ok", True, {"database_url": runtime_settings.database_url}),
    )
    monkeypatch.setattr(
        "app.health.check_redis_health",
        lambda runtime_settings: ComponentHealth("ok", True, {"broker_url": runtime_settings.celery_broker_url}),
    )
    monkeypatch.setattr(
        "app.health.check_celery_worker_health",
        lambda runtime_settings: ComponentHealth(
            "ok",
            True,
            {
                "worker_count": 1,
                "workers": ["celery@test"],
                "worker_queues": {"celery@test": list(AUDIT_QUEUES)},
                "expected_queues": list(AUDIT_QUEUES),
            },
        ),
    )
    monkeypatch.setattr(
        "app.health.check_serp_health",
        lambda runtime_settings: ComponentHealth(
            "ok",
            True,
            {"provider": runtime_settings.serp_provider, "base_url": runtime_settings.searxng_base_url},
        ),
    )

    payload, is_ready = build_readiness_payload(settings)

    assert is_ready is True
    assert payload["status"] == "ready"
    assert payload["orchestration"]["expected_queues"] == list(AUDIT_QUEUES)
    assert payload["checks"]["celery_workers"]["expected_queues"] == list(AUDIT_QUEUES)


def test_build_readiness_payload_skips_serp_when_provider_is_not_searxng(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        app_name="Site Audit API",
        app_env="test",
        celery_broker_url="redis://localhost:6379/0",
        celery_result_backend="redis://localhost:6379/0",
        serp_provider="mock",
        searxng_base_url=None,
    )
    monkeypatch.setattr(
        "app.health.check_database_health",
        lambda runtime_settings: ComponentHealth("ok", True, {"database_url": runtime_settings.database_url}),
    )
    monkeypatch.setattr(
        "app.health.check_redis_health",
        lambda runtime_settings: ComponentHealth("ok", True, {"broker_url": runtime_settings.celery_broker_url}),
    )
    monkeypatch.setattr(
        "app.health.check_celery_worker_health",
        lambda runtime_settings: ComponentHealth("ok", True, {"expected_queues": list(AUDIT_QUEUES)}),
    )

    payload, is_ready = build_readiness_payload(settings)

    assert is_ready is True
    assert payload["checks"]["serp"]["status"] == "skipped"
    assert payload["checks"]["serp"]["required"] is False
