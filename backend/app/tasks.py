from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from threading import Thread
from time import perf_counter
from typing import Any, Callable

from celery.utils.log import get_task_logger
from redis import Redis
from redis.exceptions import RedisError

from app.audit_status import COMPLETED, COMPLETED_WITH_WARNINGS, FAILED, PROCESSING, transition_status
from app.celery_app import celery_app
from app.competitors import MIN_COMPETITORS_FOR_COMPARISON, build_comparison_summary, build_competitor_results
from app.config import get_settings
from app.db import SessionLocal
from app.features import build_features
from app.ml import explain_score
from app.models import Audit
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


def _start_inline_audit_processing(audit_id: str) -> None:
    logger.warning("Celery is unavailable, running distributed audit pipeline inline in background thread: %s", audit_id)
    Thread(target=process_audit.run, args=(audit_id,), daemon=True).start()


def _clear_analysis_outputs(audit: Audit) -> None:
    audit.extracted_text = None
    audit.target_html = None
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
            task.delay(audit_id)
            return {
                "audit_id": audit_id,
                "status": PROCESSING,
                "next_stage": task.name,
                "dispatch_mode": "queued",
            }
        except Exception:
            logger.exception("Failed to enqueue stage task %s for %s, falling back to inline execution", task.name, audit_id)
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


def enqueue_audit_processing(audit_id: str) -> None:
    if _redis_available():
        try:
            process_audit.delay(audit_id)
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
    try:
        audit = _load_audit(db, audit_id, COMPETITORS_STAGE)
        if audit is None:
            return {"audit_id": audit_id, "status": "not_found"}
        if not isinstance(audit.features, dict):
            raise RuntimeError("Target page features are not available for competitor comparison")
        if audit.score is None:
            raise RuntimeError("Target page score is not available for competitor comparison")

        competitor_results = _run_logged_step(
            audit_id,
            COMPETITORS_STAGE,
            lambda: build_competitor_results(
                query=audit.query,
                target_url=audit.target_url,
                top_n=audit.top_n,
            ),
            summarize_result=_summarize_competitors,
        )
        audit.competitor_results = competitor_results
        audit.comparison_summary = build_comparison_summary(
            user_features=audit.features,
            user_score=float(audit.score),
            competitor_results=competitor_results,
        )
        audit.updated_at = _utc_now()
        db.commit()
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
