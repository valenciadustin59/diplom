from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from redis import Redis
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.audit_status import PROCESSING, QUEUED, TERMINAL_STATUSES
from app.celery_app import AUDIT_QUEUES, celery_app, resolve_task_queue
from app.config import Settings, get_settings
from app.models import Audit, AuditCompetitor, AuditEvent


STALE_PROCESSING_THRESHOLD_MINUTES = 15
RECENT_TERMINAL_AUDIT_SAMPLE_SIZE = 50
QUEUED_BACKLOG_THRESHOLD_SECONDS = 300.0
DISPATCH_WAIT_THRESHOLD_SECONDS = 180.0
QUEUE_BACKLOG_DEPTH_MULTIPLIER = 3.0
DETECTOR_SAMPLE_LIMIT = 10


TASK_STAGE_NAMES: dict[str, str] = {
    "app.process_audit": "pipeline",
    "app.process_audit_fetch_target": "fetch",
    "app.process_audit_extract_features": "features",
    "app.process_audit_score_target": "scoring",
    "app.process_audit_collect_competitors": "competitors",
    "app.process_audit_collect_competitor_page": "competitor_page",
    "app.process_audit_aggregate_competitors": "competitor_aggregation",
    "app.process_audit_generate_recommendations": "recommendations",
    "app.process_audit_finalize": "finalize",
}
@dataclass(slots=True)
class ComponentHealth:
    status: str
    required: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        details = payload.pop("details")
        payload.update(details)
        return payload


def _normalize_stage_name(value: str | None) -> str | None:
    if value is None:
        return None
    return TASK_STAGE_NAMES.get(value, value)


def _extract_task_name(task_payload: Any) -> str | None:
    if not isinstance(task_payload, dict):
        return None
    name = task_payload.get("name")
    if isinstance(name, str) and name:
        return name
    request_payload = task_payload.get("request")
    if isinstance(request_payload, dict):
        request_name = request_payload.get("name")
        if isinstance(request_name, str) and request_name:
            return request_name
    return None


def _checked_at() -> str:
    return datetime.now(UTC).isoformat()


def _create_runtime_engine(database_url: str):
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )


def _create_session_factory(database_url: str):
    runtime_engine = _create_runtime_engine(database_url)
    return runtime_engine, sessionmaker(bind=runtime_engine, autoflush=False, autocommit=False, class_=Session)


def _normalize_grouped_counts(rows: list[tuple[str | None, int]]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for name, count in rows:
        if not name:
            continue
        normalized[str(name)] = int(count)
    return normalized


def _duration_summary_ms(durations_ms: list[float]) -> dict[str, float | int | None]:
    if not durations_ms:
        return {
            "sample_size": 0,
            "average_ms": None,
            "min_ms": None,
            "max_ms": None,
        }

    return {
        "sample_size": len(durations_ms),
        "average_ms": round(sum(durations_ms) / len(durations_ms), 2),
        "min_ms": round(min(durations_ms), 2),
        "max_ms": round(max(durations_ms), 2),
    }


def _age_seconds(reference_time: datetime, value: datetime | None) -> float | None:
    if value is None:
        return None
    return round((reference_time - value).total_seconds(), 2)


def _resolve_redis_queue_depth_key(queue_name: str) -> str:
    transport_options = celery_app.conf.broker_transport_options or {}
    key_prefix = str(transport_options.get("global_keyprefix") or "")

    # Runtime queue depth metrics assume the default Celery Redis list naming scheme,
    # optionally prefixed via `global_keyprefix`. If transport-level key naming changes
    # beyond that, this endpoint should be updated together with the broker config.
    return f"{key_prefix}{queue_name}"


def check_database_health(settings: Settings) -> ComponentHealth:
    database_url = settings.database_url
    health_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )
    try:
        with health_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ComponentHealth(
            status="ok",
            required=True,
            details={"database_url": database_url},
        )
    except Exception as exc:  # pragma: no cover - defensive around SQLAlchemy driver stack
        return ComponentHealth(
            status="error",
            required=True,
            details={"database_url": database_url, "error": str(exc)},
        )
    finally:
        health_engine.dispose()


def check_redis_health(settings: Settings) -> ComponentHealth:
    client: Redis | None = None
    try:
        client = Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        client.ping()
        return ComponentHealth(
            status="ok",
            required=True,
            details={"broker_url": settings.celery_broker_url},
        )
    except Exception as exc:  # pragma: no cover - depends on redis client implementation
        return ComponentHealth(
            status="error",
            required=True,
            details={"broker_url": settings.celery_broker_url, "error": str(exc)},
        )
    finally:
        if client is not None:
            client.close()


def check_celery_worker_health(settings: Settings) -> ComponentHealth:
    del settings
    try:
        inspector = celery_app.control.inspect(timeout=0.5)
        ping_response = inspector.ping() or {}
        active_queues_response = inspector.active_queues() or {}
    except Exception as exc:  # pragma: no cover - depends on broker availability
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": 0,
                "workers": [],
                "worker_queues": {},
                "expected_queues": list(AUDIT_QUEUES),
                "error": str(exc),
            },
        )

    workers = sorted(ping_response.keys())
    worker_queues = {
        worker_name: sorted(
            queue_info.get("name", "")
            for queue_info in active_queues_response.get(worker_name, [])
            if isinstance(queue_info, dict) and queue_info.get("name")
        )
        for worker_name in workers
    }

    if not workers:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": 0,
                "workers": [],
                "worker_queues": {},
                "expected_queues": list(AUDIT_QUEUES),
                "error": "No Celery workers responded to ping.",
            },
        )

    missing_queues = sorted(
        queue_name
        for queue_name in AUDIT_QUEUES
        if not any(queue_name in queues for queues in worker_queues.values())
    )
    if missing_queues:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "worker_count": len(workers),
                "workers": workers,
                "worker_queues": worker_queues,
                "expected_queues": list(AUDIT_QUEUES),
                "missing_queues": missing_queues,
                "error": "Not all expected audit queues are served by active workers.",
            },
        )

    return ComponentHealth(
        status="ok",
        required=True,
        details={
            "worker_count": len(workers),
            "workers": workers,
            "worker_queues": worker_queues,
            "expected_queues": list(AUDIT_QUEUES),
        },
    )


def check_serp_health(settings: Settings) -> ComponentHealth:
    if settings.serp_provider != "searxng":
        return ComponentHealth(
            status="skipped",
            required=False,
            details={"provider": settings.serp_provider, "reason": "SERP provider is not searxng."},
        )

    if not settings.searxng_base_url:
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": None,
                "error": "SEARXNG_BASE_URL is not configured.",
            },
        )

    base_url = settings.searxng_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=min(settings.search_timeout, 5.0), follow_redirects=True) as client:
            response = client.get(
                f"{base_url}/search",
                params={
                    "q": "healthcheck",
                    "format": "json",
                    "categories": "general",
                    "language": settings.searxng_language,
                },
            )
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results", []) if isinstance(payload, dict) else []
        results_count = len(results) if isinstance(results, list) else 0
        return ComponentHealth(
            status="ok",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": base_url,
                "results_count": results_count,
            },
        )
    except Exception as exc:  # pragma: no cover - external network dependency
        return ComponentHealth(
            status="error",
            required=True,
            details={
                "provider": settings.serp_provider,
                "base_url": base_url,
                "error": str(exc),
            },
        )


def build_liveness_payload(settings: Settings | None = None) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    return {
        "status": "ok",
        "app_name": runtime_settings.app_name,
        "environment": runtime_settings.app_env,
        "checked_at": _checked_at(),
    }


def collect_database_runtime_metrics(settings: Settings) -> dict[str, Any]:
    runtime_engine, session_factory = _create_session_factory(settings.database_url)
    reference_time = datetime.now(UTC).replace(tzinfo=None)
    try:
        with session_factory() as db:
            audits_total = int(db.scalar(select(func.count()).select_from(Audit)) or 0)
            audits_by_status = _normalize_grouped_counts(
                db.execute(select(Audit.status, func.count()).group_by(Audit.status)).all()
            )
            active_by_stage = _normalize_grouped_counts(
                db.execute(
                    select(Audit.orchestration_stage, func.count())
                    .where(
                        Audit.status == PROCESSING,
                        Audit.orchestration_stage.is_not(None),
                    )
                    .group_by(Audit.orchestration_stage)
                ).all()
            )
            stuck_processing_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(Audit)
                    .where(
                        Audit.status == PROCESSING,
                        Audit.updated_at.is_not(None),
                        Audit.updated_at
                        < reference_time - timedelta(minutes=STALE_PROCESSING_THRESHOLD_MINUTES),
                    )
                )
                or 0
            )
            oldest_queued_created_at = db.scalar(
                select(func.min(Audit.created_at)).where(Audit.status == QUEUED)
            )
            oldest_processing_updated_at = db.scalar(
                select(func.min(Audit.updated_at)).where(
                    Audit.status == PROCESSING,
                    Audit.updated_at.is_not(None),
                )
            )
            recent_terminal_rows = db.execute(
                select(Audit.created_at, Audit.updated_at)
                .where(
                    Audit.status.in_(tuple(TERMINAL_STATUSES)),
                    Audit.updated_at.is_not(None),
                )
                .order_by(Audit.updated_at.desc())
                .limit(RECENT_TERMINAL_AUDIT_SAMPLE_SIZE)
            ).all()
            terminal_durations_ms = [
                max(round((updated_at - created_at).total_seconds() * 1000.0, 2), 0.0)
                for created_at, updated_at in recent_terminal_rows
                if created_at is not None and updated_at is not None
            ]

            processing_rows = db.execute(
                select(
                    Audit.id,
                    Audit.processing_version,
                    Audit.orchestration_stage,
                    Audit.updated_at,
                ).where(
                    Audit.status == PROCESSING,
                    Audit.processing_version > 0,
                )
            ).all()
            processing_keys = {
                (str(audit_id), int(processing_version)): {
                    "orchestration_stage": _normalize_stage_name(str(orchestration_stage) if orchestration_stage else None),
                    "updated_at": updated_at,
                }
                for audit_id, processing_version, orchestration_stage, updated_at in processing_rows
            }
            dispatch_waiting_sample: list[dict[str, Any]] = []
            if processing_keys:
                processing_audit_ids = sorted({audit_id for audit_id, _ in processing_keys.keys()})
                processing_versions = sorted({processing_version for _, processing_version in processing_keys.keys()})
                latest_processing_events: dict[tuple[str, int], AuditEvent] = {}
                processing_events = db.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.audit_id.in_(processing_audit_ids),
                        AuditEvent.processing_version.in_(processing_versions),
                    )
                    .order_by(
                        AuditEvent.audit_id.asc(),
                        AuditEvent.processing_version.asc(),
                        AuditEvent.id.desc(),
                    )
                ).all()
                for event in processing_events:
                    if event.processing_version is None:
                        continue
                    event_key = (str(event.audit_id), int(event.processing_version))
                    if event_key in processing_keys and event_key not in latest_processing_events:
                        latest_processing_events[event_key] = event

                for (audit_id, processing_version), audit_payload in processing_keys.items():
                    latest_event = latest_processing_events.get((audit_id, processing_version))
                    if latest_event is None or latest_event.event != "dispatched":
                        continue
                    dispatch_age_seconds = _age_seconds(reference_time, latest_event.created_at)
                    if dispatch_age_seconds is None or dispatch_age_seconds < DISPATCH_WAIT_THRESHOLD_SECONDS:
                        continue
                    dispatch_waiting_sample.append(
                        {
                            "audit_id": audit_id,
                            "processing_version": processing_version,
                            "dispatch_stage": _normalize_stage_name(str(latest_event.stage)),
                            "dispatch_queue": resolve_task_queue(str(latest_event.stage)),
                            "dispatch_age_seconds": dispatch_age_seconds,
                            "orchestration_stage": audit_payload["orchestration_stage"],
                            "updated_age_seconds": _age_seconds(reference_time, audit_payload["updated_at"]),
                        }
                    )

                dispatch_waiting_sample.sort(
                    key=lambda item: float(item.get("dispatch_age_seconds") or 0.0),
                    reverse=True,
                )
                dispatch_waiting_sample = dispatch_waiting_sample[:DETECTOR_SAMPLE_LIMIT]

            competitors_total = int(db.scalar(select(func.count()).select_from(AuditCompetitor)) or 0)
            competitors_by_status = _normalize_grouped_counts(
                db.execute(select(AuditCompetitor.status, func.count()).group_by(AuditCompetitor.status)).all()
            )

        return {
            "status": "ok",
            "database_url": settings.database_url,
            "audits": {
                "total": audits_total,
                "by_status": audits_by_status,
                "active_by_stage": active_by_stage,
                "stuck_processing_count": stuck_processing_count,
                "oldest_queued_age_seconds": _age_seconds(reference_time, oldest_queued_created_at),
                "oldest_processing_update_age_seconds": _age_seconds(reference_time, oldest_processing_updated_at),
                "recent_terminal_duration_ms": _duration_summary_ms(terminal_durations_ms),
                "dispatch_waiting_count": len(dispatch_waiting_sample),
                "dispatch_waiting_sample": dispatch_waiting_sample,
            },
            "competitors": {
                "total": competitors_total,
                "by_status": competitors_by_status,
            },
        }
    except Exception as exc:  # pragma: no cover - depends on runtime database state
        return {
            "status": "error",
            "database_url": settings.database_url,
            "error": str(exc),
            "audits": {},
            "competitors": {},
        }
    finally:
        runtime_engine.dispose()


def collect_broker_runtime_metrics(settings: Settings) -> dict[str, Any]:
    if not settings.celery_broker_url.startswith("redis"):
        return {
            "status": "skipped",
            "broker_url": settings.celery_broker_url,
            "queue_depths": {},
            "total_depth": 0,
            "reason": "Broker depth metrics are implemented only for Redis.",
        }

    client: Redis | None = None
    try:
        client = Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        queue_depths = {
            queue_name: int(client.llen(_resolve_redis_queue_depth_key(queue_name)))
            for queue_name in AUDIT_QUEUES
        }
        return {
            "status": "ok",
            "broker_url": settings.celery_broker_url,
            "queue_depths": queue_depths,
            "total_depth": sum(queue_depths.values()),
            "queue_key_contract": "default_redis_list_name_with_optional_global_keyprefix",
        }
    except Exception as exc:  # pragma: no cover - depends on broker availability
        return {
            "status": "error",
            "broker_url": settings.celery_broker_url,
            "queue_depths": {},
            "total_depth": 0,
            "error": str(exc),
        }
    finally:
        if client is not None:
            client.close()


def collect_worker_runtime_metrics(settings: Settings) -> dict[str, Any]:
    del settings
    try:
        inspector = celery_app.control.inspect(timeout=0.5)
        stats_response = inspector.stats() or {}
        active_response = inspector.active() or {}
        reserved_response = inspector.reserved() or {}
        scheduled_response = inspector.scheduled() or {}
        active_queues_response = inspector.active_queues() or {}
    except Exception as exc:  # pragma: no cover - depends on broker availability
        return {
            "status": "error",
            "online_count": 0,
            "workers": {},
            "active_tasks_total": 0,
            "reserved_tasks_total": 0,
            "scheduled_tasks_total": 0,
            "error": str(exc),
        }

    worker_names = sorted(
        set(stats_response.keys())
        | set(active_response.keys())
        | set(reserved_response.keys())
        | set(scheduled_response.keys())
        | set(active_queues_response.keys())
    )

    worker_payload: dict[str, dict[str, Any]] = {}
    queue_activity: dict[str, dict[str, Any]] = {
        queue_name: {
            "workers": [],
            "worker_count": 0,
            "estimated_concurrency": 0,
            "active_tasks": 0,
            "reserved_tasks": 0,
            "scheduled_tasks": 0,
        }
        for queue_name in AUDIT_QUEUES
    }
    for worker_name in worker_names:
        stats_entry = stats_response.get(worker_name) if isinstance(stats_response.get(worker_name), dict) else {}
        pool_entry = stats_entry.get("pool") if isinstance(stats_entry.get("pool"), dict) else {}
        queue_names = sorted(
            queue_info.get("name", "")
            for queue_info in active_queues_response.get(worker_name, [])
            if isinstance(queue_info, dict) and queue_info.get("name")
        )
        worker_payload[worker_name] = {
            "queues": queue_names,
            "active_tasks": len(active_response.get(worker_name, [])),
            "reserved_tasks": len(reserved_response.get(worker_name, [])),
            "scheduled_tasks": len(scheduled_response.get(worker_name, [])),
            "pool_max_concurrency": int(pool_entry.get("max-concurrency") or 0),
            "pid": stats_entry.get("pid"),
        }

        worker_concurrency = worker_payload[worker_name]["pool_max_concurrency"] or (1 if queue_names else 0)
        for queue_name in queue_names:
            queue_snapshot = queue_activity.setdefault(
                queue_name,
                {
                    "workers": [],
                    "worker_count": 0,
                    "estimated_concurrency": 0,
                    "active_tasks": 0,
                    "reserved_tasks": 0,
                    "scheduled_tasks": 0,
                },
            )
            queue_snapshot["workers"].append(worker_name)
            queue_snapshot["estimated_concurrency"] += worker_concurrency

        for task_payload in active_response.get(worker_name, []):
            task_name = _extract_task_name(task_payload)
            if task_name is None:
                continue
            queue_activity[resolve_task_queue(task_name)]["active_tasks"] += 1

        for task_payload in reserved_response.get(worker_name, []):
            task_name = _extract_task_name(task_payload)
            if task_name is None:
                continue
            queue_activity[resolve_task_queue(task_name)]["reserved_tasks"] += 1

        for task_payload in scheduled_response.get(worker_name, []):
            task_name = _extract_task_name(task_payload)
            if task_name is None:
                continue
            queue_activity[resolve_task_queue(task_name)]["scheduled_tasks"] += 1

    for queue_name, snapshot in queue_activity.items():
        snapshot["workers"] = sorted(set(str(worker_name) for worker_name in snapshot["workers"]))
        snapshot["worker_count"] = len(snapshot["workers"])
        snapshot["inflight_tasks"] = (
            int(snapshot["active_tasks"])
            + int(snapshot["reserved_tasks"])
            + int(snapshot["scheduled_tasks"])
        )
        snapshot["available_capacity_estimate"] = max(
            int(snapshot["estimated_concurrency"]) - int(snapshot["active_tasks"]),
            0,
        )

    status = "ok" if worker_names else "warning"
    return {
        "status": status,
        "online_count": len(worker_names),
        "workers": worker_payload,
        "active_tasks_total": sum(item["active_tasks"] for item in worker_payload.values()),
        "reserved_tasks_total": sum(item["reserved_tasks"] for item in worker_payload.values()),
        "scheduled_tasks_total": sum(item["scheduled_tasks"] for item in worker_payload.values()),
        "expected_queues": list(AUDIT_QUEUES),
        "queue_activity": queue_activity,
        **({"warning": "No Celery workers responded to inspect."} if not worker_names else {}),
    }


def build_queue_pressure_snapshots(
    broker_metrics: dict[str, Any],
    worker_metrics: dict[str, Any],
) -> dict[str, Any]:
    queue_depths = broker_metrics.get("queue_depths") if isinstance(broker_metrics.get("queue_depths"), dict) else {}
    queue_activity = worker_metrics.get("queue_activity") if isinstance(worker_metrics.get("queue_activity"), dict) else {}
    queue_snapshots: dict[str, dict[str, Any]] = {}
    backlogged_queues: list[str] = []
    stuck_queues: list[str] = []

    for queue_name in AUDIT_QUEUES:
        queue_payload = queue_activity.get(queue_name) if isinstance(queue_activity.get(queue_name), dict) else {}
        depth = int(queue_depths.get(queue_name) or 0)
        worker_count = int(queue_payload.get("worker_count") or 0)
        estimated_concurrency = int(queue_payload.get("estimated_concurrency") or 0)
        active_tasks = int(queue_payload.get("active_tasks") or 0)
        reserved_tasks = int(queue_payload.get("reserved_tasks") or 0)
        scheduled_tasks = int(queue_payload.get("scheduled_tasks") or 0)
        inflight_tasks = int(queue_payload.get("inflight_tasks") or (active_tasks + reserved_tasks + scheduled_tasks))
        available_capacity_estimate = int(
            queue_payload.get("available_capacity_estimate")
            if isinstance(queue_payload.get("available_capacity_estimate"), int)
            else max(estimated_concurrency - active_tasks, 0)
        )

        pressure_status = "idle"
        reasons: list[str] = []
        if depth == 0:
            if inflight_tasks > 0:
                pressure_status = "busy"
                reasons.append("inflight_without_backlog")
        elif worker_count == 0:
            pressure_status = "stuck"
            reasons.append("no_workers_serving_queue")
        elif inflight_tasks == 0 and depth > max(estimated_concurrency, 1):
            pressure_status = "backlogged"
            reasons.append("queued_tasks_without_drain_activity")
        elif inflight_tasks == 0:
            pressure_status = "waiting"
            reasons.append("queued_tasks_pending_pickup")
        elif depth > max(estimated_concurrency, 1) * QUEUE_BACKLOG_DEPTH_MULTIPLIER:
            pressure_status = "backlogged"
            reasons.append("depth_exceeds_estimated_capacity")
        else:
            pressure_status = "draining"
            reasons.append("queue_is_draining")

        if pressure_status == "backlogged":
            backlogged_queues.append(queue_name)
        if pressure_status == "stuck":
            stuck_queues.append(queue_name)

        queue_snapshots[queue_name] = {
            "depth": depth,
            "workers": list(queue_payload.get("workers") or []),
            "worker_count": worker_count,
            "estimated_concurrency": estimated_concurrency,
            "active_tasks": active_tasks,
            "reserved_tasks": reserved_tasks,
            "scheduled_tasks": scheduled_tasks,
            "inflight_tasks": inflight_tasks,
            "available_capacity_estimate": available_capacity_estimate,
            "pressure_status": pressure_status,
            "reasons": reasons,
        }

    return {
        "status": "degraded" if backlogged_queues or stuck_queues else "ok",
        "thresholds": {
            "queue_backlog_depth_multiplier": QUEUE_BACKLOG_DEPTH_MULTIPLIER,
        },
        "queues": queue_snapshots,
        "backlogged_queues": backlogged_queues,
        "stuck_queues": stuck_queues,
    }


def build_execution_detector_payload(
    database_metrics: dict[str, Any],
    queue_pressure: dict[str, Any],
) -> dict[str, Any]:
    audits_metrics = database_metrics.get("audits") if isinstance(database_metrics.get("audits"), dict) else {}
    alerts: list[dict[str, Any]] = []

    stuck_processing_count = int(audits_metrics.get("stuck_processing_count") or 0)
    if stuck_processing_count > 0:
        alerts.append(
            {
                "code": "stuck_processing_audits",
                "severity": "error",
                "count": stuck_processing_count,
                "threshold_minutes": STALE_PROCESSING_THRESHOLD_MINUTES,
            }
        )

    oldest_queued_age_seconds = audits_metrics.get("oldest_queued_age_seconds")
    if isinstance(oldest_queued_age_seconds, (int, float)) and oldest_queued_age_seconds >= QUEUED_BACKLOG_THRESHOLD_SECONDS:
        alerts.append(
            {
                "code": "queued_audits_waiting_too_long",
                "severity": "warning",
                "oldest_age_seconds": round(float(oldest_queued_age_seconds), 2),
                "threshold_seconds": QUEUED_BACKLOG_THRESHOLD_SECONDS,
                "queue": resolve_task_queue("app.process_audit"),
            }
        )

    dispatch_waiting_count = int(audits_metrics.get("dispatch_waiting_count") or 0)
    dispatch_waiting_sample = list(audits_metrics.get("dispatch_waiting_sample") or [])
    if dispatch_waiting_count > 0:
        alerts.append(
            {
                "code": "dispatched_stages_waiting_too_long",
                "severity": "warning",
                "count": dispatch_waiting_count,
                "threshold_seconds": DISPATCH_WAIT_THRESHOLD_SECONDS,
                "sample": dispatch_waiting_sample,
            }
        )

    for queue_name in queue_pressure.get("stuck_queues", []):
        queue_snapshot = queue_pressure.get("queues", {}).get(queue_name, {})
        alerts.append(
            {
                "code": "queue_without_workers",
                "severity": "error",
                "queue": queue_name,
                "depth": int(queue_snapshot.get("depth") or 0),
            }
        )

    for queue_name in queue_pressure.get("backlogged_queues", []):
        queue_snapshot = queue_pressure.get("queues", {}).get(queue_name, {})
        alerts.append(
            {
                "code": "queue_backlog_detected",
                "severity": "warning",
                "queue": queue_name,
                "depth": int(queue_snapshot.get("depth") or 0),
                "active_tasks": int(queue_snapshot.get("active_tasks") or 0),
                "reserved_tasks": int(queue_snapshot.get("reserved_tasks") or 0),
                "scheduled_tasks": int(queue_snapshot.get("scheduled_tasks") or 0),
            }
        )

    return {
        "status": "degraded" if alerts else "ok",
        "thresholds": {
            "stale_processing_threshold_minutes": STALE_PROCESSING_THRESHOLD_MINUTES,
            "queued_backlog_threshold_seconds": QUEUED_BACKLOG_THRESHOLD_SECONDS,
            "dispatch_wait_threshold_seconds": DISPATCH_WAIT_THRESHOLD_SECONDS,
        },
        "alerts": alerts,
        "summary": {
            "alert_count": len(alerts),
            "stuck_processing_count": stuck_processing_count,
            "dispatch_waiting_count": dispatch_waiting_count,
            "stuck_queue_count": len(queue_pressure.get("stuck_queues", [])),
            "backlogged_queue_count": len(queue_pressure.get("backlogged_queues", [])),
        },
    }


def build_metrics_payload(settings: Settings | None = None) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    database_metrics = collect_database_runtime_metrics(runtime_settings)
    broker_metrics = collect_broker_runtime_metrics(runtime_settings)
    worker_metrics = collect_worker_runtime_metrics(runtime_settings)
    queue_pressure = build_queue_pressure_snapshots(broker_metrics, worker_metrics)
    execution_detector = build_execution_detector_payload(database_metrics, queue_pressure)
    components = {
        "database": database_metrics,
        "broker": broker_metrics,
        "workers": worker_metrics,
        "queue_pressure": queue_pressure,
        "execution_detector": execution_detector,
    }
    degraded_statuses = {"error", "warning", "degraded"}
    overall_status = (
        "degraded"
        if any(component.get("status") in degraded_statuses for component in components.values())
        else "ok"
    )

    return {
        "status": overall_status,
        "app_name": runtime_settings.app_name,
        "environment": runtime_settings.app_env,
        "checked_at": _checked_at(),
        "orchestration": {
            "expected_queues": list(AUDIT_QUEUES),
            "broker_url": runtime_settings.celery_broker_url,
            "result_backend": runtime_settings.celery_result_backend,
        },
        **components,
    }


def build_readiness_payload(settings: Settings | None = None) -> tuple[dict[str, Any], bool]:
    runtime_settings = settings or get_settings()
    checks = {
        "database": check_database_health(runtime_settings),
        "redis": check_redis_health(runtime_settings),
        "celery_workers": check_celery_worker_health(runtime_settings),
        "serp": check_serp_health(runtime_settings),
    }
    ready = all(
        component.status == "ok"
        for component in checks.values()
        if component.required
    )

    payload = {
        "status": "ready" if ready else "not_ready",
        "app_name": runtime_settings.app_name,
        "environment": runtime_settings.app_env,
        "checked_at": _checked_at(),
        "checks": {name: component.to_dict() for name, component in checks.items()},
        "orchestration": {
            "expected_queues": list(AUDIT_QUEUES),
            "broker_url": runtime_settings.celery_broker_url,
            "result_backend": runtime_settings.celery_result_backend,
        },
    }
    return payload, ready
