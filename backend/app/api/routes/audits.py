from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models import Audit, AuditEvent
from app.schemas.audit import (
    AuditCreate,
    AuditEventRead,
    AuditEventTimelineRead,
    AuditRead,
    AuditRecommendationsRead,
    AuditResultsRead,
)
from app.tasks import enqueue_audit_processing

router = APIRouter(tags=["audits"])


def _get_audit_or_404(db: Session, audit_id: str) -> Audit:
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аудит не найден")
    return audit


@router.get("/audits", response_model=list[AuditRead])
def list_audits_endpoint(db: Session = Depends(get_db_session)) -> list[AuditRead]:
    audits = db.scalars(select(Audit).order_by(Audit.created_at.desc())).all()
    return [AuditRead.model_validate(audit) for audit in audits]


@router.post("/audits", response_model=AuditRead, status_code=status.HTTP_201_CREATED)
def create_audit_endpoint(
    payload: AuditCreate,
    db: Session = Depends(get_db_session),
) -> AuditRead:
    audit = Audit(
        id=str(uuid4()),
        query=payload.query,
        target_url=str(payload.target_url),
        top_n=payload.top_n,
        status="queued",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    enqueue_audit_processing(audit.id)
    return AuditRead.model_validate(audit)


@router.get("/audits/{audit_id}", response_model=AuditRead)
def get_audit_endpoint(
    audit_id: str,
    db: Session = Depends(get_db_session),
) -> AuditRead:
    audit = _get_audit_or_404(db, audit_id)
    return AuditRead.model_validate(audit)


@router.get("/audits/{audit_id}/results", response_model=AuditResultsRead)
def get_audit_results_endpoint(
    audit_id: str,
    db: Session = Depends(get_db_session),
) -> AuditResultsRead:
    audit = _get_audit_or_404(db, audit_id)
    return AuditResultsRead(
        audit_id=audit.id,
        status=audit.status,
        score=audit.score,
        score_breakdown=audit.score_breakdown,
        extracted_text=audit.extracted_text,
        features=audit.features,
        competitor_results=audit.competitor_results,
        comparison_summary=audit.comparison_summary,
        target_fetch_status=audit.target_fetch_status,
        target_fetch_method=audit.target_fetch_method,
        target_fetch_error_code=audit.target_fetch_error_code,
        target_fetch_error_message=audit.target_fetch_error_message,
        failure_context=audit.failure_context,
        warnings=audit.warnings,
        error_message=audit.error_message,
    )


@router.get("/audits/{audit_id}/recommendations", response_model=AuditRecommendationsRead)
def get_audit_recommendations_endpoint(
    audit_id: str,
    db: Session = Depends(get_db_session),
) -> AuditRecommendationsRead:
    audit = _get_audit_or_404(db, audit_id)
    return AuditRecommendationsRead(
        audit_id=audit.id,
        status=audit.status,
        recommendations=audit.recommendations or [],
        failure_context=audit.failure_context,
        error_message=audit.error_message,
    )


@router.get("/audits/{audit_id}/events", response_model=AuditEventTimelineRead)
def get_audit_events_endpoint(
    audit_id: str,
    processing_version: int | None = None,
    db: Session = Depends(get_db_session),
) -> AuditEventTimelineRead:
    audit = _get_audit_or_404(db, audit_id)
    statement = (
        select(AuditEvent)
        .where(AuditEvent.audit_id == audit_id)
        .order_by(AuditEvent.id.asc())
    )
    effective_processing_version = processing_version
    if effective_processing_version is not None:
        statement = statement.where(AuditEvent.processing_version == effective_processing_version)
    else:
        latest_processing_version = db.scalar(
            select(AuditEvent.processing_version)
            .where(AuditEvent.audit_id == audit_id, AuditEvent.processing_version.is_not(None))
            .order_by(AuditEvent.processing_version.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        if latest_processing_version is not None:
            effective_processing_version = int(latest_processing_version)
            statement = statement.where(AuditEvent.processing_version == effective_processing_version)

    events = db.scalars(statement).all()
    return AuditEventTimelineRead(
        audit_id=audit.id,
        processing_version=effective_processing_version,
        events=[AuditEventRead.model_validate(event) for event in events],
    )
