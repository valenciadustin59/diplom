from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from threading import Thread
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from celery.utils.log import get_task_logger
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select, update

from app.audit_status import COMPLETED, COMPLETED_WITH_WARNINGS, FAILED, PROCESSING, transition_status
from app.celery_app import celery_app, resolve_task_queue
from app.competitors import (
    MIN_COMPETITORS_FOR_COMPARISON,
    analyze_competitor_snapshot,
    build_comparison_summary,
    build_failed_competitor_result,
    fetch_competitor_page,
    search_competitor_pages,
)
from app.config import get_settings
from app.db import SessionLocal
from app.features import (
    build_features,
    detect_query_intent,
    merge_intent_alignment_features,
    merge_serp_relative_features,
    merge_snapshot_auxiliary_features,
)
from app.heavy_analysis import build_heavy_analysis_payload, merge_heavy_analysis_features
from app.ml import explain_score
from app.models import Audit, AuditCompetitor, AuditEvent
from app.parser import (
    ensure_extraction_artifact,
    extraction_artifact_html,
    extraction_artifact_text,
    fetch_page,
)
from app.recommendations import generate_recommendations, get_recommendation_count
from app.runtime_capacity import evaluate_queue_dispatch


logger = get_task_logger(__name__)
settings = get_settings()


FETCH_STAGE = "fetch"
HEAVY_ANALYSIS_STAGE = "heavy_analysis"
FEATURES_STAGE = "features"
SCORING_STAGE = "scoring"
COMPETITORS_STAGE = "competitors"
RECOMMENDATIONS_STAGE = "recommendations"
FINALIZE_STAGE = "finalize"
PIPELINE_STAGE = "pipeline"
COMPETITOR_PAGE_STAGE = "competitor_page"
COMPETITOR_ANALYSIS_STAGE = "competitor_analysis"
COMPETITOR_AGGREGATION_STAGE = "competitor_aggregation"

COMPETITOR_PENDING = "pending"
COMPETITOR_PROCESSING = "processing"
COMPETITOR_ANALYSIS_PENDING = "analysis_pending"
COMPETITOR_ANALYZING = "analyzing"
COMPETITOR_COMPLETED = "completed"
COMPETITOR_FAILED = "failed"

COMPETITOR_PROCESSING_COLLECTING = "collecting"
COMPETITOR_PROCESSING_AGGREGATING = "aggregating"
COMPETITOR_PROCESSING_AGGREGATED = "aggregated"


def _resolve_stage_task(stage: str):
    if stage == FETCH_STAGE:
        return process_audit_fetch_target
    if stage == HEAVY_ANALYSIS_STAGE:
        return process_audit_run_heavy_analysis
    if stage == FEATURES_STAGE:
        return process_audit_extract_features
    if stage == SCORING_STAGE:
        return process_audit_score_target
    if stage == COMPETITORS_STAGE:
        return process_audit_collect_competitors
    if stage == RECOMMENDATIONS_STAGE:
        return process_audit_generate_recommendations
    if stage == FINALIZE_STAGE:
        return process_audit_finalize
    return None


def _derive_failure_code(error: BaseException) -> str:
    exception_name = error.__class__.__name__.strip()
    if not exception_name:
        return "unknown_error"

    rendered: list[str] = []
    for character in exception_name:
        if character.isupper() and rendered:
            rendered.append("_")
        rendered.append(character.lower())
    return "".join(rendered)


def _map_step_to_failure_stage(step: str) -> str:
    if step == COMPETITORS_STAGE:
        return "search"
    if step in {FETCH_STAGE, HEAVY_ANALYSIS_STAGE, FEATURES_STAGE, SCORING_STAGE, RECOMMENDATIONS_STAGE}:
        return step
    return PIPELINE_STAGE


def _build_failure_context(
    *,
    stage: str,
    message: str,
    code: str | None = None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "stage": stage,
        "code": code,
        "message": message,
        "details": details or None,
    }


class AuditStepExecutionError(RuntimeError):
    def __init__(self, step: str, original_error: Exception):
        super().__init__(str(original_error))
        self.step = step
        self.original_error = original_error

    def to_failure_context(self) -> dict[str, object]:
        return _build_failure_context(
            stage=_map_step_to_failure_stage(self.step),
            code=_derive_failure_code(self.original_error),
            message=str(self.original_error),
        )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _redis_available() -> bool:
    try:
        client = Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
        try:
            return bool(client.ping())
        finally:
            client.close()
    except RedisError:
        return False


def _round_duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000.0, 2)


def _serialize_log_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalize_event_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_event_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_event_value(item) for item in value]
    return str(value)


def _build_audit_event_payload(
    audit_id: str,
    step: str,
    event: str,
    *,
    processing_version: int | None = None,
    duration_ms: float | None = None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "audit_id": audit_id,
        "processing_version": processing_version,
        "stage": step,
        "event": event,
        "duration_ms": duration_ms,
        "details": _normalize_event_value(details) if details else None,
        "created_at": _utc_now(),
    }


def _flush_audit_events(db, event_buffer: list[dict[str, object]]) -> None:
    for event_payload in event_buffer:
        db.add(AuditEvent(**event_payload))
    event_buffer.clear()


def _persist_audit_event(
    audit_id: str,
    step: str,
    event: str,
    *,
    processing_version: int | None = None,
    duration_ms: float | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditEvent(
                **_build_audit_event_payload(
                    audit_id,
                    step,
                    event,
                    processing_version=processing_version,
                    duration_ms=duration_ms,
                    details=details,
                )
            )
        )
        db.commit()
    except Exception:
        logger.exception(
            "Failed to persist audit event audit_id=%s step=%s event=%s processing_version=%s",
            audit_id,
            step,
            event,
            processing_version,
        )
        db.rollback()
    finally:
        db.close()


def _format_log_fields(fields: dict[str, object]) -> str:
    rendered_parts: list[str] = []
    for key, value in sorted(fields.items()):
        if value is None:
            continue
        rendered_value = _serialize_log_value(value).replace("\n", "\\n")
        rendered_parts.append(f"{key}={rendered_value}")
    return " ".join(rendered_parts)


def _log_audit_step(
    level: int,
    audit_id: str,
    step: str,
    event: str,
    *,
    processing_version: int | None = None,
    event_buffer: list[dict[str, object]] | None = None,
    **fields: object,
) -> None:
    message = f"audit_step audit_id={audit_id} step={step} event={event}"
    formatted_fields = _format_log_fields(fields)
    if formatted_fields:
        message = f"{message} {formatted_fields}"
    logger.log(level, message)
    event_payload = _build_audit_event_payload(
        audit_id,
        step,
        event,
        processing_version=processing_version,
        duration_ms=float(fields["duration_ms"]) if isinstance(fields.get("duration_ms"), (int, float)) else None,
        details=fields or None,
    )
    if event_buffer is not None:
        event_buffer.append(event_payload)
        return
    _persist_audit_event(
        audit_id,
        step,
        event,
        processing_version=processing_version,
        duration_ms=event_payload["duration_ms"] if isinstance(event_payload.get("duration_ms"), float) else None,
        details=fields or None,
    )


def _run_logged_step(
    audit_id: str,
    step: str,
    action: Callable[[], Any],
    *,
    processing_version: int | None,
    event_buffer: list[dict[str, object]],
    summarize_result: Callable[[Any], dict[str, object]],
) -> Any:
    _log_audit_step(
        logging.INFO,
        audit_id,
        step,
        "started",
        processing_version=processing_version,
        event_buffer=event_buffer,
    )
    started_at = perf_counter()
    try:
        result = action()
    except Exception as exc:
        duration_ms = _round_duration_ms(started_at)
        logger.exception(
            "audit_step audit_id=%s step=%s event=failed duration_ms=%.2f error=%s",
            audit_id,
            step,
            duration_ms,
            exc,
        )
        _log_audit_step(
            logging.ERROR,
            audit_id,
            step,
            "failed",
            processing_version=processing_version,
            event_buffer=event_buffer,
            duration_ms=duration_ms,
            error=str(exc),
        )
        raise AuditStepExecutionError(step, exc) from exc
    summary = summarize_result(result)
    _log_audit_step(
        logging.INFO,
        audit_id,
        step,
        "completed",
        processing_version=processing_version,
        event_buffer=event_buffer,
        duration_ms=_round_duration_ms(started_at),
        **summary,
    )
    return result


def _summarize_fetch_result(result: dict[str, object]) -> dict[str, object]:
    return {
        "status": result.get("status"),
        "fetch_method": result.get("fetch_method"),
        "error_code": result.get("fetch_error_code"),
        "http_status": result.get("http_status"),
        "text_length": len(str(result.get("text") or "")),
    }


def _summarize_heavy_analysis(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "overall_score": summary.get("overall_score"),
        "risk_level": summary.get("risk_level"),
        "feature_count": summary.get("feature_count"),
    }


def _summarize_features(features: dict[str, float | int]) -> dict[str, object]:
    return {
        "feature_count": len(features),
        "text_length_chars": features.get("text_length_chars"),
        "semantic_similarity": features.get("semantic_similarity"),
        "intent_alignment_score": features.get("intent_alignment_score"),
    }


def _summarize_score(score_breakdown: dict[str, object]) -> dict[str, object]:
    model_info = score_breakdown.get("model_info")
    model_source = model_info.get("source") if isinstance(model_info, dict) else None
    return {
        "final_score": score_breakdown.get("final_score"),
        "rule_score": score_breakdown.get("rule_score"),
        "ml_score": score_breakdown.get("ml_score"),
        "model_source": model_source,
    }


def _summarize_competitors(competitor_results: list[dict[str, object]]) -> dict[str, object]:
    analyzed = sum(
        1
        for item in competitor_results
        if isinstance(item.get("features"), dict) and isinstance(item.get("score"), (int, float))
    )
    total = len(competitor_results)
    return {
        "competitors_found": total,
        "competitors_analyzed": analyzed,
        "competitors_failed": total - analyzed,
    }


def _summarize_recommendations(recommendations: object) -> dict[str, object]:
    return {"recommendations_count": get_recommendation_count(recommendations)}


def _summarize_finalize_result(result: dict[str, object]) -> dict[str, object]:
    recommendations = result.get("recommendations") if isinstance(result, dict) else None
    warnings = result.get("warnings") if isinstance(result, dict) else None
    comparison_summary = result.get("comparison_summary") if isinstance(result, dict) else None
    score = result.get("score") if isinstance(result, dict) else None
    return {
        "score": score,
        "competitors_found": comparison_summary.get("competitors_found") if isinstance(comparison_summary, dict) else None,
        "competitors_failed": comparison_summary.get("competitors_failed") if isinstance(comparison_summary, dict) else None,
        "recommendations_count": get_recommendation_count(recommendations),
        "warnings_count": len(warnings) if isinstance(warnings, list) else None,
    }


def _summarize_competitor_pages(pages: list[dict[str, object]]) -> dict[str, object]:
    return {"competitors_found": len(pages), "competitor_tasks_planned": len(pages)}


def _summarize_competitor_fetch(payload: dict[str, object]) -> dict[str, object]:
    return {
        "competitor_id": payload.get("competitor_id"),
        "domain": payload.get("domain"),
        "fetch_status": payload.get("fetch_status"),
        "fetch_method": payload.get("fetch_method"),
        "error_code": payload.get("fetch_error_code"),
    }


def _summarize_competitor_analysis(payload: dict[str, object]) -> dict[str, object]:
    features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
    return {
        "competitor_id": payload.get("competitor_id"),
        "domain": payload.get("domain"),
        "score": payload.get("score"),
        "feature_count": len(features),
    }


def _serialize_audit_competitor(competitor: AuditCompetitor) -> dict[str, object]:
    return {
        "url": competitor.url,
        "domain": competitor.domain,
        "title": competitor.title,
        "snippet": competitor.snippet,
        "serp_rank": competitor.serp_rank,
        "serp_page": competitor.serp_page,
        "fetch_status": competitor.fetch_status,
        "fetch_method": competitor.fetch_method,
        "fetch_error_code": competitor.fetch_error_code,
        "fetch_error_message": competitor.fetch_error_message,
        "score": competitor.score,
        "features": competitor.features,
    }


def _serialize_competitor_search_result(competitor: AuditCompetitor) -> dict[str, object]:
    return {
        "url": competitor.url,
        "domain": competitor.domain,
        "title": competitor.title,
        "snippet": competitor.snippet,
        "rank": competitor.serp_rank,
        "serp_rank": competitor.serp_rank,
        "serp_page": competitor.serp_page,
        "fetch_status": competitor.fetch_status,
        "fetch_method": competitor.fetch_method,
        "fetch_error_code": competitor.fetch_error_code,
        "fetch_error_message": competitor.fetch_error_message,
    }


def _build_competitor_aggregation_result(
    *,
    user_features: dict[str, float | int],
    user_score: float,
    competitors: list[AuditCompetitor],
    query_intent: dict[str, object] | None,
    requested_top_n: int | None,
) -> dict[str, object]:
    competitor_results = [_serialize_audit_competitor(item) for item in competitors]
    competitor_features = [
        item["features"]
        for item in competitor_results
        if isinstance(item.get("features"), dict)
    ]
    enriched_user_features, serp_relative_summary = merge_serp_relative_features(user_features, competitor_features)
    return {
        "competitor_results": competitor_results,
        "user_features": enriched_user_features,
        "comparison_summary": build_comparison_summary(
            user_features=enriched_user_features,
            user_score=user_score,
            competitor_results=competitor_results,
            query_intent=query_intent,
            serp_relative_summary=serp_relative_summary,
            requested_top_n=requested_top_n,
        ),
    }


def _extract_competitiveness_score(comparison_summary: dict[str, object]) -> float | None:
    score = comparison_summary.get("competitiveness_score")
    if not isinstance(score, (int, float)):
        return None
    return max(0.0, min(100.0, float(score)))


def _upsert_audit_competitor_result(competitor: AuditCompetitor, result: dict[str, object], *, status: str) -> None:
    competitor.title = str(result.get("title") or "")
    competitor.snippet = str(result.get("snippet") or "")
    competitor.serp_rank = int(result.get("serp_rank") or competitor.serp_rank or 0)
    competitor.serp_page = int(result.get("serp_page") or competitor.serp_page or 0)
    competitor.fetch_status = str(result.get("fetch_status") or "") or None
    competitor.fetch_method = str(result.get("fetch_method") or "") or None
    competitor.fetch_error_code = str(result.get("fetch_error_code") or "") or None
    competitor.fetch_error_message = str(result.get("fetch_error_message") or "") or None
    competitor.snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else competitor.snapshot
    competitor.score = float(result["score"]) if isinstance(result.get("score"), (int, float)) else None
    competitor.features = result.get("features") if isinstance(result.get("features"), dict) else None
    competitor.status = status
    competitor.updated_at = _utc_now()


def _load_audit_competitor(db, competitor_id: str, audit_id: str) -> AuditCompetitor | None:
    competitor = db.get(AuditCompetitor, competitor_id)
    if competitor is None or competitor.audit_id != audit_id:
        logger.warning("Audit competitor not found for audit %s: %s", audit_id, competitor_id)
        _log_audit_step(
            logging.WARNING,
            audit_id,
            COMPETITOR_PAGE_STAGE,
            "aborted",
            reason="competitor_not_found",
            competitor_id=competitor_id,
        )
        return None
    return competitor


def _claim_audit_competitor_processing(db, audit_id: str, competitor_id: str) -> bool:
    claim_result = db.execute(
        update(AuditCompetitor)
        .where(
            AuditCompetitor.id == competitor_id,
            AuditCompetitor.audit_id == audit_id,
            AuditCompetitor.status == COMPETITOR_PENDING,
        )
        .values(
            status=COMPETITOR_PROCESSING,
            updated_at=_utc_now(),
        )
    )
    return bool(claim_result.rowcount)


def _claim_audit_competitor_analysis(db, audit_id: str, competitor_id: str) -> bool:
    claim_result = db.execute(
        update(AuditCompetitor)
        .where(
            AuditCompetitor.id == competitor_id,
            AuditCompetitor.audit_id == audit_id,
            AuditCompetitor.status == COMPETITOR_ANALYSIS_PENDING,
        )
        .values(
            status=COMPETITOR_ANALYZING,
            updated_at=_utc_now(),
        )
    )
    return bool(claim_result.rowcount)


def _enqueue_task(task, *args: object) -> dict[str, object]:
    audit_id = str(args[0]) if args else ""
    queue_name = resolve_task_queue(task.name)
    processing_version = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else None
    task.apply_async(args=args, queue=queue_name)
    _log_audit_step(
        logging.INFO,
        audit_id,
        task.name,
        "dispatched",
        processing_version=processing_version,
        queue=queue_name,
    )
    return {
        "audit_id": audit_id,
        "status": PROCESSING,
        "next_stage": task.name,
        "next_queue": queue_name,
        "dispatch_mode": "queued",
    }


def _build_stage_skip_response(
    audit_id: str,
    stage: str,
    processing_version: int,
    reason: str,
    *,
    current_version: int | None = None,
    current_stage: str | None = None,
) -> dict[str, object]:
    _log_audit_step(
        logging.INFO,
        audit_id,
        stage,
        "aborted",
        processing_version=processing_version,
        reason=reason,
        current_version=current_version,
        current_stage=current_stage,
    )
    return {
        "audit_id": audit_id,
        "status": "ignored",
        "reason": reason,
        "processing_version": processing_version,
        "current_version": current_version,
        "current_stage": current_stage,
    }


def _validate_stage_execution(
    audit_id: str,
    audit: Audit,
    log_stage: str,
    processing_version: int,
    *,
    expected_stage: str,
) -> dict[str, object] | None:
    if audit.processing_version != processing_version:
        return _build_stage_skip_response(
            audit_id,
            log_stage,
            processing_version,
            "stale_processing_version",
            current_version=audit.processing_version,
            current_stage=audit.orchestration_stage,
        )
    if audit.orchestration_stage != expected_stage:
        return _build_stage_skip_response(
            audit_id,
            log_stage,
            processing_version,
            "stage_already_advanced",
            current_version=audit.processing_version,
            current_stage=audit.orchestration_stage,
        )
    return None


def _set_next_orchestration_stage(audit: Audit, next_stage: str | None) -> None:
    audit.orchestration_stage = next_stage
    audit.updated_at = _utc_now()


def _start_inline_audit_processing(audit_id: str) -> None:
    logger.warning("Celery is unavailable, running distributed audit pipeline inline in background thread: %s", audit_id)
    _log_audit_step(
        logging.WARNING,
        audit_id,
        PIPELINE_STAGE,
        "inline_fallback",
        reason="celery_unavailable",
    )
    Thread(target=process_audit.run, args=(audit_id,), daemon=True).start()


def _clear_analysis_outputs(audit: Audit) -> None:
    audit.extracted_text = None
    audit.target_html = None
    audit.heavy_analysis = None
    audit.orchestration_stage = None
    audit.competitor_processing_status = None
    audit.features = None
    audit.score = None
    audit.score_breakdown = None
    audit.competitor_results = None
    audit.comparison_summary = None
    audit.recommendations = None


def _clear_fetch_outputs(audit: Audit) -> None:
    audit.target_fetch_status = None
    audit.target_fetch_method = None
    audit.target_fetch_error_code = None
    audit.target_fetch_error_message = None
    audit.target_snapshot = None
    audit.feature_schema_version = None


def _mark_audit_processing(audit: Audit) -> None:
    audit.status = transition_status(audit.status, PROCESSING)
    audit.updated_at = _utc_now()
    audit.error_message = None
    audit.failure_context = None
    audit.warnings = []
    _clear_analysis_outputs(audit)
    _clear_fetch_outputs(audit)


def _mark_audit_failed(audit: Audit, failure_context: dict[str, object]) -> None:
    try:
        audit.status = transition_status(audit.status, FAILED)
    except ValueError:
        audit.status = FAILED
    audit.error_message = str(failure_context.get("message") or "Audit processing failed")
    audit.failure_context = failure_context
    audit.warnings = []
    _clear_analysis_outputs(audit)
    audit.updated_at = _utc_now()


def _mark_audit_completed(
    audit: Audit,
    *,
    recommendations: dict[str, object] | list[dict[str, object]],
    warnings: list[str],
) -> str:
    final_status = COMPLETED_WITH_WARNINGS if warnings else COMPLETED
    audit.status = transition_status(audit.status, final_status)
    audit.recommendations = recommendations
    audit.warnings = warnings
    audit.error_message = None
    audit.failure_context = None
    audit.orchestration_stage = None
    audit.updated_at = _utc_now()
    return final_status


def _load_audit(db, audit_id: str, stage: str) -> Audit | None:
    audit = db.get(Audit, audit_id)
    if audit is None:
        logger.warning("Audit not found for stage %s: %s", stage, audit_id)
        _log_audit_step(logging.WARNING, audit_id, stage, "aborted", reason="audit_not_found")
    return audit


def _dispatch_stage_task(task, *args: object, preserve_queue_affinity: bool = False) -> Any:
    audit_id = str(args[0]) if args else ""
    queue_name = resolve_task_queue(task.name)
    processing_version = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else None
    dispatch_decision = evaluate_queue_dispatch(queue_name)
    if dispatch_decision.action == "inline":
        if preserve_queue_affinity and _redis_available():
            _log_audit_step(
                logging.WARNING,
                audit_id,
                task.name,
                "queue_affinity_preserved",
                processing_version=processing_version,
                queue=queue_name,
                reason=dispatch_decision.reason,
                guard_message=dispatch_decision.message,
                guard_details=dispatch_decision.details or None,
            )
            try:
                return _enqueue_task(task, *args)
            except Exception:
                logger.exception(
                    "Failed to enqueue queue-affinity-preserved task %s on queue %s for %s, falling back to inline execution",
                    task.name,
                    queue_name,
                    audit_id,
                )
        _log_audit_step(
            logging.WARNING,
            audit_id,
            task.name,
            "inline_fallback",
            processing_version=processing_version,
            queue=queue_name,
            reason=dispatch_decision.reason,
            guard_message=dispatch_decision.message,
            guard_details=dispatch_decision.details or None,
        )
        return task.run(*args)
    if _redis_available():
        try:
            return _enqueue_task(task, *args)
        except Exception:
            logger.exception(
                "Failed to enqueue stage task %s on queue %s for %s, falling back to inline execution",
                task.name,
                queue_name,
                audit_id,
            )
    _log_audit_step(
        logging.INFO,
        audit_id,
        task.name,
        "dispatched",
        processing_version=processing_version,
        queue=queue_name,
        dispatch_mode="inline",
    )
    return task.run(*args)


def _build_completion_warnings(comparison_summary: dict[str, float | int] | None) -> list[str]:
    if not isinstance(comparison_summary, dict):
        return []

    warnings: list[str] = []
    competitors_found = int(comparison_summary.get("competitors_found") or 0)
    competitors_analyzed = int(comparison_summary.get("competitors_analyzed") or 0)
    competitors_failed = int(comparison_summary.get("competitors_failed") or 0)
    if competitors_found and competitors_failed:
        warnings.append(
            f"Обработано {competitors_analyzed} из {competitors_found} конкурентных страниц, "
            f"{competitors_failed} страниц ограничили автоматический доступ."
        )
    if competitors_analyzed < MIN_COMPETITORS_FOR_COMPARISON:
        warnings.append(
            "Для корректного competitor-aware сравнения обработано недостаточно конкурентных страниц."
        )
    return warnings


def _handle_stage_failure(
    audit_id: str,
    exc: Exception,
    *,
    processing_version: int | None = None,
    event_buffer: list[dict[str, object]] | None = None,
) -> None:
    db = SessionLocal()
    try:
        audit = db.get(Audit, audit_id)
        failure_context = (
            exc.to_failure_context()
            if isinstance(exc, AuditStepExecutionError)
            else _build_failure_context(
                stage=PIPELINE_STAGE,
                code=_derive_failure_code(exc),
                message=str(exc),
            )
        )
        if audit is not None and (processing_version is None or audit.processing_version == processing_version):
            _mark_audit_failed(audit, failure_context)
            db.execute(delete(AuditCompetitor).where(AuditCompetitor.audit_id == audit_id))
            _log_audit_step(
                logging.ERROR,
                audit_id,
                PIPELINE_STAGE,
                "failed",
                processing_version=processing_version,
                event_buffer=event_buffer,
                error=str(failure_context["message"]),
                failure_code=failure_context.get("code"),
                failure_stage=failure_context["stage"],
            )
            if event_buffer:
                _flush_audit_events(db, event_buffer)
            db.commit()
        else:
            _log_audit_step(
                logging.ERROR,
                audit_id,
                PIPELINE_STAGE,
                "failed",
                processing_version=processing_version,
                error=str(failure_context["message"]),
                failure_code=failure_context.get("code"),
                failure_stage=failure_context["stage"],
            )
    finally:
        db.close()


def _dispatch_competitor_aggregation_if_ready(audit_id: str, processing_version: int) -> dict[str, object] | None:
    db = SessionLocal()
    should_dispatch = False
    try:
        audit = db.get(Audit, audit_id)
        if (
            audit is None
            or audit.processing_version != processing_version
            or audit.orchestration_stage != COMPETITORS_STAGE
            or audit.competitor_processing_status != COMPETITOR_PROCESSING_COLLECTING
        ):
            return None

        pending_count = int(
            db.scalar(
                select(func.count())
                .select_from(AuditCompetitor)
                .where(
                    AuditCompetitor.audit_id == audit_id,
                    AuditCompetitor.status.in_(
                        [
                            COMPETITOR_PENDING,
                            COMPETITOR_PROCESSING,
                            COMPETITOR_ANALYSIS_PENDING,
                            COMPETITOR_ANALYZING,
                        ]
                    ),
                )
            )
            or 0
        )
        if pending_count > 0:
            return None

        update_result = db.execute(
            update(Audit)
            .where(
                Audit.id == audit_id,
                Audit.processing_version == processing_version,
                Audit.orchestration_stage == COMPETITORS_STAGE,
                Audit.competitor_processing_status == COMPETITOR_PROCESSING_COLLECTING,
            )
            .values(
                competitor_processing_status=COMPETITOR_PROCESSING_AGGREGATING,
                updated_at=_utc_now(),
            )
        )
        should_dispatch = bool(update_result.rowcount)
        db.commit()
    finally:
        db.close()

    if not should_dispatch:
        return None
    return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id, processing_version)


def enqueue_audit_processing(audit_id: str) -> None:
    if _redis_available():
        try:
            process_audit.apply_async(args=(audit_id,), queue=resolve_task_queue(process_audit.name))
            return
        except Exception:
            logger.exception("Failed to enqueue audit via Celery, falling back to inline thread: %s", audit_id)
    _start_inline_audit_processing(audit_id)


@celery_app.task(name="app.process_audit")
def process_audit(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    processing_version: int | None = None
    stage_to_resume: str | None = None
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, PIPELINE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}

        if audit.status == PROCESSING and audit.processing_version > 0:
            processing_version = audit.processing_version
            stage_to_resume = audit.orchestration_stage or FETCH_STAGE
            _log_audit_step(
                logging.INFO,
                audit_id,
                PIPELINE_STAGE,
                "resumed",
                processing_version=processing_version,
                event_buffer=event_buffer,
                orchestration_stage=stage_to_resume,
            )
        else:
            _mark_audit_processing(audit)
            processing_version = int(audit.processing_version or 0) + 1
            audit.processing_version = processing_version
            audit.orchestration_stage = FETCH_STAGE
            stage_to_resume = FETCH_STAGE
            _log_audit_step(
                logging.INFO,
                audit_id,
                PIPELINE_STAGE,
                "started",
                processing_version=processing_version,
                event_buffer=event_buffer,
            )
        _flush_audit_events(db, event_buffer)
        db.commit()
    finally:
        db.close()

    next_task = _resolve_stage_task(stage_to_resume or FETCH_STAGE)
    if next_task is None or processing_version is None:
        return {
            "audit_id": audit_id,
            "status": PROCESSING,
            "processing_version": processing_version,
            "orchestration_stage": stage_to_resume,
        }
    return _dispatch_stage_task(next_task, audit_id, processing_version)


@celery_app.task(name="app.process_audit_fetch_target")
def process_audit_fetch_target(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, FETCH_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            FETCH_STAGE,
            processing_version,
            expected_stage=FETCH_STAGE,
        )
        if skip_result is not None:
            return skip_result

        target_fetch = _run_logged_step(
            audit_id,
            FETCH_STAGE,
            lambda: fetch_page(audit.target_url, use_browser=True),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_fetch_result,
        )
        audit.target_fetch_status = str(target_fetch.get("status") or "")
        audit.target_fetch_method = str(target_fetch.get("fetch_method") or "") or None
        audit.target_fetch_error_code = str(target_fetch.get("fetch_error_code") or "") or None
        audit.target_fetch_error_message = str(target_fetch.get("fetch_error_message") or "") or None
        target_snapshot = ensure_extraction_artifact(
            requested_url=audit.target_url,
            artifact=target_fetch.get("snapshot") if isinstance(target_fetch.get("snapshot"), dict) else None,
            final_url=str(target_fetch.get("final_url") or audit.target_url),
            status_code=(
                int(target_fetch.get("http_status")) if isinstance(target_fetch.get("http_status"), (int, float)) else None
            ),
            html=str(target_fetch.get("html") or "") or None,
            extracted_text=str(target_fetch.get("text") or "") or None,
            fetch_method=audit.target_fetch_method,
        )
        audit.target_snapshot = target_snapshot
        audit.feature_schema_version = str(target_snapshot.get("feature_schema_version") or "") or None
        audit.target_html = extraction_artifact_html(target_snapshot) or None
        audit.extracted_text = extraction_artifact_text(target_snapshot) or None

        if target_fetch["status"] != "success":
            failure_details = {
                key: value
                for key, value in {
                    "fetch_method": audit.target_fetch_method,
                    "http_status": target_fetch.get("http_status"),
                }.items()
                if value is not None
            }
            _mark_audit_failed(
                audit,
                _build_failure_context(
                    stage=FETCH_STAGE,
                    code=audit.target_fetch_error_code,
                    message=audit.target_fetch_error_message or "Target page fetch failed",
                    details=failure_details,
                ),
            )
            db.commit()
            _log_audit_step(
                logging.WARNING,
                audit_id,
                PIPELINE_STAGE,
                "aborted",
                processing_version=processing_version,
                event_buffer=event_buffer,
                reason="target_fetch_failed",
                error_code=audit.target_fetch_error_code,
            )
            _flush_audit_events(db, event_buffer)
            db.commit()
            return {
                "audit_id": audit_id,
                "status": FAILED,
                "error_code": audit.target_fetch_error_code,
            }

        _set_next_orchestration_stage(audit, HEAVY_ANALYSIS_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_run_heavy_analysis, audit_id, processing_version, preserve_queue_affinity=True)


@celery_app.task(name="app.process_audit_run_heavy_analysis")
def process_audit_run_heavy_analysis(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, HEAVY_ANALYSIS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            HEAVY_ANALYSIS_STAGE,
            processing_version,
            expected_stage=HEAVY_ANALYSIS_STAGE,
        )
        if skip_result is not None:
            return skip_result
        if not isinstance(audit.target_snapshot, dict):
            raise RuntimeError("Target page snapshot is not available for heavy analysis")

        heavy_analysis = _run_logged_step(
            audit_id,
            HEAVY_ANALYSIS_STAGE,
            lambda: build_heavy_analysis_payload(audit.target_snapshot),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_heavy_analysis,
        )
        audit.heavy_analysis = heavy_analysis
        _set_next_orchestration_stage(audit, FEATURES_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_extract_features, audit_id, processing_version)


@celery_app.task(name="app.process_audit_extract_features")
def process_audit_extract_features(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, FEATURES_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            FEATURES_STAGE,
            processing_version,
            expected_stage=FEATURES_STAGE,
        )
        if skip_result is not None:
            return skip_result

        target_snapshot = ensure_extraction_artifact(
            requested_url=audit.target_url,
            artifact=audit.target_snapshot if isinstance(audit.target_snapshot, dict) else None,
            final_url=audit.target_url,
            html=str(audit.target_html or "") or None,
            extracted_text=str(audit.extracted_text or "") or None,
            fetch_method=audit.target_fetch_method,
        )
        html = extraction_artifact_html(target_snapshot)
        text = extraction_artifact_text(target_snapshot)
        if not html or not text:
            raise RuntimeError("Target page content is not available for feature extraction")

        query_intent = detect_query_intent(audit.query)
        features = _run_logged_step(
            audit_id,
            FEATURES_STAGE,
            lambda: merge_intent_alignment_features(
                merge_heavy_analysis_features(
                    merge_snapshot_auxiliary_features(
                        build_features(html=html, text=text, query=audit.query),
                        target_snapshot,
                    ),
                    audit.heavy_analysis if isinstance(audit.heavy_analysis, dict) else None,
                ),
                query_intent,
            ),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_features,
        )
        audit.target_snapshot = target_snapshot
        audit.feature_schema_version = str(target_snapshot.get("feature_schema_version") or audit.feature_schema_version or "") or None
        audit.query_intent = query_intent
        audit.features = features
        audit.target_html = None
        _set_next_orchestration_stage(audit, SCORING_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_score_target, audit_id, processing_version)


@celery_app.task(name="app.process_audit_score_target")
def process_audit_score_target(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, SCORING_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            SCORING_STAGE,
            processing_version,
            expected_stage=SCORING_STAGE,
        )
        if skip_result is not None:
            return skip_result
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for scoring")

        score_breakdown = _run_logged_step(
            audit_id,
            SCORING_STAGE,
            lambda: explain_score(audit.features or {}),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_score,
        )
        audit.score_breakdown = score_breakdown
        audit.score = float(score_breakdown["final_score"])
        _set_next_orchestration_stage(audit, COMPETITORS_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_collect_competitors, audit_id, processing_version)


@celery_app.task(name="app.process_audit_collect_competitors")
def process_audit_collect_competitors(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    competitor_ids: list[str] = []
    analysis_competitor_ids: list[str] = []
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, COMPETITORS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            COMPETITORS_STAGE,
            processing_version,
            expected_stage=COMPETITORS_STAGE,
        )
        if skip_result is not None:
            return skip_result
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for competitor comparison")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for competitor comparison")

        existing_competitors = db.scalars(
            select(AuditCompetitor)
            .where(AuditCompetitor.audit_id == audit_id)
            .order_by(AuditCompetitor.serp_rank.asc(), AuditCompetitor.created_at.asc())
        ).all()

        if audit.competitor_processing_status == COMPETITOR_PROCESSING_AGGREGATING:
            return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id, processing_version)

        if audit.competitor_processing_status == COMPETITOR_PROCESSING_COLLECTING and existing_competitors:
            competitor_ids = [item.id for item in existing_competitors if item.status == COMPETITOR_PENDING]
            analysis_competitor_ids = [
                item.id for item in existing_competitors if item.status == COMPETITOR_ANALYSIS_PENDING
            ]
            if not competitor_ids and not analysis_competitor_ids and any(
                item.status in {COMPETITOR_PROCESSING, COMPETITOR_ANALYZING} for item in existing_competitors
            ):
                return {
                    "audit_id": audit_id,
                    "status": PROCESSING,
                    "processing_version": processing_version,
                    "reason": "competitor_tasks_in_progress",
                }
        else:
            competitor_pages = _run_logged_step(
                audit_id,
                COMPETITORS_STAGE,
                lambda: search_competitor_pages(
                    query=audit.query,
                    target_url=audit.target_url,
                    limit=audit.top_n,
                ),
                processing_version=processing_version,
                event_buffer=event_buffer,
                summarize_result=_summarize_competitor_pages,
            )
            db.execute(delete(AuditCompetitor).where(AuditCompetitor.audit_id == audit_id))
            audit.competitor_processing_status = COMPETITOR_PROCESSING_COLLECTING
            audit.competitor_results = None
            audit.comparison_summary = None

            for competitor_page in competitor_pages:
                competitor_id = str(uuid4())
                db.add(
                    AuditCompetitor(
                        id=competitor_id,
                        audit_id=audit_id,
                        url=str(competitor_page.get("url") or ""),
                        domain=str(competitor_page.get("domain") or ""),
                        title=str(competitor_page.get("title") or ""),
                        snippet=str(competitor_page.get("snippet") or ""),
                        serp_rank=int(competitor_page.get("rank") or 0),
                        serp_page=int(competitor_page.get("serp_page") or 0),
                        status=COMPETITOR_PENDING,
                        created_at=_utc_now(),
                        updated_at=_utc_now(),
                    )
                )
                competitor_ids.append(competitor_id)

            audit.updated_at = _utc_now()
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    if analysis_competitor_ids:
        last_result: dict[str, object] | None = None
        for competitor_id in analysis_competitor_ids:
            last_result = _dispatch_stage_task(
                process_audit_analyze_competitor_page,
                audit_id,
                processing_version,
                competitor_id,
                preserve_queue_affinity=True,
            )
        if last_result is not None:
            return last_result

    if not competitor_ids:
        aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id, processing_version)
        if aggregate_result is not None:
            return aggregate_result
        return {
            "audit_id": audit_id,
            "status": PROCESSING,
            "processing_version": processing_version,
            "reason": "competitor_tasks_in_progress",
        }

    queue_name = resolve_task_queue(process_audit_collect_competitor_page.name)
    dispatch_decision = evaluate_queue_dispatch(queue_name)
    if dispatch_decision.action == "allow" and _redis_available():
        db = SessionLocal()
        try:
            enqueued_count = 0
            for competitor_id in competitor_ids:
                try:
                    _enqueue_task(process_audit_collect_competitor_page, audit_id, processing_version, competitor_id)
                    enqueued_count += 1
                except Exception as error:
                    logger.exception(
                        "Failed to enqueue competitor task for audit %s competitor %s",
                        audit_id,
                        competitor_id,
                    )
                    competitor = db.get(AuditCompetitor, competitor_id)
                    if competitor is None:
                        continue
                    failed_result = build_failed_competitor_result(
                        {
                            "url": competitor.url,
                            "domain": competitor.domain,
                            "title": competitor.title,
                            "snippet": competitor.snippet,
                            "rank": competitor.serp_rank,
                            "serp_page": competitor.serp_page,
                        },
                        error,
                        fetch_error_code="queue_dispatch_failed",
                    )
                    _upsert_audit_competitor_result(competitor, failed_result, status=COMPETITOR_FAILED)
            db.commit()
        finally:
            db.close()

        aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id, processing_version)
        if aggregate_result is not None:
            return aggregate_result
        return {
            "audit_id": audit_id,
            "status": PROCESSING,
            "next_stage": process_audit_collect_competitor_page.name,
            "next_queue": resolve_task_queue(process_audit_collect_competitor_page.name),
            "dispatch_mode": "queued",
            "processing_version": processing_version,
            "competitor_tasks_dispatched": len(competitor_ids),
            "competitor_tasks_enqueued": enqueued_count,
        }

    if dispatch_decision.action == "inline":
        _log_audit_step(
            logging.WARNING,
            audit_id,
            process_audit_collect_competitor_page.name,
            "inline_fallback",
            processing_version=processing_version,
            queue=queue_name,
            reason=dispatch_decision.reason,
            guard_message=dispatch_decision.message,
            guard_details=dispatch_decision.details or None,
        )

    last_result: dict[str, object] | None = None
    for competitor_id in competitor_ids:
        last_result = process_audit_collect_competitor_page.run(audit_id, processing_version, competitor_id)
    if last_result is not None:
        return last_result
    return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id, processing_version)


@celery_app.task(name="app.process_audit_collect_competitor_page")
def process_audit_collect_competitor_page(audit_id: str, processing_version: int, competitor_id: str) -> dict[str, object]:
    db = SessionLocal()
    competitor_status: str | None = None
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, COMPETITOR_PAGE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            COMPETITOR_PAGE_STAGE,
            processing_version,
            expected_stage=COMPETITORS_STAGE,
        )
        if skip_result is not None:
            return skip_result

        competitor = _load_audit_competitor(db, competitor_id, audit_id)
        if competitor is None:
            return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}
        if competitor.status == COMPETITOR_ANALYSIS_PENDING:
            competitor_status = COMPETITOR_ANALYSIS_PENDING
        elif competitor.status not in {COMPETITOR_PENDING, COMPETITOR_PROCESSING}:
            return {
                "audit_id": audit_id,
                "competitor_id": competitor_id,
                "status": competitor.status,
            }
        else:
            claimed = False
            if competitor.status == COMPETITOR_PENDING:
                claimed = _claim_audit_competitor_processing(db, audit_id, competitor_id)
                if not claimed:
                    db.rollback()
                    competitor = _load_audit_competitor(db, competitor_id, audit_id)
                    if competitor is None:
                        return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}
                    return {
                        "audit_id": audit_id,
                        "competitor_id": competitor_id,
                        "status": competitor.status,
                    }
                db.commit()

            if competitor.status == COMPETITOR_PROCESSING and not claimed:
                return {
                    "audit_id": audit_id,
                    "competitor_id": competitor_id,
                    "status": competitor.status,
                }

            competitor = _load_audit_competitor(db, competitor_id, audit_id)
            if competitor is None:
                return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}

            search_result = _serialize_competitor_search_result(competitor)
            try:
                result = _run_logged_step(
                    audit_id,
                    COMPETITOR_PAGE_STAGE,
                    lambda: fetch_competitor_page(search_result),
                    processing_version=processing_version,
                    event_buffer=event_buffer,
                    summarize_result=lambda payload: _summarize_competitor_fetch({**payload, "competitor_id": competitor_id}),
                )
                competitor_status = COMPETITOR_ANALYSIS_PENDING if result.get("fetch_status") == "success" else COMPETITOR_FAILED
            except Exception as error:
                logger.warning("Competitor fetch failed for %s: %s", competitor.url, error)
                result = build_failed_competitor_result(search_result, error)
                competitor_status = COMPETITOR_FAILED

            _upsert_audit_competitor_result(competitor, result, status=competitor_status)
            _flush_audit_events(db, event_buffer)
            db.commit()
    finally:
        db.close()

    if competitor_status == COMPETITOR_ANALYSIS_PENDING:
        return _dispatch_stage_task(
            process_audit_analyze_competitor_page,
            audit_id,
            processing_version,
            competitor_id,
            preserve_queue_affinity=True,
        )

    aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id, processing_version)
    if aggregate_result is not None:
        return aggregate_result
    return {
        "audit_id": audit_id,
        "competitor_id": competitor_id,
        "status": PROCESSING,
    }


@celery_app.task(name="app.process_audit_analyze_competitor_page")
def process_audit_analyze_competitor_page(audit_id: str, processing_version: int, competitor_id: str) -> dict[str, object]:
    db = SessionLocal()
    competitor_status: str | None = None
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, COMPETITOR_ANALYSIS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            COMPETITOR_ANALYSIS_STAGE,
            processing_version,
            expected_stage=COMPETITORS_STAGE,
        )
        if skip_result is not None:
            return skip_result

        competitor = _load_audit_competitor(db, competitor_id, audit_id)
        if competitor is None:
            return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}
        if competitor.status not in {COMPETITOR_ANALYSIS_PENDING, COMPETITOR_ANALYZING}:
            return {
                "audit_id": audit_id,
                "competitor_id": competitor_id,
                "status": competitor.status,
            }

        claimed = False
        if competitor.status == COMPETITOR_ANALYSIS_PENDING:
            claimed = _claim_audit_competitor_analysis(db, audit_id, competitor_id)
            if not claimed:
                db.rollback()
                competitor = _load_audit_competitor(db, competitor_id, audit_id)
                if competitor is None:
                    return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}
                return {
                    "audit_id": audit_id,
                    "competitor_id": competitor_id,
                    "status": competitor.status,
                }
            db.commit()

        if competitor.status == COMPETITOR_ANALYZING and not claimed:
            return {
                "audit_id": audit_id,
                "competitor_id": competitor_id,
                "status": competitor.status,
            }

        competitor = _load_audit_competitor(db, competitor_id, audit_id)
        if competitor is None:
            return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}

        search_result = _serialize_competitor_search_result(competitor)
        try:
            result = _run_logged_step(
                audit_id,
                COMPETITOR_ANALYSIS_STAGE,
                lambda: analyze_competitor_snapshot(search_result, audit.query, competitor.snapshot),
                processing_version=processing_version,
                event_buffer=event_buffer,
                summarize_result=lambda payload: _summarize_competitor_analysis({**payload, "competitor_id": competitor_id}),
            )
            competitor_status = COMPETITOR_COMPLETED
        except Exception as error:
            logger.warning("Competitor heavy analysis failed for %s: %s", competitor.url, error)
            result = build_failed_competitor_result(
                search_result,
                error,
                fetch_error_code="competitor_heavy_analysis_failed",
                fetch_method=competitor.fetch_method,
            )
            competitor_status = COMPETITOR_FAILED

        _upsert_audit_competitor_result(competitor, result, status=competitor_status)
        _flush_audit_events(db, event_buffer)
        db.commit()
    finally:
        db.close()

    aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id, processing_version)
    if aggregate_result is not None:
        return aggregate_result
    return {
        "audit_id": audit_id,
        "competitor_id": competitor_id,
        "status": PROCESSING,
    }


@celery_app.task(name="app.process_audit_aggregate_competitors")
def process_audit_aggregate_competitors(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, COMPETITOR_AGGREGATION_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if audit.processing_version != processing_version:
            return _build_stage_skip_response(
                audit_id,
                COMPETITOR_AGGREGATION_STAGE,
                processing_version,
                "stale_processing_version",
                current_version=audit.processing_version,
                current_stage=audit.orchestration_stage,
            )
        if audit.orchestration_stage != COMPETITORS_STAGE:
            if audit.orchestration_stage == RECOMMENDATIONS_STAGE and audit.competitor_processing_status == COMPETITOR_PROCESSING_AGGREGATED:
                return _dispatch_stage_task(process_audit_generate_recommendations, audit_id, processing_version)
            return _build_stage_skip_response(
                audit_id,
                COMPETITOR_AGGREGATION_STAGE,
                processing_version,
                "stage_already_advanced",
                current_version=audit.processing_version,
                current_stage=audit.orchestration_stage,
            )
        if audit.competitor_processing_status not in {COMPETITOR_PROCESSING_AGGREGATING, COMPETITOR_PROCESSING_AGGREGATED}:
            return _build_stage_skip_response(
                audit_id,
                COMPETITOR_AGGREGATION_STAGE,
                processing_version,
                "aggregation_not_ready",
                current_version=audit.processing_version,
                current_stage=audit.orchestration_stage,
            )
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for competitor aggregation")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for competitor aggregation")

        competitors = db.scalars(
            select(AuditCompetitor)
            .where(AuditCompetitor.audit_id == audit_id)
            .order_by(AuditCompetitor.serp_rank.asc(), AuditCompetitor.created_at.asc())
        ).all()
        aggregation_result = _run_logged_step(
            audit_id,
            COMPETITOR_AGGREGATION_STAGE,
            lambda: _build_competitor_aggregation_result(
                user_features=audit.features,
                user_score=float(audit.score),
                competitors=competitors,
                query_intent=audit.query_intent if isinstance(audit.query_intent, dict) else None,
                requested_top_n=int(audit.top_n) if audit.top_n is not None else None,
            ),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=lambda payload: _summarize_competitors(payload["competitor_results"]),
        )
        audit.features = aggregation_result["user_features"]
        comparison_summary = aggregation_result["comparison_summary"]
        competitiveness_score = (
            _extract_competitiveness_score(comparison_summary)
            if isinstance(comparison_summary, dict)
            else None
        )
        if isinstance(audit.score_breakdown, dict):
            relative_explanation = explain_score(aggregation_result["user_features"])
            primary_page_score = float(
                comparison_summary.get("primary_page_score", audit.score)
                if isinstance(comparison_summary, dict)
                else audit.score
            )
            final_score = competitiveness_score if competitiveness_score is not None else primary_page_score
            audit.score_breakdown = {
                **audit.score_breakdown,
                "final_score": round(final_score, 4),
                "primary_page_score": round(primary_page_score, 4),
                "competitiveness_score": round(final_score, 4),
                "competitiveness": comparison_summary.get("competitiveness")
                if isinstance(comparison_summary, dict)
                else None,
                "serp_relative_factors": relative_explanation.get("serp_relative_factors")
                if isinstance(relative_explanation, dict)
                else [],
            }
        if competitiveness_score is not None:
            audit.score = competitiveness_score
        audit.competitor_results = aggregation_result["competitor_results"]
        audit.comparison_summary = comparison_summary
        audit.competitor_processing_status = COMPETITOR_PROCESSING_AGGREGATED
        _set_next_orchestration_stage(audit, RECOMMENDATIONS_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_generate_recommendations, audit_id, processing_version)


@celery_app.task(name="app.process_audit_generate_recommendations")
def process_audit_generate_recommendations(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, RECOMMENDATIONS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            RECOMMENDATIONS_STAGE,
            processing_version,
            expected_stage=RECOMMENDATIONS_STAGE,
        )
        if skip_result is not None:
            return skip_result
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for recommendations")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for recommendations")

        competitor_features = [
            item["features"]
            for item in (audit.competitor_results or [])
            if isinstance(item.get("features"), dict)
        ]
        recommendations = _run_logged_step(
            audit_id,
            RECOMMENDATIONS_STAGE,
            lambda: generate_recommendations(
                page_features=audit.features or {},
                page_score=float(audit.score),
                competitor_pages_features=competitor_features,
            ),
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_recommendations,
        )
        audit.recommendations = recommendations
        _set_next_orchestration_stage(audit, FINALIZE_STAGE)
        _flush_audit_events(db, event_buffer)
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_finalize, audit_id, processing_version)


@celery_app.task(name="app.process_audit_finalize")
def process_audit_finalize(audit_id: str, processing_version: int) -> dict[str, object]:
    db = SessionLocal()
    event_buffer: list[dict[str, object]] = []
    try:
        audit = _load_audit(db, audit_id, FINALIZE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        skip_result = _validate_stage_execution(
            audit_id,
            audit,
            FINALIZE_STAGE,
            processing_version,
            expected_stage=FINALIZE_STAGE,
        )
        if skip_result is not None:
            return skip_result
        if audit.score is None or not isinstance(audit.comparison_summary, dict):
            raise RuntimeError("Audit summary is incomplete and cannot be finalized")

        finalize_payload = _run_logged_step(
            audit_id,
            FINALIZE_STAGE,
            lambda: {
                "recommendations": audit.recommendations or [],
                "warnings": _build_completion_warnings(audit.comparison_summary),
                "comparison_summary": audit.comparison_summary,
                "score": float(audit.score),
            },
            processing_version=processing_version,
            event_buffer=event_buffer,
            summarize_result=_summarize_finalize_result,
        )
        recommendations = finalize_payload["recommendations"]
        warnings = list(finalize_payload["warnings"])
        final_status = _mark_audit_completed(
            audit,
            recommendations=recommendations,
            warnings=warnings,
        )
        _log_audit_step(
            logging.INFO,
            audit_id,
            PIPELINE_STAGE,
            "completed",
            processing_version=processing_version,
            event_buffer=event_buffer,
            final_status=final_status,
            score=float(audit.score),
            competitors_found=int(audit.comparison_summary.get("competitors_found") or 0),
            competitors_failed=int(audit.comparison_summary.get("competitors_failed") or 0),
            recommendations_count=get_recommendation_count(recommendations),
            warnings_count=len(warnings),
        )
        _flush_audit_events(db, event_buffer)
        db.commit()
        return {
            "audit_id": audit_id,
            "status": final_status,
            "score": float(audit.score),
            "competitors_count": len(audit.competitor_results or []),
            "recommendations_count": get_recommendation_count(recommendations),
        }
    except Exception as exc:
        _handle_stage_failure(audit_id, exc, processing_version=processing_version, event_buffer=event_buffer)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()


@celery_app.task(name="app.process_page")
def process_page(url: str) -> str:
    logger.info("Fetching page: %s", url)
    result = fetch_page(url, use_browser=True)
    if result["status"] != "success":
        raise RuntimeError(str(result.get("fetch_error_message") or "Page fetch failed"))
    text = str(result.get("text") or "")
    logger.info("Extracted %s characters from %s", len(text), url)
    return text
