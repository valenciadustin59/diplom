from __future__ import annotations
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Sequence
import httpx
from app.audit_status import TERMINAL_STATUSES
DEFAULT_BENCHMARK_NAME = "distributed-runtime-benchmark"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_BENCHMARK_TIMEOUT_SECONDS = 600.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_METRICS_INTERVAL_SECONDS = 2.0
DEFAULT_MAX_INFLIGHT = 3
DEFAULT_BENCHMARK_OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "benchmarks"
@dataclass(frozen=True, slots=True)
class BenchmarkWorkloadEntry:
    label: str
    query: str
    target_url: str
    top_n: int = 10
    def to_request_payload(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "target_url": self.target_url,
            "top_n": self.top_n,
        }
    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "query": self.query,
            "target_url": self.target_url,
            "top_n": self.top_n,
        }
@dataclass(frozen=True, slots=True)
class DistributedBenchmarkConfig:
    benchmark_name: str = DEFAULT_BENCHMARK_NAME
    max_inflight: int = DEFAULT_MAX_INFLIGHT
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    metrics_interval_seconds: float = DEFAULT_METRICS_INTERVAL_SECONDS
    timeout_seconds: float = DEFAULT_BENCHMARK_TIMEOUT_SECONDS
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "max_inflight": self.max_inflight,
            "poll_interval_seconds": self.poll_interval_seconds,
            "metrics_interval_seconds": self.metrics_interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "request_timeout_seconds": self.request_timeout_seconds,
        }
@dataclass(slots=True)
class BenchmarkAuditRecord:
    label: str
    request_payload: dict[str, Any]
    admission_status: str
    create_http_status: int | None = None
    create_latency_ms: float | None = None
    audit_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    terminal_status: str | None = None
    last_status: str | None = None
    total_duration_ms: float | None = None
    poll_count: int = 0
    details: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    error: str | None = None
    @classmethod
    def from_workload(cls, entry: BenchmarkWorkloadEntry) -> "BenchmarkAuditRecord":
        return cls(
            label=entry.label,
            request_payload=entry.to_request_payload(),
            admission_status="pending",
        )
    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "request_payload": self.request_payload,
            "admission_status": self.admission_status,
            "create_http_status": self.create_http_status,
            "create_latency_ms": self.create_latency_ms,
            "audit_id": self.audit_id,
            "created_at": _serialize_datetime(self.created_at),
            "completed_at": _serialize_datetime(self.completed_at),
            "terminal_status": self.terminal_status,
            "last_status": self.last_status,
            "total_duration_ms": self.total_duration_ms,
            "poll_count": self.poll_count,
            "details": self.details,
            "diagnostics": self.diagnostics,
            "error": self.error,
        }
@dataclass(frozen=True, slots=True)
class BenchmarkRuntimeSample:
    captured_at: datetime
    http_status: int | None
    payload: dict[str, Any]
    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": _serialize_datetime(self.captured_at),
            "http_status": self.http_status,
            "payload": self.payload,
        }
def load_benchmark_workload(path: str | Path) -> tuple[BenchmarkWorkloadEntry, ...]:
    workload_path = Path(path)
    raw_payload = json.loads(workload_path.read_text(encoding="utf-8"))
    raw_entries = raw_payload.get("audits") if isinstance(raw_payload, dict) else raw_payload
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("Benchmark workload must be a non-empty list or {'audits': [...]} payload.")
    entries: list[BenchmarkWorkloadEntry] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError("Each benchmark workload entry must be an object.")
        label = str(raw_entry.get("label") or f"audit-{index}").strip()
        query = str(raw_entry.get("query") or "").strip()
        target_url = str(raw_entry.get("target_url") or "").strip()
        top_n = int(raw_entry.get("top_n") or 10)
        if not query:
            raise ValueError(f"Benchmark workload entry '{label}' must define a non-empty query.")
        if not target_url:
            raise ValueError(f"Benchmark workload entry '{label}' must define a non-empty target_url.")
        if top_n < 1 or top_n > 100:
            raise ValueError(f"Benchmark workload entry '{label}' must keep top_n within 1..100.")
        entries.append(
            BenchmarkWorkloadEntry(
                label=label,
                query=query,
                target_url=target_url,
                top_n=top_n,
            )
        )
    return tuple(entries)
def build_default_benchmark_output_dir(
    benchmark_name: str = DEFAULT_BENCHMARK_NAME,
    now_factory: Callable[[], datetime] | None = None,
) -> Path:
    now_value = (now_factory or _utc_now)()
    slug = benchmark_name.strip().lower().replace(" ", "-") or DEFAULT_BENCHMARK_NAME
    timestamp = now_value.strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_BENCHMARK_OUTPUT_ROOT / f"{timestamp}-{slug}"
def run_distributed_benchmark(
    client: httpx.Client,
    workload: Sequence[BenchmarkWorkloadEntry],
    config: DistributedBenchmarkConfig,
    *,
    base_url: str,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    if not workload:
        raise ValueError("Distributed benchmark workload must not be empty.")
    if config.max_inflight < 1:
        raise ValueError("max_inflight must be >= 1")
    if config.poll_interval_seconds <= 0 or config.metrics_interval_seconds <= 0 or config.timeout_seconds <= 0:
        raise ValueError("Benchmark timing configuration values must be > 0")
    pending = deque(workload)
    active_records: dict[str, BenchmarkAuditRecord] = {}
    finished_records: list[BenchmarkAuditRecord] = []
    runtime_samples: list[BenchmarkRuntimeSample] = []
    effective_now_factory = now_factory or _utc_now
    started_at = effective_now_factory()
    started_monotonic = monotonic()
    next_metrics_sample_at = started_monotonic
    while pending or active_records:
        current_monotonic = monotonic()
        if current_monotonic - started_monotonic >= config.timeout_seconds:
            break
        while pending and len(active_records) < config.max_inflight:
            entry = pending.popleft()
            record = BenchmarkAuditRecord.from_workload(entry)
            request_started = monotonic()
            try:
                response = client.post("/audits", json=entry.to_request_payload())
            except Exception as exc:  # pragma: no cover - runtime HTTP/network path
                record.admission_status = "error"
                record.create_latency_ms = round((monotonic() - request_started) * 1000.0, 2)
                record.error = f"create_request_failed: {exc}"
                finished_records.append(record)
                continue
            record.create_latency_ms = round((monotonic() - request_started) * 1000.0, 2)
            record.create_http_status = response.status_code
            response_payload = _safe_response_payload(response)
            if response.status_code == 201 and isinstance(response_payload, dict):
                record.admission_status = "accepted"
                record.audit_id = str(response_payload.get("id") or "") or None
                record.last_status = str(response_payload.get("status") or "") or None
                record.created_at = _parse_datetime(response_payload.get("created_at")) or effective_now_factory()
                record.details = response_payload
                if record.audit_id is None:
                    record.admission_status = "error"
                    record.error = "create_audit_response_missing_id"
                    finished_records.append(record)
                else:
                    active_records[record.audit_id] = record
            elif response.status_code == 503:
                record.admission_status = "rejected"
                record.details = response_payload if isinstance(response_payload, dict) else {"detail": response_payload}
                finished_records.append(record)
            else:
                record.admission_status = "error"
                record.details = {
                    "status_code": response.status_code,
                    "response": response_payload,
                }
                finished_records.append(record)
        current_monotonic = monotonic()
        if current_monotonic >= next_metrics_sample_at:
            runtime_samples.append(_collect_runtime_sample(client, now_factory=effective_now_factory))
            next_metrics_sample_at = current_monotonic + config.metrics_interval_seconds
        if not active_records:
            if pending:
                sleep(config.poll_interval_seconds)
            continue
        completed_ids: list[str] = []
        for audit_id, record in list(active_records.items()):
            try:
                response = client.get(f"/audits/{audit_id}")
            except Exception as exc:  # pragma: no cover - runtime HTTP/network path
                record.error = f"audit_poll_failed: {exc}"
                continue
            response_payload = _safe_response_payload(response)
            if response.status_code != 200 or not isinstance(response_payload, dict):
                record.error = f"audit_poll_failed_status: {response.status_code}"
                record.details = {
                    **(record.details or {}),
                    "latest_poll_response": response_payload,
                }
                continue
            record.poll_count += 1
            record.last_status = str(response_payload.get("status") or "") or None
            if record.last_status not in TERMINAL_STATUSES:
                continue
            record.terminal_status = record.last_status
            record.completed_at = _parse_datetime(response_payload.get("updated_at")) or effective_now_factory()
            diagnostics_payload = _fetch_audit_diagnostics(client, audit_id)
            if diagnostics_payload is not None:
                record.diagnostics = diagnostics_payload
                total_duration = diagnostics_payload.get("total_duration_ms")
                if isinstance(total_duration, (int, float)):
                    record.total_duration_ms = round(float(total_duration), 2)
            completed_ids.append(audit_id)
            finished_records.append(record)
        for audit_id in completed_ids:
            active_records.pop(audit_id, None)
        if pending or active_records:
            sleep(config.poll_interval_seconds)
    if active_records:
        timed_out_at = effective_now_factory()
        for record in active_records.values():
            record.terminal_status = "timeout"
            record.completed_at = timed_out_at
            record.error = record.error or f"benchmark_timeout_after_{config.timeout_seconds}_seconds"
            finished_records.append(record)
    runtime_samples.append(_collect_runtime_sample(client, now_factory=effective_now_factory))
    finished_at = effective_now_factory()
    return build_distributed_benchmark_report(
        base_url=base_url,
        workload=workload,
        config=config,
        audit_records=finished_records,
        runtime_samples=runtime_samples,
        started_at=started_at,
        finished_at=finished_at,
    )
def build_distributed_benchmark_report(
    *,
    base_url: str,
    workload: Sequence[BenchmarkWorkloadEntry],
    config: DistributedBenchmarkConfig,
    audit_records: Sequence[BenchmarkAuditRecord],
    runtime_samples: Sequence[BenchmarkRuntimeSample],
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Any]:
    duration_seconds = max((finished_at - started_at).total_seconds(), 0.0)
    admission_summary = _build_admission_summary(audit_records, duration_seconds, requested_count=len(workload))
    audit_summary = _build_audit_summary(audit_records, duration_seconds)
    runtime_summary = _build_runtime_summary(runtime_samples)
    return {
        "benchmark_name": config.benchmark_name,
        "base_url": base_url,
        "generated_at": _serialize_datetime(finished_at),
        "window": {
            "started_at": _serialize_datetime(started_at),
            "finished_at": _serialize_datetime(finished_at),
            "duration_seconds": round(duration_seconds, 2),
        },
        "configuration": config.to_dict(),
        "workload": {
            "requested_audits": len(workload),
            "entries": [entry.to_dict() for entry in workload],
        },
        "admission": admission_summary,
        "audits": audit_summary,
        "runtime": runtime_summary,
        "audit_records": [record.to_dict() for record in audit_records],
        "runtime_samples": [sample.to_dict() for sample in runtime_samples],
    }
def render_benchmark_report_markdown(report: dict[str, Any]) -> str:
    window = report.get("window", {}) if isinstance(report.get("window"), dict) else {}
    admission = report.get("admission", {}) if isinstance(report.get("admission"), dict) else {}
    audits = report.get("audits", {}) if isinstance(report.get("audits"), dict) else {}
    runtime = report.get("runtime", {}) if isinstance(report.get("runtime"), dict) else {}
    latency = audits.get("latency_ms", {}) if isinstance(audits.get("latency_ms"), dict) else {}
    throughput = audits.get("throughput", {}) if isinstance(audits.get("throughput"), dict) else {}
    backlog = runtime.get("queue_backlog", {}) if isinstance(runtime.get("queue_backlog"), dict) else {}
    worker_utilization = runtime.get("worker_utilization", {}) if isinstance(runtime.get("worker_utilization"), dict) else {}
    overall_utilization = worker_utilization.get("overall", {}) if isinstance(worker_utilization.get("overall"), dict) else {}
    profile_utilization = worker_utilization.get("by_profile", {}) if isinstance(worker_utilization.get("by_profile"), dict) else {}
    topology_profiles = runtime.get("topology_profiles", {}) if isinstance(runtime.get("topology_profiles"), dict) else {}
    configured_profiles = topology_profiles.get("configured_profiles", {}) if isinstance(topology_profiles.get("configured_profiles"), dict) else {}
    profile_pressure_counts = topology_profiles.get("profile_queue_pressure_counts", {}) if isinstance(topology_profiles.get("profile_queue_pressure_counts"), dict) else {}
    alerts = runtime.get("alerts", {}) if isinstance(runtime.get("alerts"), dict) else {}
    alert_code_counts = alerts.get("alert_code_counts", {}) if isinstance(alerts.get("alert_code_counts"), dict) else {}
    lines = [
        f"# {report.get('benchmark_name', DEFAULT_BENCHMARK_NAME)}",
        "",
        f"- Generated At: {report.get('generated_at')}",
        f"- Base URL: {report.get('base_url')}",
        f"- Window: {window.get('started_at')} -> {window.get('finished_at')} ({window.get('duration_seconds')} s)",
        "",
        "## Admission",
        "",
        f"- Requested Audits: {admission.get('requested')}",
        f"- Accepted Audits: {admission.get('accepted')}",
        f"- Rejected Audits: {admission.get('rejected')}",
        f"- Admission Errors: {admission.get('errors')}",
        f"- Acceptance Rate: {admission.get('acceptance_rate')}",
        "",
        "## Audit Latency And Throughput",
        "",
        f"- Terminal Status Counts: {json.dumps(audits.get('terminal_status_counts', {}), ensure_ascii=False, sort_keys=True)}",
        f"- Latency Avg / P50 / P95 / Max (ms): {latency.get('average')} / {latency.get('p50')} / {latency.get('p95')} / {latency.get('max')}",
        f"- Accepted Per Minute: {throughput.get('accepted_per_minute')}",
        f"- Successful Terminal Per Minute: {throughput.get('successful_terminal_per_minute')}",
        "",
        "## Queue Backlog",
        "",
        f"- Runtime Samples: {runtime.get('sample_count')}",
        f"- Degraded Sample Ratio: {backlog.get('degraded_sample_ratio')}",
        f"- Average / Max Total Queue Depth: {backlog.get('average_total_depth')} / {backlog.get('max_total_depth')}",
        f"- Queue Pressure Status Counts: {json.dumps(backlog.get('queue_pressure_status_counts', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "## Topology Profiles",
        "",
        f"- Heavy Analysis Isolated: {topology_profiles.get('heavy_analysis_isolated')}",
        "",
        "| Profile | Queues | Queue Pressure Counts |",
        "| --- | --- | --- |",
    ]
    for profile_name, profile_payload in sorted(configured_profiles.items()):
        if not isinstance(profile_payload, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    profile_name,
                    ", ".join(profile_payload.get("queues", [])) or "-",
                    json.dumps(profile_pressure_counts.get(profile_name, {}), ensure_ascii=False, sort_keys=True),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Worker Utilization",
            "",
            f"- Overall Average Active Utilization Ratio: {overall_utilization.get('average_active_utilization_ratio')}",
            f"- Overall Peak Active Utilization Ratio: {overall_utilization.get('peak_active_utilization_ratio')}",
            f"- Average Active / Reserved / Scheduled Tasks: {overall_utilization.get('average_active_tasks')} / {overall_utilization.get('average_reserved_tasks')} / {overall_utilization.get('average_scheduled_tasks')}",
            "",
            "| Profile | Workers Seen | Avg Utilization | Peak Utilization | Avg Active Tasks | Avg Concurrency |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for profile_name, profile_payload in sorted(profile_utilization.items()):
        if not isinstance(profile_payload, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    profile_name,
                    ", ".join(profile_payload.get("workers_seen", [])) or "-",
                    str(profile_payload.get("average_active_utilization_ratio")),
                    str(profile_payload.get("peak_active_utilization_ratio")),
                    str(profile_payload.get("average_active_tasks")),
                    str(profile_payload.get("average_estimated_concurrency")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Alerts",
            "",
            f"- Samples With Alerts: {alerts.get('samples_with_alerts')}",
            f"- Alert Code Counts: {json.dumps(alert_code_counts, ensure_ascii=False, sort_keys=True)}",
        ]
    )
    return "\n".join(lines) + "\n"
def write_distributed_benchmark_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / "benchmark-report.json"
    markdown_path = resolved_output_dir / "benchmark-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_benchmark_report_markdown(report), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
def _collect_runtime_sample(
    client: httpx.Client,
    *,
    now_factory: Callable[[], datetime],
) -> BenchmarkRuntimeSample:
    captured_at = now_factory()
    try:
        response = client.get("/health/metrics")
        payload = _safe_response_payload(response)
        sample_payload = payload if isinstance(payload, dict) else {"raw_payload": payload}
        return BenchmarkRuntimeSample(
            captured_at=captured_at,
            http_status=response.status_code,
            payload=sample_payload,
        )
    except Exception as exc:  # pragma: no cover - runtime HTTP/network path
        return BenchmarkRuntimeSample(
            captured_at=captured_at,
            http_status=None,
            payload={
                "status": "error",
                "error": str(exc),
            },
        )
def _fetch_audit_diagnostics(client: httpx.Client, audit_id: str) -> dict[str, Any] | None:
    try:
        response = client.get(f"/audits/{audit_id}/events/diagnostics")
    except Exception:  # pragma: no cover - runtime HTTP/network path
        return None
    payload = _safe_response_payload(response)
    if response.status_code != 200 or not isinstance(payload, dict):
        return None
    return payload
def _build_admission_summary(
    audit_records: Sequence[BenchmarkAuditRecord],
    duration_seconds: float,
    *,
    requested_count: int,
) -> dict[str, Any]:
    accepted = sum(1 for record in audit_records if record.admission_status == "accepted")
    rejected = sum(1 for record in audit_records if record.admission_status == "rejected")
    errors = sum(1 for record in audit_records if record.admission_status == "error")
    return {
        "requested": requested_count,
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors,
        "acceptance_rate": _safe_ratio(accepted, requested_count),
        "rejection_rate": _safe_ratio(rejected, requested_count),
        "accepted_per_minute": _per_minute_rate(accepted, duration_seconds),
    }
def _build_audit_summary(
    audit_records: Sequence[BenchmarkAuditRecord],
    duration_seconds: float,
) -> dict[str, Any]:
    terminal_status_counts = Counter(
        record.terminal_status or record.admission_status
        for record in audit_records
        if (record.terminal_status or record.admission_status)
    )
    latency_values = [
        float(record.total_duration_ms)
        for record in audit_records
        if isinstance(record.total_duration_ms, (int, float))
    ]
    successful_terminal_count = sum(
        1
        for record in audit_records
        if record.terminal_status in {"completed", "completed_with_warnings"}
    )
    terminal_count = sum(
        1
        for record in audit_records
        if record.terminal_status in TERMINAL_STATUSES or record.terminal_status == "timeout"
    )
    accepted_count = sum(1 for record in audit_records if record.admission_status == "accepted")
    return {
        "terminal_status_counts": dict(sorted(terminal_status_counts.items())),
        "latency_ms": _numeric_summary(latency_values),
        "throughput": {
            "accepted_per_minute": _per_minute_rate(accepted_count, duration_seconds),
            "terminal_per_minute": _per_minute_rate(terminal_count, duration_seconds),
            "successful_terminal_per_minute": _per_minute_rate(successful_terminal_count, duration_seconds),
        },
    }
def _build_runtime_summary(runtime_samples: Sequence[BenchmarkRuntimeSample]) -> dict[str, Any]:
    status_counts = Counter()
    good_samples: list[BenchmarkRuntimeSample] = []
    for sample in runtime_samples:
        payload_status = str(sample.payload.get("status") or "unknown")
        status_counts[payload_status] += 1
        if sample.http_status == 200 and isinstance(sample.payload, dict):
            good_samples.append(sample)
    return {
        "sample_count": len(runtime_samples),
        "sample_error_count": len(runtime_samples) - len(good_samples),
        "status_counts": dict(sorted(status_counts.items())),
        "queue_backlog": _build_queue_backlog_summary(good_samples),
        "worker_utilization": _build_worker_utilization_summary(good_samples),
        "topology_profiles": _build_topology_profile_summary(good_samples),
        "alerts": _build_alert_summary(good_samples),
    }


def _build_topology_profile_summary(runtime_samples: Sequence[BenchmarkRuntimeSample]) -> dict[str, Any]:
    configured_profiles: dict[str, dict[str, Any]] = {}
    queue_profile_map: dict[str, str] = {}
    profile_pressure_counts: dict[str, Counter[str]] = defaultdict(Counter)
    heavy_analysis_isolated = False

    for sample in runtime_samples:
        worker_section = sample.payload.get("workers") if isinstance(sample.payload.get("workers"), dict) else {}
        topology_contract = worker_section.get("topology_contract") if isinstance(worker_section.get("topology_contract"), dict) else {}
        raw_profiles = topology_contract.get("profiles") if isinstance(topology_contract.get("profiles"), list) else []
        for raw_profile in raw_profiles:
            if not isinstance(raw_profile, dict):
                continue
            profile_name = str(raw_profile.get("name") or "").strip()
            queues = [str(queue_name) for queue_name in raw_profile.get("queues", []) if str(queue_name)] if isinstance(raw_profile.get("queues"), list) else []
            if not profile_name:
                continue
            configured_profiles[profile_name] = {
                "workload_class": raw_profile.get("workload_class"),
                "recommended_concurrency": raw_profile.get("recommended_concurrency"),
                "queues": sorted(queues),
            }
            for queue_name in queues:
                queue_profile_map[queue_name] = profile_name
            if profile_name == "heavy_analysis" and queues == ["audits.heavy_analysis"]:
                heavy_analysis_isolated = True

        queue_pressure = sample.payload.get("queue_pressure") if isinstance(sample.payload.get("queue_pressure"), dict) else {}
        queue_snapshots = queue_pressure.get("queues") if isinstance(queue_pressure.get("queues"), dict) else {}
        for queue_name, snapshot in queue_snapshots.items():
            if not isinstance(snapshot, dict):
                continue
            profile_name = queue_profile_map.get(str(queue_name), "unassigned")
            pressure_status = str(snapshot.get("pressure_status") or "unknown")
            profile_pressure_counts[profile_name][pressure_status] += 1

    return {
        "configured_profiles": {name: configured_profiles[name] for name in sorted(configured_profiles)},
        "queue_profile_map": dict(sorted(queue_profile_map.items())),
        "profile_queue_pressure_counts": {
            profile_name: dict(sorted(counter.items()))
            for profile_name, counter in sorted(profile_pressure_counts.items())
        },
        "heavy_analysis_isolated": heavy_analysis_isolated,
    }


def _build_queue_backlog_summary(runtime_samples: Sequence[BenchmarkRuntimeSample]) -> dict[str, Any]:
    total_depth_values: list[float] = []
    per_queue_max_depth: dict[str, float] = defaultdict(float)
    queue_pressure_status_counts: Counter[str] = Counter()
    per_queue_pressure_counts: dict[str, Counter[str]] = defaultdict(Counter)
    degraded_samples = 0
    max_backlogged_queue_count = 0
    max_stuck_queue_count = 0
    for sample in runtime_samples:
        broker_payload = sample.payload.get("broker") if isinstance(sample.payload.get("broker"), dict) else {}
        queue_pressure = sample.payload.get("queue_pressure") if isinstance(sample.payload.get("queue_pressure"), dict) else {}
        if isinstance(broker_payload.get("total_depth"), (int, float)):
            total_depth_values.append(float(broker_payload["total_depth"]))
        queue_depths = broker_payload.get("queue_depths") if isinstance(broker_payload.get("queue_depths"), dict) else {}
        for queue_name, depth in queue_depths.items():
            if isinstance(depth, (int, float)):
                per_queue_max_depth[str(queue_name)] = max(per_queue_max_depth[str(queue_name)], float(depth))
        if queue_pressure.get("status") == "degraded":
            degraded_samples += 1
        backlogged_queues = queue_pressure.get("backlogged_queues") if isinstance(queue_pressure.get("backlogged_queues"), list) else []
        stuck_queues = queue_pressure.get("stuck_queues") if isinstance(queue_pressure.get("stuck_queues"), list) else []
        max_backlogged_queue_count = max(max_backlogged_queue_count, len(backlogged_queues))
        max_stuck_queue_count = max(max_stuck_queue_count, len(stuck_queues))
        queue_snapshots = queue_pressure.get("queues") if isinstance(queue_pressure.get("queues"), dict) else {}
        for queue_name, snapshot in queue_snapshots.items():
            if not isinstance(snapshot, dict):
                continue
            pressure_status = str(snapshot.get("pressure_status") or "unknown")
            queue_pressure_status_counts[pressure_status] += 1
            per_queue_pressure_counts[str(queue_name)][pressure_status] += 1
    return {
        "average_total_depth": _round_or_none(_average(total_depth_values)),
        "max_total_depth": _round_or_none(max(total_depth_values) if total_depth_values else None),
        "degraded_sample_ratio": _safe_ratio(degraded_samples, len(runtime_samples)),
        "max_backlogged_queue_count": max_backlogged_queue_count,
        "max_stuck_queue_count": max_stuck_queue_count,
        "per_queue_max_depth": {queue_name: _round_or_none(depth) for queue_name, depth in sorted(per_queue_max_depth.items())},
        "queue_pressure_status_counts": dict(sorted(queue_pressure_status_counts.items())),
        "per_queue_pressure_counts": {
            queue_name: dict(sorted(counter.items()))
            for queue_name, counter in sorted(per_queue_pressure_counts.items())
        },
    }
def _build_worker_utilization_summary(runtime_samples: Sequence[BenchmarkRuntimeSample]) -> dict[str, Any]:
    overall_active_tasks: list[float] = []
    overall_reserved_tasks: list[float] = []
    overall_scheduled_tasks: list[float] = []
    overall_concurrency: list[float] = []
    overall_active_utilization: list[float] = []
    workers_seen: set[str] = set()
    profile_active_tasks: dict[str, list[float]] = defaultdict(list)
    profile_concurrency: dict[str, list[float]] = defaultdict(list)
    profile_utilization: dict[str, list[float]] = defaultdict(list)
    profile_workers_seen: dict[str, set[str]] = defaultdict(set)
    for sample in runtime_samples:
        worker_section = sample.payload.get("workers") if isinstance(sample.payload.get("workers"), dict) else {}
        workers_payload = worker_section.get("workers") if isinstance(worker_section.get("workers"), dict) else {}
        if not workers_payload:
            continue
        sample_active_total = 0
        sample_reserved_total = 0
        sample_scheduled_total = 0
        sample_concurrency_total = 0
        profile_active_totals: dict[str, int] = defaultdict(int)
        profile_concurrency_totals: dict[str, int] = defaultdict(int)
        for worker_name, worker_payload in workers_payload.items():
            if not isinstance(worker_payload, dict):
                continue
            workers_seen.add(str(worker_name))
            profile_name = str(worker_payload.get("profile_name") or "unassigned")
            profile_workers_seen[profile_name].add(str(worker_name))
            active_tasks = int(worker_payload.get("active_tasks") or 0)
            reserved_tasks = int(worker_payload.get("reserved_tasks") or 0)
            scheduled_tasks = int(worker_payload.get("scheduled_tasks") or 0)
            queues = worker_payload.get("queues") if isinstance(worker_payload.get("queues"), list) else []
            estimated_concurrency = int(worker_payload.get("pool_max_concurrency") or (1 if queues else 0))
            sample_active_total += active_tasks
            sample_reserved_total += reserved_tasks
            sample_scheduled_total += scheduled_tasks
            sample_concurrency_total += estimated_concurrency
            profile_active_totals[profile_name] += active_tasks
            profile_concurrency_totals[profile_name] += estimated_concurrency
        overall_active_tasks.append(float(sample_active_total))
        overall_reserved_tasks.append(float(sample_reserved_total))
        overall_scheduled_tasks.append(float(sample_scheduled_total))
        overall_concurrency.append(float(sample_concurrency_total))
        if sample_concurrency_total > 0:
            overall_active_utilization.append(sample_active_total / sample_concurrency_total)
        for profile_name, active_total in profile_active_totals.items():
            estimated_concurrency = profile_concurrency_totals[profile_name]
            profile_active_tasks[profile_name].append(float(active_total))
            profile_concurrency[profile_name].append(float(estimated_concurrency))
            if estimated_concurrency > 0:
                profile_utilization[profile_name].append(active_total / estimated_concurrency)
    by_profile = {
        profile_name: {
            "workers_seen": sorted(profile_workers_seen.get(profile_name, set())),
            "sample_count": len(profile_active_tasks.get(profile_name, [])),
            "average_active_tasks": _round_or_none(_average(profile_active_tasks.get(profile_name, []))),
            "average_estimated_concurrency": _round_or_none(_average(profile_concurrency.get(profile_name, []))),
            "average_active_utilization_ratio": _round_or_none(_average(profile_utilization.get(profile_name, []))),
            "peak_active_utilization_ratio": _round_or_none(max(profile_utilization.get(profile_name, []) or [0.0])),
        }
        for profile_name in sorted(profile_active_tasks.keys() | profile_workers_seen.keys())
    }
    return {
        "overall": {
            "workers_seen": sorted(workers_seen),
            "average_active_tasks": _round_or_none(_average(overall_active_tasks)),
            "average_reserved_tasks": _round_or_none(_average(overall_reserved_tasks)),
            "average_scheduled_tasks": _round_or_none(_average(overall_scheduled_tasks)),
            "average_estimated_concurrency": _round_or_none(_average(overall_concurrency)),
            "average_active_utilization_ratio": _round_or_none(_average(overall_active_utilization)),
            "peak_active_utilization_ratio": _round_or_none(max(overall_active_utilization) if overall_active_utilization else None),
        },
        "by_profile": by_profile,
    }
def _build_alert_summary(runtime_samples: Sequence[BenchmarkRuntimeSample]) -> dict[str, Any]:
    alert_code_counts: Counter[str] = Counter()
    samples_with_alerts = 0
    for sample in runtime_samples:
        detector_payload = sample.payload.get("execution_detector") if isinstance(sample.payload.get("execution_detector"), dict) else {}
        alerts = detector_payload.get("alerts") if isinstance(detector_payload.get("alerts"), list) else []
        if alerts:
            samples_with_alerts += 1
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            code = str(alert.get("code") or "unknown")
            alert_code_counts[code] += 1
    return {
        "samples_with_alerts": samples_with_alerts,
        "alert_code_counts": dict(sorted(alert_code_counts.items())),
    }
def _safe_response_payload(response: httpx.Response) -> dict[str, Any] | str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()
    return payload if isinstance(payload, dict) else json.dumps(payload, ensure_ascii=False)
def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.isoformat()
def _utc_now() -> datetime:
    return datetime.now(UTC)
def _average(values: Sequence[float]) -> float | None:
    return (sum(values) / len(values)) if values else None
def _numeric_summary(values: Sequence[float]) -> dict[str, Any]:
    numeric_values = sorted(float(value) for value in values)
    return {
        "count": len(numeric_values),
        "min": _round_or_none(min(numeric_values) if numeric_values else None),
        "average": _round_or_none(_average(numeric_values)),
        "p50": _percentile(numeric_values, 50.0),
        "p95": _percentile(numeric_values, 95.0),
        "max": _round_or_none(max(numeric_values) if numeric_values else None),
    }
def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return _round_or_none(values[0])
    rank = (len(values) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return _round_or_none(values[lower])
    interpolation = values[lower] + (values[upper] - values[lower]) * (rank - lower)
    return _round_or_none(interpolation)
def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 4)
def _per_minute_rate(count: int, duration_seconds: float) -> float | None:
    if duration_seconds <= 0:
        return None
    return round(count / (duration_seconds / 60.0), 2)
def _round_or_none(value: float | None) -> float | None:
    return round(float(value), 2) if value is not None else None
