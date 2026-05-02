import { describe, expect, it } from "vitest";
import { getApiErrorMessage } from "./api";

describe("getApiErrorMessage", () => {
  it("uses structured backend detail messages", () => {
    expect(
      getApiErrorMessage(
        {
          detail: {
            code: "pipeline_queue_capacity_exhausted",
            message: "Невозможно запустить новый аудит: очередь pipeline перегружена или не обслуживается worker'ами.",
            queue_name: "audits.pipeline",
            details: {
              worker_count: 0,
            },
          },
        },
        503,
      ),
    ).toContain("Проверьте состояние стека и запустите профиль оркестратора");
  });

  it("keeps plain detail strings", () => {
    expect(getApiErrorMessage({ detail: "Некорректный URL" }, 422)).toBe("Некорректный URL");
  });
});

describe("auditsApi", () => {
  it("requests timeline diagnostics from the audit events endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            audit_id: "audit-1",
            processing_version: 1,
            status: "completed",
            event_count: 0,
            dispatch_count: 0,
            started_at: null,
            finished_at: null,
            total_duration_ms: null,
            terminal_stage: null,
            terminal_event: null,
            critical_path_duration_ms: null,
            critical_path_stages: [],
            stage_breakdown: [],
            fan_out: null,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { auditsApi } = await import("./api");
      const diagnostics = await auditsApi.getTimelineDiagnostics("audit-1");
      expect(diagnostics.audit_id).toBe("audit-1");
      expect(calls[0]).toContain("/audits/audit-1/events/diagnostics");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("requests raw timeline events from the audit events endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            audit_id: "audit-1",
            processing_version: 1,
            events: [
              {
                id: 1,
                audit_id: "audit-1",
                processing_version: 1,
                stage: "pipeline",
                event: "started",
                duration_ms: null,
                details: null,
                created_at: "2026-01-01T10:00:00",
              },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { auditsApi } = await import("./api");
      const timeline = await auditsApi.getTimelineEvents("audit-1");
      expect(timeline.events).toHaveLength(1);
      expect(calls[0]).toContain("/audits/audit-1/events");
      expect(calls[0]).not.toContain("/events/diagnostics");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

describe("runtimeApi", () => {
  it("accepts not-ready readiness responses as runtime state payloads", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "not_ready",
            app_name: "site-audit",
            environment: "local",
            checked_at: "2026-01-01T10:00:00Z",
            checks: {},
            orchestration: {
              expected_queues: [],
              broker_url: "redis://localhost:6379/0",
              result_backend: "redis://localhost:6379/0",
              worker_topology: { profiles: [], expected_queues: [] },
            },
          }),
          { status: 503, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { runtimeApi } = await import("./api");
      const readiness = await runtimeApi.getReadiness();
      expect(readiness.status).toBe("not_ready");
      expect(calls[0]).toContain("/health/ready");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("requests runtime metrics from the health metrics endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "ok",
            app_name: "site-audit",
            environment: "local",
            checked_at: "2026-01-01T10:00:00Z",
            orchestration: {
              expected_queues: [],
              broker_url: "redis://localhost:6379/0",
              result_backend: "redis://localhost:6379/0",
              worker_topology: { profiles: [], expected_queues: [] },
            },
            database: { status: "ok" },
            broker: { status: "ok", queue_depths: {}, total_depth: 0 },
            workers: { status: "ok", online_count: 0, workers: {}, missing_queues: [], queue_activity: {} },
            queue_pressure: { status: "ok", queues: {}, backlogged_queues: [], stuck_queues: [] },
            execution_detector: { status: "ok", alerts: [], summary: { alert_count: 0 } },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { runtimeApi } = await import("./api");
      const metrics = await runtimeApi.getMetrics();
      expect(metrics.status).toBe("ok");
      expect(calls[0]).toContain("/health/metrics");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("requests active model status from the health model endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "active",
            checked_at: "2026-05-01T20:05:00Z",
            artifact_path: "artifacts/page_quality_model.pkl",
            artifact_sha1: "abc123",
            metadata_path: "artifacts/page_quality_model.metadata.json",
            metadata_sha1: "def456",
            model: {
              model_type: "CatBoostRegressor",
              model_schema_version: "v3",
              feature_count: 148,
              artifact_version: "dataset-v3-d37-20260501200434",
            },
            dataset: {
              dataset_version: "dataset-v3-d37",
              rows_count: 885,
              queries_count: 99,
            },
            metrics_summary: {
              top_3_hit_rate: 0.95,
              ndcg_at_10: 0.945929,
              mae: 11.774165,
            },
            publish: {
              selected_candidate: "pointwise_catboost",
              publish_recommendation: "publish_candidate",
            },
            rollback: {
              available: true,
              model_sha1: "rollback-sha",
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { runtimeApi } = await import("./api");
      const modelStatus = await runtimeApi.getModelStatus();
      expect(modelStatus.status).toBe("active");
      expect(calls[0]).toContain("/health/model");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("requests model registry from the health model registry endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "ok",
            checked_at: "2026-05-02T00:00:00Z",
            artifact_family: "page_quality_model",
            active_artifact_sha1: "active-sha",
            rollback_artifact_sha1: "rollback-sha",
            summary: {
              record_count: 2,
              current_count: 1,
              rollback_count: 1,
              archived_count: 0,
              warning_count: 0,
            },
            records: [],
            rollback_check: {
              status: "ok",
              dry_run_only: true,
              checklist: [],
              warnings: [],
            },
            invariants: {
              does_not_execute_rollback: true,
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { runtimeApi } = await import("./api");
      const registry = await runtimeApi.getModelRegistry();
      expect(registry.artifact_family).toBe("page_quality_model");
      expect(calls[0]).toContain("/health/model/registry");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("requests model monitoring from the health model monitoring endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "ok",
            checked_at: "2026-05-02T00:00:00Z",
            window_days: 30,
            window_start: "2026-04-02T00:00:00Z",
            window_end: "2026-05-02T00:00:00Z",
            total_audits: 1,
            audits_with_model_info: 1,
            legacy_or_unknown_count: 0,
            status_counts: { completed: 1 },
            warning_count: 0,
            warning_message_count: 0,
            failure_count: 0,
            active_model: {
              artifact_version: "dataset-v3-d37-20260501200434",
              model_schema_version: "v3",
              dataset_version: "dataset-v3-d37",
            },
            score_distribution: {
              sample_size: 1,
              average: 72,
              min: 72,
              max: 72,
              p25: 72,
              p50: 72,
              p75: 72,
              low_score_count: 0,
              high_score_count: 0,
              low_score_threshold: 50,
              high_score_threshold: 80,
            },
            competitor_coverage: {
              sample_size: 1,
              total_found: 2,
              total_analyzed: 2,
              total_failed: 0,
              average_found: 2,
              average_analyzed: 2,
              average_failed: 0,
              coverage_ratio: 1,
            },
            model_usage: [],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    }) as typeof fetch;

    try {
      const { runtimeApi } = await import("./api");
      const monitoring = await runtimeApi.getModelMonitoring();
      expect(monitoring.status).toBe("ok");
      expect(calls[0]).toContain("/health/model/monitoring");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
