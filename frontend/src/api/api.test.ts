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
    ).toContain("Очередь audits.pipeline сейчас без активных воркеров");
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
});
