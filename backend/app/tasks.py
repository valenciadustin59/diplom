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
    analyze_competitor_page,
    build_comparison_summary,
    build_failed_competitor_result,
    search_competitor_pages,
)
from app.config import get_settings
from app.db import SessionLocal
from app.features import build_features
from app.ml import explain_score
from app.models import Audit, AuditCompetitor
from app.parser import fetch_page
from app.recommendations import generate_recommendations


logger = get_task_logger(__name__)
settings = get_settings()


FETCH_STAGE = "fetch"
FEATURES_STAGE = "features"
SCORING_STAGE = "scoring"
COMPETITORS_STAGE = "competitors"
RECOMMENDATIONS_STAGE = "recommendations"
FINALIZE_STAGE = "finalize"
PIPELINE_STAGE = "pipeline"
COMPETITOR_PAGE_STAGE = "competitor_page"
COMPETITOR_AGGREGATION_STAGE = "competitor_aggregation"

COMPETITOR_PENDING = "pending"
COMPETITOR_COMPLETED = "completed"
COMPETITOR_FAILED = "failed"

COMPETITOR_PROCESSING_COLLECTING = "collecting"
COMPETITOR_PROCESSING_AGGREGATING = "aggregating"
COMPETITOR_PROCESSING_AGGREGATED = "aggregated"


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
    if step in {FETCH_STAGE, FEATURES_STAGE, SCORING_STAGE, RECOMMENDATIONS_STAGE}:
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


def _format_log_fields(fields: dict[str, object]) -> str:
    rendered_parts: list[str] = []
    for key, value in sorted(fields.items()):
        if value is None:
            continue
        rendered_value = _serialize_log_value(value).replace("\n", "\\n")
        rendered_parts.append(f"{key}={rendered_value}")
    return " ".join(rendered_parts)


def _log_audit_step(level: int, audit_id: str, step: str, event: str, **fields: object) -> None:
    message = f"audit_step audit_id={audit_id} step={step} event={event}"
    formatted_fields = _format_log_fields(fields)
    if formatted_fields:
        message = f"{message} {formatted_fields}"
    logger.log(level, message)


def _run_logged_step(
    audit_id: str,
    step: str,
    action: Callable[[], Any],
    *,
    summarize_result: Callable[[Any], dict[str, object]],
) -> Any:
    _log_audit_step(logging.INFO, audit_id, step, "started")
    started_at = perf_counter()
    try:
        result = action()
    except Exception as exc:
        logger.exception(
            "audit_step audit_id=%s step=%s event=failed duration_ms=%.2f error=%s",
            audit_id,
            step,
            _round_duration_ms(started_at),
            exc,
        )
        raise AuditStepExecutionError(step, exc) from exc
    summary = summarize_result(result)
    _log_audit_step(
        logging.INFO,
        audit_id,
        step,
        "completed",
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


def _summarize_features(features: dict[str, float | int]) -> dict[str, object]:
    return {
        "feature_count": len(features),
        "text_length_chars": features.get("text_length_chars"),
        "semantic_similarity": features.get("semantic_similarity"),
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


def _summarize_recommendations(recommendations: list[dict[str, str]]) -> dict[str, object]:
    return {"recommendations_count": len(recommendations)}


def _summarize_competitor_pages(pages: list[dict[str, object]]) -> dict[str, object]:
    return {"competitors_found": len(pages), "competitor_tasks_planned": len(pages)}


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


def _upsert_audit_competitor_result(competitor: AuditCompetitor, result: dict[str, object], *, status: str) -> None:
    competitor.title = str(result.get("title") or "")
    competitor.snippet = str(result.get("snippet") or "")
    competitor.serp_rank = int(result.get("serp_rank") or competitor.serp_rank or 0)
    competitor.serp_page = int(result.get("serp_page") or competitor.serp_page or 0)
    competitor.fetch_status = str(result.get("fetch_status") or "") or None
    competitor.fetch_method = str(result.get("fetch_method") or "") or None
    competitor.fetch_error_code = str(result.get("fetch_error_code") or "") or None
    competitor.fetch_error_message = str(result.get("fetch_error_message") or "") or None
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


def _enqueue_task(task, *args: object) -> dict[str, object]:
    audit_id = str(args[0]) if args else ""
    queue_name = resolve_task_queue(task.name)
    task.apply_async(args=args, queue=queue_name)
    return {
        "audit_id": audit_id,
        "status": PROCESSING,
        "next_stage": task.name,
        "next_queue": queue_name,
        "dispatch_mode": "queued",
    }


def _start_inline_audit_processing(audit_id: str) -> None:
    logger.warning("Celery is unavailable, running distributed audit pipeline inline in background thread: %s", audit_id)
    Thread(target=process_audit.run, args=(audit_id,), daemon=True).start()


def _clear_analysis_outputs(audit: Audit) -> None:
    audit.extracted_text = None
    audit.target_html = None
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
    recommendations: list[dict[str, str]],
    warnings: list[str],
) -> str:
    final_status = COMPLETED_WITH_WARNINGS if warnings else COMPLETED
    audit.status = transition_status(audit.status, final_status)
    audit.recommendations = recommendations
    audit.warnings = warnings
    audit.error_message = None
    audit.failure_context = None
    audit.updated_at = _utc_now()
    return final_status


def _load_audit(db, audit_id: str, stage: str) -> Audit | None:
    audit = db.get(Audit, audit_id)
    if audit is None:
        logger.warning("Audit not found for stage %s: %s", stage, audit_id)
        _log_audit_step(logging.WARNING, audit_id, stage, "aborted", reason="audit_not_found")
    return audit


def _dispatch_stage_task(task, audit_id: str) -> Any:
    if _redis_available():
        try:
            return _enqueue_task(task, audit_id)
        except Exception:
            logger.exception(
                "Failed to enqueue stage task %s on queue %s for %s, falling back to inline execution",
                task.name,
                resolve_task_queue(task.name),
                audit_id,
            )
    return task.run(audit_id)


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


def _handle_stage_failure(audit_id: str, exc: Exception) -> None:
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
        if audit is not None:
            _mark_audit_failed(audit, failure_context)
            db.execute(delete(AuditCompetitor).where(AuditCompetitor.audit_id == audit_id))
            db.commit()
        _log_audit_step(
            logging.ERROR,
            audit_id,
            PIPELINE_STAGE,
            "failed",
            error=str(failure_context["message"]),
            failure_code=failure_context.get("code"),
            failure_stage=failure_context["stage"],
        )
    finally:
        db.close()


def _dispatch_competitor_aggregation_if_ready(audit_id: str) -> dict[str, object] | None:
    db = SessionLocal()
    should_dispatch = False
    try:
        audit = db.get(Audit, audit_id)
        if audit is None or audit.competitor_processing_status != COMPETITOR_PROCESSING_COLLECTING:
            return None

        pending_count = int(
            db.scalar(
                select(func.count())
                .select_from(AuditCompetitor)
                .where(
                    AuditCompetitor.audit_id == audit_id,
                    AuditCompetitor.status == COMPETITOR_PENDING,
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
    return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id)


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
    _log_audit_step(logging.INFO, audit_id, PIPELINE_STAGE, "started")
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, PIPELINE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        _mark_audit_processing(audit)
        db.commit()
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_fetch_target, audit_id)


@celery_app.task(name="app.process_audit_fetch_target")
def process_audit_fetch_target(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, FETCH_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}

        target_fetch = _run_logged_step(
            audit_id,
            FETCH_STAGE,
            lambda: fetch_page(audit.target_url, use_browser=True),
            summarize_result=_summarize_fetch_result,
        )
        audit.target_fetch_status = str(target_fetch.get("status") or "")
        audit.target_fetch_method = str(target_fetch.get("fetch_method") or "") or None
        audit.target_fetch_error_code = str(target_fetch.get("fetch_error_code") or "") or None
        audit.target_fetch_error_message = str(target_fetch.get("fetch_error_message") or "") or None

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
                reason="target_fetch_failed",
                error_code=audit.target_fetch_error_code,
            )
            return {
                "audit_id": audit_id,
                "status": FAILED,
                "error_code": audit.target_fetch_error_code,
            }

        audit.target_html = str(target_fetch.get("html") or "")
        audit.extracted_text = str(target_fetch.get("text") or "")
        audit.updated_at = _utc_now()
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_extract_features, audit_id)


@celery_app.task(name="app.process_audit_extract_features")
def process_audit_extract_features(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, FEATURES_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}

        html = str(audit.target_html or "")
        text = str(audit.extracted_text or "")
        if not html or not text:
            raise RuntimeError("Target page content is not available for feature extraction")

        features = _run_logged_step(
            audit_id,
            FEATURES_STAGE,
            lambda: build_features(html=html, text=text, query=audit.query),
            summarize_result=_summarize_features,
        )
        audit.features = features
        audit.target_html = None
        audit.updated_at = _utc_now()
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_score_target, audit_id)


@celery_app.task(name="app.process_audit_score_target")
def process_audit_score_target(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, SCORING_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for scoring")

        score_breakdown = _run_logged_step(
            audit_id,
            SCORING_STAGE,
            lambda: explain_score(audit.features or {}),
            summarize_result=_summarize_score,
        )
        audit.score_breakdown = score_breakdown
        audit.score = float(score_breakdown["final_score"])
        audit.updated_at = _utc_now()
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_collect_competitors, audit_id)


@celery_app.task(name="app.process_audit_collect_competitors")
def process_audit_collect_competitors(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    competitor_ids: list[str] = []
    try:
        audit = _load_audit(db, audit_id, COMPETITORS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for competitor comparison")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for competitor comparison")

        competitor_pages = _run_logged_step(
            audit_id,
            COMPETITORS_STAGE,
            lambda: search_competitor_pages(
                query=audit.query,
                target_url=audit.target_url,
                limit=audit.top_n,
            ),
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
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    if not competitor_ids:
        return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id)

    if _redis_available():
        db = SessionLocal()
        try:
            enqueued_count = 0
            for competitor_id in competitor_ids:
                try:
                    _enqueue_task(process_audit_collect_competitor_page, audit_id, competitor_id)
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

        aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id)
        if aggregate_result is not None:
            return aggregate_result
        return {
            "audit_id": audit_id,
            "status": PROCESSING,
            "next_stage": process_audit_collect_competitor_page.name,
            "next_queue": resolve_task_queue(process_audit_collect_competitor_page.name),
            "dispatch_mode": "queued",
            "competitor_tasks_dispatched": len(competitor_ids),
            "competitor_tasks_enqueued": enqueued_count,
        }

    last_result: dict[str, object] | None = None
    for competitor_id in competitor_ids:
        last_result = process_audit_collect_competitor_page.run(audit_id, competitor_id)
    if last_result is not None:
        return last_result
    return _dispatch_stage_task(process_audit_aggregate_competitors, audit_id)


@celery_app.task(name="app.process_audit_collect_competitor_page")
def process_audit_collect_competitor_page(audit_id: str, competitor_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, COMPETITOR_PAGE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}

        competitor = _load_audit_competitor(db, competitor_id, audit_id)
        if competitor is None:
            return {"audit_id": audit_id, "status": "competitor_not_found", "competitor_id": competitor_id}
        if competitor.status != COMPETITOR_PENDING:
            return {
                "audit_id": audit_id,
                "competitor_id": competitor_id,
                "status": competitor.status,
            }

        search_result = {
            "url": competitor.url,
            "domain": competitor.domain,
            "title": competitor.title,
            "snippet": competitor.snippet,
            "rank": competitor.serp_rank,
            "serp_page": competitor.serp_page,
        }
        try:
            result = _run_logged_step(
                audit_id,
                COMPETITOR_PAGE_STAGE,
                lambda: analyze_competitor_page(search_result, audit.query),
                summarize_result=lambda payload: {
                    "competitor_id": competitor_id,
                    "domain": payload.get("domain"),
                    "fetch_status": payload.get("fetch_status"),
                    "score": payload.get("score"),
                },
            )
            competitor_status = COMPETITOR_COMPLETED
        except Exception as error:
            logger.warning("Competitor analysis failed for %s: %s", competitor.url, error)
            result = build_failed_competitor_result(search_result, error)
            competitor_status = COMPETITOR_FAILED

        _upsert_audit_competitor_result(competitor, result, status=competitor_status)
        db.commit()
    finally:
        db.close()

    aggregate_result = _dispatch_competitor_aggregation_if_ready(audit_id)
    if aggregate_result is not None:
        return aggregate_result
    return {
        "audit_id": audit_id,
        "competitor_id": competitor_id,
        "status": PROCESSING,
    }


@celery_app.task(name="app.process_audit_aggregate_competitors")
def process_audit_aggregate_competitors(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, COMPETITOR_AGGREGATION_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for competitor aggregation")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for competitor aggregation")

        competitors = db.scalars(
            select(AuditCompetitor)
            .where(AuditCompetitor.audit_id == audit_id)
            .order_by(AuditCompetitor.serp_rank.asc(), AuditCompetitor.created_at.asc())
        ).all()
        competitor_results = [_serialize_audit_competitor(item) for item in competitors]
        audit.competitor_results = competitor_results
        audit.comparison_summary = build_comparison_summary(
            user_features=audit.features,
            user_score=float(audit.score),
            competitor_results=competitor_results,
        )
        audit.competitor_processing_status = COMPETITOR_PROCESSING_AGGREGATED
        audit.updated_at = _utc_now()
        db.commit()

        _log_audit_step(
            logging.INFO,
            audit_id,
            COMPETITOR_AGGREGATION_STAGE,
            "completed",
            **_summarize_competitors(competitor_results),
        )
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_generate_recommendations, audit_id)


@celery_app.task(name="app.process_audit_generate_recommendations")
def process_audit_generate_recommendations(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, RECOMMENDATIONS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
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
            summarize_result=_summarize_recommendations,
        )
        audit.recommendations = recommendations
        audit.updated_at = _utc_now()
        db.commit()
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
        if isinstance(exc, AuditStepExecutionError):
            raise exc.original_error from exc
        raise
    finally:
        db.close()

    return _dispatch_stage_task(process_audit_finalize, audit_id)


@celery_app.task(name="app.process_audit_finalize")
def process_audit_finalize(audit_id: str) -> dict[str, object]:
    db = SessionLocal()
    try:
        audit = _load_audit(db, audit_id, FINALIZE_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if audit.score is None or not isinstance(audit.comparison_summary, dict):
            raise RuntimeError("Audit summary is incomplete and cannot be finalized")

        recommendations = audit.recommendations or []
        warnings = _build_completion_warnings(audit.comparison_summary)
        final_status = _mark_audit_completed(
            audit,
            recommendations=recommendations,
            warnings=warnings,
        )
        db.commit()
        _log_audit_step(
            logging.INFO,
            audit_id,
            PIPELINE_STAGE,
            "completed",
            final_status=final_status,
            score=float(audit.score),
            competitors_found=int(audit.comparison_summary.get("competitors_found") or 0),
            competitors_failed=int(audit.comparison_summary.get("competitors_failed") or 0),
            recommendations_count=len(recommendations),
            warnings_count=len(warnings),
        )
        return {
            "audit_id": audit_id,
            "status": final_status,
            "score": float(audit.score),
            "competitors_count": len(audit.competitor_results or []),
            "recommendations_count": len(recommendations),
        }
    except Exception as exc:
        _handle_stage_failure(audit_id, exc)
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
