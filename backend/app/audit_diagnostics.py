from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.schemas.audit import (
    AuditEarlyStopRead,
    AuditTimelineCriticalPathStageRead,
    AuditTimelineDiagnosticsRead,
    AuditTimelineFanOutRead,
    AuditTimelineStageDiagnosticsRead,
)


LOGICAL_STAGE_ORDER = {
    "pipeline": 0,
    "fetch": 1,
    "heavy_analysis": 2,
    "features": 3,
    "scoring": 4,
    "competitors": 5,
    "competitor_page": 6,
    "competitor_analysis": 7,
    "competitor_aggregation": 8,
    "recommendations": 9,
    "finalize": 10,
}

TASK_STAGE_MAP = {
    "app.process_audit": "pipeline",
    "app.process_audit_fetch_target": "fetch",
    "app.process_audit_run_heavy_analysis": "heavy_analysis",
    "app.process_audit_extract_features": "features",
    "app.process_audit_score_target": "scoring",
    "app.process_audit_collect_competitors": "competitors",
    "app.process_audit_collect_competitor_page": "competitor_page",
    "app.process_audit_analyze_competitor_page": "competitor_analysis",
    "app.process_audit_aggregate_competitors": "competitor_aggregation",
    "app.process_audit_generate_recommendations": "recommendations",
    "app.process_audit_finalize": "finalize",
}

TERMINAL_EVENTS = {"completed", "failed", "aborted"}
FAN_OUT_STAGES = {"competitor_page", "competitor_analysis"}


def resolve_audit_events_processing_version(
    db: Session,
    audit_id: str,
    processing_version: int | None,
) -> int | None:
    if processing_version is not None:
        return processing_version
    latest_processing_version = db.scalar(
        select(AuditEvent.processing_version)
        .where(AuditEvent.audit_id == audit_id, AuditEvent.processing_version.is_not(None))
        .order_by(AuditEvent.processing_version.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    if latest_processing_version is None:
        return None
    return int(latest_processing_version)


def load_audit_events(
    db: Session,
    audit_id: str,
    processing_version: int | None,
) -> tuple[int | None, list[AuditEvent]]:
    effective_processing_version = resolve_audit_events_processing_version(db, audit_id, processing_version)
    statement = select(AuditEvent).where(AuditEvent.audit_id == audit_id).order_by(AuditEvent.id.asc())
    if effective_processing_version is not None:
        statement = statement.where(AuditEvent.processing_version == effective_processing_version)
    return effective_processing_version, db.scalars(statement).all()


def _normalize_stage(stage: str) -> str:
    return TASK_STAGE_MAP.get(stage, stage)


def _round_ms(started_at: datetime, finished_at: datetime) -> float:
    return round((finished_at - started_at).total_seconds() * 1000.0, 2)


def _safe_duration_values(events: Iterable[AuditEvent]) -> list[float]:
    return [round(float(event.duration_ms), 2) for event in events if isinstance(event.duration_ms, (int, float))]


def _build_stage_diagnostics(stage: str, events: list[AuditEvent]) -> AuditTimelineStageDiagnosticsRead:
    durations = _safe_duration_values(event for event in events if event.event in TERMINAL_EVENTS)
    dispatch_count = sum(1 for event in events if event.event == "dispatched")
    started_count = sum(1 for event in events if event.event == "started")
    completed_count = sum(1 for event in events if event.event == "completed")
    failed_count = sum(1 for event in events if event.event == "failed")
    aborted_count = sum(1 for event in events if event.event == "aborted")
    total_duration_ms = round(sum(durations), 2) if durations else None
    average_duration_ms = round(sum(durations) / len(durations), 2) if durations else None
    max_duration_ms = max(durations) if durations else None
    critical_path_mode = "fan_out_max" if stage in FAN_OUT_STAGES else "serial_sum"
    critical_path_duration_ms = None
    if durations:
        critical_path_duration_ms = max_duration_ms if stage in FAN_OUT_STAGES else total_duration_ms

    latest_event = events[-1] if events else None
    return AuditTimelineStageDiagnosticsRead(
        stage=stage,
        dispatch_count=dispatch_count,
        started_count=started_count,
        completed_count=completed_count,
        failed_count=failed_count,
        aborted_count=aborted_count,
        terminal_count=completed_count + failed_count + aborted_count,
        total_duration_ms=total_duration_ms,
        average_duration_ms=average_duration_ms,
        max_duration_ms=max_duration_ms,
        critical_path_mode=critical_path_mode,
        critical_path_duration_ms=critical_path_duration_ms,
        first_event_at=events[0].created_at if events else None,
        last_event_at=latest_event.created_at if latest_event is not None else None,
        latest_event=latest_event.event if latest_event is not None else None,
    )


def _derive_run_status(fallback_status: str, last_event: AuditEvent) -> str:
    if last_event.stage == "pipeline" and last_event.event == "completed":
        details = last_event.details if isinstance(last_event.details, dict) else None
        final_status = details.get("final_status") if isinstance(details, dict) else None
        return str(final_status or fallback_status)
    if last_event.stage == "pipeline" and last_event.event in {"failed", "aborted"}:
        return "failed"
    return fallback_status


def build_audit_timeline_diagnostics(
    *,
    audit_id: str,
    audit_status: str,
    processing_version: int | None,
    events: list[AuditEvent],
    early_stop: AuditEarlyStopRead | None = None,
) -> AuditTimelineDiagnosticsRead:
    if not events:
        return AuditTimelineDiagnosticsRead(
            audit_id=audit_id,
            processing_version=processing_version,
            status=audit_status,
            event_count=0,
            dispatch_count=0,
            started_at=None,
            finished_at=None,
            total_duration_ms=None,
            terminal_stage=None,
            terminal_event=None,
            critical_path_duration_ms=None,
            critical_path_stages=[],
            stage_breakdown=[],
            fan_out=None,
            early_stop=early_stop,
        )

    stage_groups: dict[str, list[AuditEvent]] = {}
    for event in events:
        logical_stage = _normalize_stage(event.stage)
        stage_groups.setdefault(logical_stage, []).append(event)

    ordered_stage_names = sorted(
        stage_groups,
        key=lambda stage: (LOGICAL_STAGE_ORDER.get(stage, 999), stage),
    )
    stage_breakdown = [_build_stage_diagnostics(stage, stage_groups[stage]) for stage in ordered_stage_names]
    critical_path_stages = [
        AuditTimelineCriticalPathStageRead(
            stage=stage.stage,
            contribution_duration_ms=stage.critical_path_duration_ms,
            mode=stage.critical_path_mode,
            terminal_count=stage.terminal_count,
        )
        for stage in stage_breakdown
        if stage.critical_path_duration_ms is not None
    ]
    fan_out_stage = next((stage for stage in stage_breakdown if stage.stage in FAN_OUT_STAGES), None)
    fan_out = None
    if fan_out_stage is not None:
        fan_out = AuditTimelineFanOutRead(
            stage=fan_out_stage.stage,
            dispatch_count=fan_out_stage.dispatch_count,
            started_count=fan_out_stage.started_count,
            terminal_count=fan_out_stage.terminal_count,
            in_flight_count=max(fan_out_stage.started_count - fan_out_stage.terminal_count, 0),
            total_duration_ms=fan_out_stage.total_duration_ms,
            average_duration_ms=fan_out_stage.average_duration_ms,
            max_duration_ms=fan_out_stage.max_duration_ms,
            critical_path_duration_ms=fan_out_stage.critical_path_duration_ms,
        )

    first_event = events[0]
    last_event = events[-1]
    total_duration_ms = _round_ms(first_event.created_at, last_event.created_at) if len(events) > 1 else 0.0
    critical_path_duration_ms = round(
        sum(stage.contribution_duration_ms for stage in critical_path_stages if stage.contribution_duration_ms is not None),
        2,
    )

    return AuditTimelineDiagnosticsRead(
        audit_id=audit_id,
        processing_version=processing_version,
        status=_derive_run_status(audit_status, last_event),
        event_count=len(events),
        dispatch_count=sum(1 for event in events if event.event == "dispatched"),
        started_at=first_event.created_at,
        finished_at=last_event.created_at,
        total_duration_ms=total_duration_ms,
        terminal_stage=_normalize_stage(last_event.stage),
        terminal_event=last_event.event,
        critical_path_duration_ms=critical_path_duration_ms if critical_path_stages else None,
        critical_path_stages=critical_path_stages,
        stage_breakdown=stage_breakdown,
        fan_out=fan_out,
        early_stop=early_stop,
    )
