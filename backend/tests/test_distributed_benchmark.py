from datetime import UTC, datetime, timedelta
import json
import httpx
from app.distributed_benchmark import (
    BenchmarkAuditRecord,
    BenchmarkRuntimeSample,
    BenchmarkWorkloadEntry,
    DistributedBenchmarkConfig,
    build_distributed_benchmark_report,
    load_benchmark_workload,
    render_benchmark_report_markdown,
    run_distributed_benchmark,
    write_distributed_benchmark_report,
)
class FakeClock:
    def __init__(self, start: datetime):
        self.current = start
        self.monotonic_value = 0.0
    def now(self) -> datetime:
        self.current += timedelta(milliseconds=100)
        return self.current
    def monotonic(self) -> float:
        self.monotonic_value += 0.05
        return self.monotonic_value
def _build_runtime_metrics_payload(
    *,
    total_depth: int,
    network_active_tasks: int,
    network_reserved_tasks: int = 0,
    pressure_status: str = "draining",
    alert_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    queue_pressure_status = "degraded" if pressure_status in {"backlogged", "stuck"} else "ok"
    return {
        "status": "degraded" if alert_codes or queue_pressure_status == "degraded" else "ok",
        "broker": {
            "status": "ok",
            "total_depth": total_depth,
            "queue_depths": {
                "audits.pipeline": max(total_depth - 1, 0),
                "audits.fetch": 1,
                "audits.features": 0,
                "audits.scoring": 0,
                "audits.competitors": 0,
                "audits.competitor_pages": 0,
                "audits.recommendations": 0,
                "audits.finalize": 0,
            },
        },
        "workers": {
            "status": "ok",
            "online_count": 3,
            "active_tasks_total": 1 + network_active_tasks,
            "reserved_tasks_total": network_reserved_tasks,
            "scheduled_tasks_total": 0,
            "workers": {
                "pipeline@test": {
                    "profile_name": "pipeline",
                    "queues": ["audits.pipeline"],
                    "active_tasks": 1,
                    "reserved_tasks": 0,
                    "scheduled_tasks": 0,
                    "pool_max_concurrency": 1,
                    "pid": 1001,
                },
                "network@test": {
                    "profile_name": "network",
                    "queues": ["audits.fetch", "audits.competitors", "audits.competitor_pages"],
                    "active_tasks": network_active_tasks,
                    "reserved_tasks": network_reserved_tasks,
                    "scheduled_tasks": 0,
                    "pool_max_concurrency": 4,
                    "pid": 1002,
                },
                "cpu@test": {
                    "profile_name": "cpu_ml",
                    "queues": ["audits.features", "audits.scoring", "audits.recommendations", "audits.finalize"],
                    "active_tasks": 0,
                    "reserved_tasks": 0,
                    "scheduled_tasks": 0,
                    "pool_max_concurrency": 2,
                    "pid": 1003,
                },
            },
        },
        "queue_pressure": {
            "status": queue_pressure_status,
            "backlogged_queues": ["audits.fetch"] if pressure_status == "backlogged" else [],
            "stuck_queues": ["audits.fetch"] if pressure_status == "stuck" else [],
            "queues": {
                "audits.fetch": {
                    "depth": 1,
                    "pressure_status": pressure_status,
                    "worker_count": 1,
                    "estimated_concurrency": 4,
                    "active_tasks": network_active_tasks,
                    "reserved_tasks": network_reserved_tasks,
                    "scheduled_tasks": 0,
                    "inflight_tasks": network_active_tasks + network_reserved_tasks,
                    "available_capacity_estimate": max(4 - network_active_tasks, 0),
                    "reasons": [pressure_status],
                }
            },
        },
        "execution_detector": {
            "status": "degraded" if alert_codes else "ok",
            "alerts": [{"code": code} for code in alert_codes],
        },
    }
def test_load_benchmark_workload_accepts_object_payload(tmp_path):
    workload_path = tmp_path / "workload.json"
    workload_path.write_text(
        json.dumps(
            {
                "audits": [
                    {
                        "label": "audit-a",
                        "query": "seo audit",
                        "target_url": "https://example.com/",
                        "top_n": 5,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workload = load_benchmark_workload(workload_path)
    assert len(workload) == 1
    assert workload[0].label == "audit-a"
    assert workload[0].to_request_payload()["top_n"] == 5
def test_build_distributed_benchmark_report_summarizes_runtime_metrics_and_writes_report(tmp_path):
    started_at = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    finished_at = started_at + timedelta(seconds=30)
    workload = (
        BenchmarkWorkloadEntry(label="accepted", query="seo audit", target_url="https://example.com/", top_n=5),
        BenchmarkWorkloadEntry(label="rejected", query="landing page", target_url="https://example.com/", top_n=5),
    )
    records = [
        BenchmarkAuditRecord(
            label="accepted",
            request_payload=workload[0].to_request_payload(),
            admission_status="accepted",
            create_http_status=201,
            create_latency_ms=45.0,
            audit_id="audit-1",
            created_at=started_at,
            completed_at=started_at + timedelta(seconds=4),
            terminal_status="completed",
            last_status="completed",
            total_duration_ms=4200.0,
        ),
        BenchmarkAuditRecord(
            label="rejected",
            request_payload=workload[1].to_request_payload(),
            admission_status="rejected",
            create_http_status=503,
            create_latency_ms=20.0,
            details={"code": "pipeline_queue_capacity_exhausted"},
        ),
    ]
    samples = [
        BenchmarkRuntimeSample(
            captured_at=started_at + timedelta(seconds=1),
            http_status=200,
            payload=_build_runtime_metrics_payload(total_depth=3, network_active_tasks=2),
        ),
        BenchmarkRuntimeSample(
            captured_at=started_at + timedelta(seconds=3),
            http_status=200,
            payload=_build_runtime_metrics_payload(
                total_depth=8,
                network_active_tasks=3,
                network_reserved_tasks=1,
                pressure_status="backlogged",
                alert_codes=("queue_backlog_detected",),
            ),
        ),
    ]
    report = build_distributed_benchmark_report(
        base_url="http://127.0.0.1:8000",
        workload=workload,
        config=DistributedBenchmarkConfig(benchmark_name="d12-report-test"),
        audit_records=records,
        runtime_samples=samples,
        started_at=started_at,
        finished_at=finished_at,
    )
    assert report["admission"]["accepted"] == 1
    assert report["admission"]["rejected"] == 1
    assert report["audits"]["terminal_status_counts"] == {"completed": 1, "rejected": 1}
    assert report["audits"]["latency_ms"]["p95"] == 4200.0
    assert report["runtime"]["queue_backlog"]["max_total_depth"] == 8.0
    assert report["runtime"]["worker_utilization"]["by_profile"]["network"]["peak_active_utilization_ratio"] == 0.75
    assert report["runtime"]["alerts"]["alert_code_counts"] == {"queue_backlog_detected": 1}
    output_paths = write_distributed_benchmark_report(report, tmp_path / "report")
    markdown = render_benchmark_report_markdown(report)
    assert (tmp_path / "report" / "benchmark-report.json").exists()
    assert (tmp_path / "report" / "benchmark-report.md").exists()
    assert output_paths["json_path"].endswith("benchmark-report.json")
    assert "## Worker Utilization" in markdown
    assert "queue_backlog_detected" in markdown
def test_run_distributed_benchmark_collects_runtime_metrics_and_diagnostics():
    clock = FakeClock(datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    state = {
        "audit_poll_count": 0,
        "metrics_count": 0,
    }
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/audits":
            return httpx.Response(
                201,
                json={
                    "id": "audit-1",
                    "query": "seo audit",
                    "target_url": "https://example.com/",
                    "top_n": 5,
                    "status": "queued",
                    "created_at": "2026-04-22T12:00:00+00:00",
                    "updated_at": "2026-04-22T12:00:00+00:00",
                },
            )
        if request.method == "GET" and request.url.path == "/health/metrics":
            state["metrics_count"] += 1
            return httpx.Response(
                200,
                json=_build_runtime_metrics_payload(
                    total_depth=2 + state["metrics_count"],
                    network_active_tasks=min(state["metrics_count"], 3),
                ),
            )
        if request.method == "GET" and request.url.path == "/audits/audit-1":
            state["audit_poll_count"] += 1
            if state["audit_poll_count"] < 2:
                return httpx.Response(
                    200,
                    json={
                        "id": "audit-1",
                        "query": "seo audit",
                        "target_url": "https://example.com/",
                        "top_n": 5,
                        "status": "processing",
                        "created_at": "2026-04-22T12:00:00+00:00",
                        "updated_at": "2026-04-22T12:00:01+00:00",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "audit-1",
                    "query": "seo audit",
                    "target_url": "https://example.com/",
                    "top_n": 5,
                    "status": "completed",
                    "created_at": "2026-04-22T12:00:00+00:00",
                    "updated_at": "2026-04-22T12:00:05+00:00",
                },
            )
        if request.method == "GET" and request.url.path == "/audits/audit-1/events/diagnostics":
            return httpx.Response(
                200,
                json={
                    "audit_id": "audit-1",
                    "status": "completed",
                    "processing_version": 1,
                    "event_count": 12,
                    "dispatch_count": 8,
                    "started_at": "2026-04-22T12:00:00+00:00",
                    "finished_at": "2026-04-22T12:00:05+00:00",
                    "total_duration_ms": 4200.0,
                    "critical_path_duration_ms": 3900.0,
                    "critical_path_stages": [],
                    "stage_breakdown": [],
                    "fan_out": None,
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")
    workload = (
        BenchmarkWorkloadEntry(
            label="audit-1",
            query="seo audit",
            target_url="https://example.com/",
            top_n=5,
        ),
    )
    config = DistributedBenchmarkConfig(
        benchmark_name="d12-live-runner-test",
        max_inflight=1,
        poll_interval_seconds=0.01,
        metrics_interval_seconds=0.01,
        timeout_seconds=2.0,
        request_timeout_seconds=1.0,
    )
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://benchmark.test") as client:
        report = run_distributed_benchmark(
            client,
            workload,
            config,
            base_url="http://benchmark.test",
            monotonic=clock.monotonic,
            sleep=lambda _seconds: None,
            now_factory=clock.now,
        )
    assert report["benchmark_name"] == "d12-live-runner-test"
    assert report["admission"]["accepted"] == 1
    assert report["admission"]["rejected"] == 0
    assert report["audits"]["terminal_status_counts"] == {"completed": 1}
    assert report["audit_records"][0]["total_duration_ms"] == 4200.0
    assert report["runtime"]["sample_count"] >= 2
    assert state["metrics_count"] >= 2
