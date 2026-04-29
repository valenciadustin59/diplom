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
});
