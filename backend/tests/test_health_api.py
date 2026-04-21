from datetime import datetime

import pytest

from app.celery_app import AUDIT_QUEUES
from app.config import Settings
from app.db import Base
from app.health import (
    ComponentHealth,
    build_metrics_payload,
    build_readiness_payload,
    check_database_health,
    collect_broker_runtime_metrics,
    collect_database_runtime_metrics,
)
from app.models import Audit, AuditCompetitor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


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


def test_metrics_endpoint_returns_runtime_payload(client, monkeypatch: pytest.MonkeyPatch):
    payload = {
        "status": "ok",
        "app_name": "Site Audit API",
        "environment": "test",
        "checked_at": "2026-04-21T10:00:00+00:00",
        "orchestration": {"expected_queues": list(AUDIT_QUEUES)},
        "database": {"status": "ok", "audits": {"total": 2}, "competitors": {"total": 3}},
        "broker": {"status": "ok", "total_depth": 5},
        "workers": {"status": "ok", "online_count": 1},
    }
    monkeypatch.setattr("app.api.routes.health.build_metrics_payload", lambda: payload)

    response = client.get("/health/metrics")

    assert response.status_code == 200
    assert response.json() == payload


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


def test_build_readiness_payload_fails_when_celery_workers_do_not_cover_all_expected_queues(
    monkeypatch: pytest.MonkeyPatch,
):
    partial_queue_coverage = list(AUDIT_QUEUES[:-1])
    settings = Settings(
        app_name="Site Audit API",
        app_env="test",
        database_url="sqlite:///:memory:",
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
        lambda runtime_settings: ComponentHealth(
            "error",
            True,
            {
                "worker_count": 1,
                "workers": ["celery@test"],
                "worker_queues": {"celery@test": partial_queue_coverage},
                "expected_queues": list(AUDIT_QUEUES),
                "missing_queues": [AUDIT_QUEUES[-1]],
                "error": "Not all expected audit queues are served by active workers.",
            },
        ),
    )

    payload, is_ready = build_readiness_payload(settings)

    assert is_ready is False
    assert payload["status"] == "not_ready"
    assert payload["checks"]["celery_workers"]["status"] == "error"
    assert payload["checks"]["celery_workers"]["missing_queues"] == [AUDIT_QUEUES[-1]]


def test_build_readiness_payload_fails_when_searxng_is_required_but_not_configured(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        app_name="Site Audit API",
        app_env="test",
        database_url="sqlite:///:memory:",
        celery_broker_url="redis://localhost:6379/0",
        celery_result_backend="redis://localhost:6379/0",
        serp_provider="searxng",
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

    assert is_ready is False
    assert payload["status"] == "not_ready"
    assert payload["checks"]["serp"]["status"] == "error"
    assert payload["checks"]["serp"]["error"] == "SEARXNG_BASE_URL is not configured."


def test_check_database_health_uses_runtime_settings_database_url(tmp_path):
    database_path = tmp_path / "readiness-test.db"
    settings = Settings(database_url=f"sqlite:///{database_path}")

    health = check_database_health(settings)

    assert health.status == "ok"
    assert health.details["database_url"] == f"sqlite:///{database_path}"


def test_collect_database_runtime_metrics_aggregates_pipeline_state(tmp_path):
    db_path = tmp_path / "metrics.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        db.add_all(
            [
                Audit(
                    id="queued-audit",
                    query="q1",
                    target_url="https://example.com/1",
                    top_n=10,
                    status="queued",
                    created_at=datetime(2026, 4, 21, 10, 0, 0),
                    updated_at=datetime(2026, 4, 21, 10, 0, 0),
                    processing_version=1,
                ),
                Audit(
                    id="processing-audit",
                    query="q2",
                    target_url="https://example.com/2",
                    top_n=10,
                    status="processing",
                    created_at=datetime(2026, 4, 21, 9, 0, 0),
                    updated_at=datetime(2026, 4, 21, 9, 30, 0),
                    processing_version=2,
                    orchestration_stage="scoring",
                ),
                Audit(
                    id="completed-audit",
                    query="q3",
                    target_url="https://example.com/3",
                    top_n=10,
                    status="completed",
                    created_at=datetime(2026, 4, 21, 8, 0, 0),
                    updated_at=datetime(2026, 4, 21, 8, 5, 0),
                    processing_version=1,
                ),
            ]
        )
        db.add_all(
            [
                AuditCompetitor(
                    id="competitor-1",
                    audit_id="processing-audit",
                    url="https://competitor-1.test",
                    domain="competitor-1.test",
                    title="Competitor 1",
                    snippet="Snippet 1",
                    serp_rank=1,
                    serp_page=0,
                    status="pending",
                    created_at=datetime(2026, 4, 21, 9, 0, 0),
                    updated_at=datetime(2026, 4, 21, 9, 0, 0),
                ),
                AuditCompetitor(
                    id="competitor-2",
                    audit_id="processing-audit",
                    url="https://competitor-2.test",
                    domain="competitor-2.test",
                    title="Competitor 2",
                    snippet="Snippet 2",
                    serp_rank=2,
                    serp_page=0,
                    status="completed",
                    created_at=datetime(2026, 4, 21, 9, 1, 0),
                    updated_at=datetime(2026, 4, 21, 9, 2, 0),
                ),
            ]
        )
        db.commit()

    payload = collect_database_runtime_metrics(Settings(database_url=f"sqlite:///{db_path}"))

    assert payload["status"] == "ok"
    assert payload["audits"]["total"] == 3
    assert payload["audits"]["by_status"]["queued"] == 1
    assert payload["audits"]["by_status"]["processing"] == 1
    assert payload["audits"]["active_by_stage"]["scoring"] == 1
    assert payload["competitors"]["total"] == 2
    assert payload["competitors"]["by_status"]["pending"] == 1
    assert payload["competitors"]["by_status"]["completed"] == 1
    assert payload["audits"]["recent_terminal_duration_ms"]["sample_size"] == 1

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_collect_broker_runtime_metrics_returns_queue_depths(monkeypatch: pytest.MonkeyPatch):
    class FakeRedis:
        def __init__(self):
            self._depths = {queue_name: index + 1 for index, queue_name in enumerate(AUDIT_QUEUES)}

        def llen(self, queue_name: str) -> int:
            return self._depths[queue_name]

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.health.Redis.from_url", lambda *args, **kwargs: FakeRedis())

    payload = collect_broker_runtime_metrics(Settings(celery_broker_url="redis://localhost:6379/0"))

    assert payload["status"] == "ok"
    assert payload["queue_depths"][AUDIT_QUEUES[0]] == 1
    assert payload["queue_depths"][AUDIT_QUEUES[-1]] == len(AUDIT_QUEUES)
    assert payload["total_depth"] == sum(range(1, len(AUDIT_QUEUES) + 1))


def test_build_metrics_payload_reports_degraded_when_workers_are_missing(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        app_name="Site Audit API",
        app_env="test",
        database_url="sqlite:///:memory:",
        celery_broker_url="redis://localhost:6379/0",
        celery_result_backend="redis://localhost:6379/0",
    )
    monkeypatch.setattr(
        "app.health.collect_database_runtime_metrics",
        lambda runtime_settings: {"status": "ok", "database_url": runtime_settings.database_url, "audits": {}, "competitors": {}},
    )
    monkeypatch.setattr(
        "app.health.collect_broker_runtime_metrics",
        lambda runtime_settings: {"status": "ok", "broker_url": runtime_settings.celery_broker_url, "queue_depths": {}, "total_depth": 0},
    )
    monkeypatch.setattr(
        "app.health.collect_worker_runtime_metrics",
        lambda runtime_settings: {"status": "warning", "online_count": 0, "workers": {}, "warning": "No Celery workers responded to inspect."},
    )

    payload = build_metrics_payload(settings)

    assert payload["status"] == "degraded"
    assert payload["workers"]["status"] == "warning"
