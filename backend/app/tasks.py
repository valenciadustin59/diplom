from datetime import UTC, datetime
from threading import Thread

from celery.utils.log import get_task_logger
from redis import Redis
from redis.exceptions import RedisError

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


def enqueue_audit_processing(audit_id: str) -> None:
    if _redis_available():
        process_audit.delay(audit_id)
        return

    logger.warning("Celery is unavailable, running audit inline in background thread: %s", audit_id)
    Thread(target=process_audit.run, args=(audit_id,), daemon=True).start()


@celery_app.task(name="app.process_audit")
def process_audit(audit_id: str) -> dict[str, object]:
    logger.info("Processing audit pipeline: %s", audit_id)
    db = SessionLocal()
    audit: Audit | None = None

    try:
        audit = db.get(Audit, audit_id)
        if audit is None:
            logger.warning("Audit not found: %s", audit_id)
            return {"audit_id": audit_id, "status": "not_found"}

        audit.status = "processing"
        audit.updated_at = _utc_now()
        audit.error_message = None
        audit.warnings = []
        audit.target_fetch_status = None
        audit.target_fetch_method = None
        audit.target_fetch_error_code = None
        audit.target_fetch_error_message = None
        db.commit()

        target_fetch = fetch_page(audit.target_url, use_browser=True)
        audit.target_fetch_status = str(target_fetch.get("status") or "")
        audit.target_fetch_method = str(target_fetch.get("fetch_method") or "") or None
        audit.target_fetch_error_code = str(target_fetch.get("fetch_error_code") or "") or None
        audit.target_fetch_error_message = str(target_fetch.get("fetch_error_message") or "") or None

        if target_fetch["status"] != "success":
            audit.status = "failed"
            audit.error_message = audit.target_fetch_error_message or "Target page fetch failed"
            audit.updated_at = _utc_now()
            db.commit()
            return {
                "audit_id": audit_id,
                "status": "failed",
                "error_code": audit.target_fetch_error_code,
            }

        html = str(target_fetch.get("html") or "")
        text = str(target_fetch.get("text") or "")
        features = build_features(html=html, text=text, query=audit.query)
        score_breakdown = explain_score(features)
        score = float(score_breakdown["final_score"])

        competitor_results = build_competitor_results(
            query=audit.query,
            target_url=audit.target_url,
            top_n=audit.top_n,
        )
        competitor_features = [
            item["features"]
            for item in competitor_results
            if isinstance(item.get("features"), dict)
        ]
        comparison_summary = build_comparison_summary(
            user_features=features,
            user_score=score,
            competitor_results=competitor_results,
        )
        recommendations = generate_recommendations(
            page_features=features,
            page_score=score,
            competitor_pages_features=competitor_features,
        )

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

        final_status = "completed_with_warnings" if warnings else "completed"

        audit.extracted_text = text
        audit.features = features
        audit.score = score
        audit.score_breakdown = score_breakdown
        audit.competitor_results = competitor_results
        audit.comparison_summary = comparison_summary
        audit.recommendations = recommendations
        audit.warnings = warnings
        audit.status = final_status
        audit.updated_at = _utc_now()
        db.commit()

        return {
            "audit_id": audit_id,
            "status": final_status,
            "score": score,
            "competitors_count": len(competitor_results),
            "recommendations_count": len(recommendations),
        }
    except Exception as exc:
        logger.exception("Audit processing failed: %s", audit_id)
        if audit is not None:
            audit.status = "failed"
            audit.error_message = str(exc)
            audit.updated_at = _utc_now()
            db.commit()
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
