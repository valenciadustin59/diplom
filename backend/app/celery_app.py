from celery import Celery
from kombu import Queue

from app.config import get_settings

settings = get_settings()


AUDIT_PIPELINE_QUEUE = "audits.pipeline"
AUDIT_FETCH_QUEUE = "audits.fetch"
AUDIT_HEAVY_ANALYSIS_QUEUE = "audits.heavy_analysis"
AUDIT_FEATURES_QUEUE = "audits.features"
AUDIT_SCORING_QUEUE = "audits.scoring"
AUDIT_COMPETITORS_QUEUE = "audits.competitors"
AUDIT_COMPETITOR_PAGES_QUEUE = "audits.competitor_pages"
AUDIT_RECOMMENDATIONS_QUEUE = "audits.recommendations"
AUDIT_FINALIZE_QUEUE = "audits.finalize"

AUDIT_TASK_ROUTES: dict[str, str] = {
    "app.process_audit": AUDIT_PIPELINE_QUEUE,
    "app.process_audit_fetch_target": AUDIT_FETCH_QUEUE,
    "app.process_audit_run_heavy_analysis": AUDIT_HEAVY_ANALYSIS_QUEUE,
    "app.process_audit_extract_features": AUDIT_FEATURES_QUEUE,
    "app.process_audit_score_target": AUDIT_SCORING_QUEUE,
    "app.process_audit_collect_competitors": AUDIT_COMPETITORS_QUEUE,
    "app.process_audit_collect_competitor_page": AUDIT_COMPETITOR_PAGES_QUEUE,
    "app.process_audit_analyze_competitor_page": AUDIT_HEAVY_ANALYSIS_QUEUE,
    "app.process_audit_aggregate_competitors": AUDIT_COMPETITORS_QUEUE,
    "app.process_audit_generate_recommendations": AUDIT_RECOMMENDATIONS_QUEUE,
    "app.process_audit_finalize": AUDIT_FINALIZE_QUEUE,
    "app.process_page": AUDIT_FETCH_QUEUE,
}

AUDIT_QUEUES: tuple[str, ...] = tuple(dict.fromkeys(AUDIT_TASK_ROUTES.values()))


def resolve_task_queue(task_name: str) -> str:
    return AUDIT_TASK_ROUTES.get(task_name, AUDIT_PIPELINE_QUEUE)

celery_app = Celery(
    "site_audit_backend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue=AUDIT_PIPELINE_QUEUE,
    task_queues=tuple(Queue(queue_name) for queue_name in AUDIT_QUEUES),
    task_routes={task_name: {"queue": queue_name} for task_name, queue_name in AUDIT_TASK_ROUTES.items()},
    task_annotations={
        "app.process_audit_run_heavy_analysis": {
            "soft_time_limit": 90,
            "time_limit": 120,
            "max_retries": 1,
            "default_retry_delay": 15,
        },
        "app.process_audit_analyze_competitor_page": {
            "soft_time_limit": 120,
            "time_limit": 180,
            "max_retries": 1,
            "default_retry_delay": 15,
        },
    },
    task_create_missing_queues=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app"])
