from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.celery_app import AUDIT_HEAVY_ANALYSIS_QUEUE, resolve_task_queue
from app.config import Settings, get_settings
from app.health import (
    build_execution_detector_payload,
    build_queue_pressure_snapshots,
    collect_broker_runtime_metrics,
    collect_database_runtime_metrics,
    collect_worker_runtime_metrics,
)


PIPELINE_TASK_NAME = "app.process_audit"


@dataclass(slots=True, frozen=True)
class RuntimeCapacityDecision:
    action: Literal["allow", "reject", "inline"]
    reason: str
    message: str
    queue_name: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_http_detail(self) -> dict[str, Any]:
        return {
            "code": self.reason,
            "message": self.message,
            "queue_name": self.queue_name,
            "details": self.details or None,
        }


def _build_runtime_snapshot(settings: Settings) -> dict[str, Any]:
    broker_metrics = collect_broker_runtime_metrics(settings)
    worker_metrics = collect_worker_runtime_metrics(settings)
    queue_pressure = build_queue_pressure_snapshots(broker_metrics, worker_metrics)
    database_metrics = collect_database_runtime_metrics(settings)
    execution_detector = build_execution_detector_payload(database_metrics, queue_pressure)
    return {
        "broker": broker_metrics,
        "workers": worker_metrics,
        "queue_pressure": queue_pressure,
        "database": database_metrics,
        "execution_detector": execution_detector,
    }


def evaluate_new_audit_admission(settings: Settings | None = None) -> RuntimeCapacityDecision:
    runtime_settings = settings or get_settings()
    snapshot = _build_runtime_snapshot(runtime_settings)
    broker_metrics = snapshot["broker"]
    queue_pressure = snapshot["queue_pressure"]
    execution_detector = snapshot["execution_detector"]
    pipeline_queue = resolve_task_queue(PIPELINE_TASK_NAME)
    pipeline_snapshot = queue_pressure.get("queues", {}).get(pipeline_queue, {})
    heavy_analysis_snapshot = queue_pressure.get("queues", {}).get(AUDIT_HEAVY_ANALYSIS_QUEUE, {})

    # If broker telemetry itself is unavailable, keep the existing inline-fallback behavior.
    if broker_metrics.get("status") != "ok":
        return RuntimeCapacityDecision(
            action="allow",
            reason="broker_runtime_telemetry_unavailable",
            message="Runtime admission guard skipped because broker telemetry is unavailable.",
            queue_name=pipeline_queue,
            details={"broker_status": broker_metrics.get("status")},
        )

    if pipeline_snapshot.get("pressure_status") in {"backlogged", "stuck"}:
        return RuntimeCapacityDecision(
            action="reject",
            reason="pipeline_queue_capacity_exhausted",
            message="Невозможно запустить новый аудит: очередь pipeline перегружена или не обслуживается worker'ами.",
            queue_name=pipeline_queue,
            details={
                "pressure_status": pipeline_snapshot.get("pressure_status"),
                "depth": pipeline_snapshot.get("depth"),
                "worker_count": pipeline_snapshot.get("worker_count"),
                "reasons": pipeline_snapshot.get("reasons"),
            },
        )

    if heavy_analysis_snapshot.get("pressure_status") in {"backlogged", "stuck"}:
        return RuntimeCapacityDecision(
            action="reject",
            reason="heavy_analysis_queue_capacity_exhausted",
            message="Невозможно запустить новый аудит: очередь тяжёлых анализаторов перегружена или не обслуживается worker'ами.",
            queue_name=AUDIT_HEAVY_ANALYSIS_QUEUE,
            details={
                "pressure_status": heavy_analysis_snapshot.get("pressure_status"),
                "depth": heavy_analysis_snapshot.get("depth"),
                "worker_count": heavy_analysis_snapshot.get("worker_count"),
                "reasons": heavy_analysis_snapshot.get("reasons"),
            },
        )

    detector_alerts = execution_detector.get("alerts", []) if isinstance(execution_detector.get("alerts"), list) else []
    if any(alert.get("code") == "queued_audits_waiting_too_long" for alert in detector_alerts):
        return RuntimeCapacityDecision(
            action="reject",
            reason="pipeline_queue_backlog_detected",
            message="Невозможно запустить новый аудит: уже накопился backlog ожидающих pipeline-запусков.",
            queue_name=pipeline_queue,
            details={
                "alerts": detector_alerts,
            },
        )

    return RuntimeCapacityDecision(
        action="allow",
        reason="runtime_capacity_available",
        message="Runtime capacity is sufficient for a new audit.",
        queue_name=pipeline_queue,
    )


def evaluate_queue_dispatch(queue_name: str, settings: Settings | None = None) -> RuntimeCapacityDecision:
    runtime_settings = settings or get_settings()
    broker_metrics = collect_broker_runtime_metrics(runtime_settings)
    worker_metrics = collect_worker_runtime_metrics(runtime_settings)
    queue_pressure = build_queue_pressure_snapshots(broker_metrics, worker_metrics)
    queue_snapshot = queue_pressure.get("queues", {}).get(queue_name, {})

    if broker_metrics.get("status") != "ok":
        return RuntimeCapacityDecision(
            action="allow",
            reason="broker_runtime_telemetry_unavailable",
            message="Queue dispatch guard skipped because broker telemetry is unavailable.",
            queue_name=queue_name,
            details={"broker_status": broker_metrics.get("status")},
        )

    pressure_status = str(queue_snapshot.get("pressure_status") or "idle")
    if pressure_status in {"backlogged", "stuck"}:
        return RuntimeCapacityDecision(
            action="inline",
            reason="queue_capacity_guard",
            message="Queue dispatch switched to inline execution because queue capacity is degraded.",
            queue_name=queue_name,
            details={
                "pressure_status": pressure_status,
                "depth": queue_snapshot.get("depth"),
                "worker_count": queue_snapshot.get("worker_count"),
                "reasons": queue_snapshot.get("reasons"),
            },
        )

    return RuntimeCapacityDecision(
        action="allow",
        reason="queue_capacity_available",
        message="Queue dispatch is allowed.",
        queue_name=queue_name,
        details={
            "pressure_status": pressure_status,
            "depth": queue_snapshot.get("depth"),
            "worker_count": queue_snapshot.get("worker_count"),
        },
    )
