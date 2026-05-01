from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.model_monitoring import build_model_monitoring_payload
from app.models import Audit


ACTIVE_MODEL_INFO = {
    "source": "local_dataset",
    "model_type": "CatBoostRegressor",
    "model_schema_version": "v3",
    "artifact_version": "dataset-v3-d37-20260501200434",
    "artifact_family": "page_quality_model",
    "dataset_version": "dataset-v3-d37",
    "feature_count": 148,
}
ACTIVE_MODEL_STATUS = {
    "model": {
        "source": "local_dataset",
        "model_type": "CatBoostRegressor",
        "model_schema_version": "v3",
        "artifact_version": "dataset-v3-d37-20260501200434",
        "artifact_family": "page_quality_model",
        "feature_count": 148,
    },
    "dataset": {"dataset_version": "dataset-v3-d37"},
}


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'model_monitoring.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _add_audit(
    db: Session,
    *,
    created_at: datetime,
    status: str = "completed",
    score: float | None = 70.0,
    model_info: dict[str, object] | None = ACTIVE_MODEL_INFO,
    comparison_summary: dict[str, object] | None = None,
    competitor_results: list[dict[str, object]] | None = None,
    warnings: list[str] | None = None,
    failure_context: dict[str, object] | None = None,
    error_message: str | None = None,
) -> None:
    db.add(
        Audit(
            id=str(uuid4()),
            query="golden query",
            target_url="https://example.com/",
            top_n=10,
            status=status,
            created_at=created_at.replace(tzinfo=None),
            updated_at=created_at.replace(tzinfo=None),
            score=score,
            score_breakdown={"model_info": model_info, "final_score": score} if model_info is not None else None,
            competitor_results=competitor_results,
            comparison_summary=comparison_summary,
            warnings=warnings,
            failure_context=failure_context,
            error_message=error_message,
        )
    )


def test_build_model_monitoring_payload_groups_recent_audits_by_runtime_model(db_session: Session):
    now = datetime(2026, 5, 2, 0, 0, tzinfo=UTC)
    _add_audit(
        db_session,
        created_at=now - timedelta(days=1),
        score=40.0,
        comparison_summary={"competitors_found": 2, "competitors_analyzed": 2, "competitors_failed": 0},
    )
    _add_audit(
        db_session,
        created_at=now - timedelta(days=2),
        status="completed_with_warnings",
        score=70.0,
        comparison_summary={"competitors_found": 3, "competitors_analyzed": 2, "competitors_failed": 1},
        warnings=["Один конкурент ограничил автоматический доступ."],
    )
    _add_audit(
        db_session,
        created_at=now - timedelta(days=3),
        score=90.0,
        comparison_summary={"competitors_found": 1, "competitors_analyzed": 1, "competitors_failed": 0},
    )
    _add_audit(
        db_session,
        created_at=now - timedelta(days=4),
        score=64.0,
        model_info={
            **ACTIVE_MODEL_INFO,
            "artifact_version": "previous-artifact",
            "model_schema_version": "v1",
            "dataset_version": "dataset-v1",
            "model_type": "RandomForestRegressor",
        },
        comparison_summary={"competitors_found": 2, "competitors_analyzed": 1, "competitors_failed": 1},
    )
    _add_audit(
        db_session,
        created_at=now - timedelta(days=5),
        score=55.0,
        model_info=None,
        comparison_summary={"competitors_found": 2, "competitors_analyzed": 2, "competitors_failed": 0},
    )
    _add_audit(
        db_session,
        created_at=now - timedelta(days=45),
        score=99.0,
        comparison_summary={"competitors_found": 1, "competitors_analyzed": 1, "competitors_failed": 0},
    )
    db_session.commit()

    payload = build_model_monitoring_payload(
        db_session,
        now=now,
        window_days=30,
        active_model_status=ACTIVE_MODEL_STATUS,
    )

    assert payload["status"] == "warning"
    assert payload["total_audits"] == 5
    assert payload["audits_with_model_info"] == 4
    assert payload["legacy_or_unknown_count"] == 1
    assert payload["status_counts"] == {"completed": 4, "completed_with_warnings": 1}
    assert payload["warning_count"] == 1
    assert payload["failure_count"] == 0
    assert payload["active_model"]["artifact_version"] == "dataset-v3-d37-20260501200434"

    active_usage = payload["model_usage"][0]
    assert active_usage["is_active_model"] is True
    assert active_usage["audit_count"] == 3
    assert active_usage["artifact_version"] == "dataset-v3-d37-20260501200434"
    assert active_usage["status_counts"] == {"completed": 2, "completed_with_warnings": 1}
    assert active_usage["warning_message_count"] == 1
    assert active_usage["score_distribution"] == {
        "sample_size": 3,
        "average": 66.6667,
        "min": 40.0,
        "max": 90.0,
        "p25": 55.0,
        "p50": 70.0,
        "p75": 80.0,
        "low_score_count": 1,
        "high_score_count": 1,
        "low_score_threshold": 50.0,
        "high_score_threshold": 80.0,
    }
    assert active_usage["competitor_coverage"] == {
        "sample_size": 3,
        "total_found": 6,
        "total_analyzed": 5,
        "total_failed": 1,
        "average_found": 2.0,
        "average_analyzed": 1.6667,
        "average_failed": 0.3333,
        "coverage_ratio": 0.8333,
    }
    assert payload["score_distribution"]["p50"] == 70.0
    assert payload["competitor_coverage"]["total_analyzed"] == 5
    assert payload["model_usage"][1]["artifact_version"] == "previous-artifact"


def test_model_monitoring_falls_back_to_competitor_results_when_summary_is_legacy(db_session: Session):
    now = datetime(2026, 5, 2, 0, 0, tzinfo=UTC)
    _add_audit(
        db_session,
        created_at=now - timedelta(days=1),
        score=72.0,
        comparison_summary=None,
        competitor_results=[
            {"url": "https://a.example", "score": 78.0, "features": {"word_count": 300}},
            {"url": "https://b.example", "score": None, "features": None},
        ],
    )
    db_session.commit()

    payload = build_model_monitoring_payload(
        db_session,
        now=now,
        active_model_status=ACTIVE_MODEL_STATUS,
    )

    assert payload["status"] == "ok"
    assert payload["competitor_coverage"]["total_found"] == 2
    assert payload["competitor_coverage"]["total_analyzed"] == 1
    assert payload["competitor_coverage"]["total_failed"] == 1


def test_model_monitoring_empty_state_is_explicit(db_session: Session):
    payload = build_model_monitoring_payload(
        db_session,
        now=datetime(2026, 5, 2, 0, 0, tzinfo=UTC),
        active_model_status=ACTIVE_MODEL_STATUS,
    )

    assert payload["status"] == "empty"
    assert payload["total_audits"] == 0
    assert payload["audits_with_model_info"] == 0
    assert payload["legacy_or_unknown_count"] == 0
    assert payload["score_distribution"]["sample_size"] == 0
    assert payload["model_usage"] == []
