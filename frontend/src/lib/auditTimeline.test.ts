import { describe, expect, it } from "vitest";
import type {
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  FailureContext,
} from "../types";
import { buildAuditTimelineModel, normalizeTimelineStage } from "./auditTimeline";

function createAudit(overrides: Partial<AuditStatusResponse> = {}): AuditStatusResponse {
  return {
    id: "audit-1",
    query: "seo audit",
    target_url: "https://example.com",
    top_n: 10,
    status: "completed",
    created_at: "2026-01-01T10:00:00",
    updated_at: null,
    extracted_text: null,
    feature_schema_version: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score: 72,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    recommendations: null,
    target_fetch_status: "success",
    target_fetch_method: "http",
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
    ...overrides,
  };
}

function createResults(overrides: Partial<AuditResultsResponse> = {}): AuditResultsResponse {
  return {
    audit_id: "audit-1",
    status: "completed",
    score: 72,
    extracted_text: null,
    feature_schema_version: null,
    target_snapshot_summary: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    target_fetch_status: "success",
    target_fetch_method: "http",
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
    ...overrides,
  };
}

function createDiagnostics(overrides: Partial<AuditTimelineDiagnosticsResponse> = {}): AuditTimelineDiagnosticsResponse {
  return {
    audit_id: "audit-1",
    processing_version: 1,
    status: "completed",
    event_count: 8,
    dispatch_count: 3,
    started_at: "2026-01-01T10:00:00",
    finished_at: "2026-01-01T10:00:08",
    total_duration_ms: 8_000,
    terminal_stage: "pipeline",
    terminal_event: "completed",
    critical_path_duration_ms: 7_000,
    critical_path_stages: [
      {
        stage: "heavy_analysis",
        contribution_duration_ms: 3_000,
        mode: "serial_sum",
        terminal_count: 1,
      },
      {
        stage: "competitor_analysis",
        contribution_duration_ms: 4_000,
        mode: "fan_out_max",
        terminal_count: 2,
      },
    ],
    stage_breakdown: [
      {
        stage: "heavy_analysis",
        dispatch_count: 1,
        started_count: 1,
        completed_count: 1,
        failed_count: 0,
        aborted_count: 0,
        terminal_count: 1,
        total_duration_ms: 3_000,
        average_duration_ms: 3_000,
        max_duration_ms: 3_000,
        critical_path_mode: "serial_sum",
        critical_path_duration_ms: 3_000,
        first_event_at: "2026-01-01T10:00:01",
        last_event_at: "2026-01-01T10:00:04",
        latest_event: "completed",
      },
      {
        stage: "competitor_analysis",
        dispatch_count: 2,
        started_count: 2,
        completed_count: 2,
        failed_count: 0,
        aborted_count: 0,
        terminal_count: 2,
        total_duration_ms: 6_000,
        average_duration_ms: 3_000,
        max_duration_ms: 4_000,
        critical_path_mode: "fan_out_max",
        critical_path_duration_ms: 4_000,
        first_event_at: "2026-01-01T10:00:04",
        last_event_at: "2026-01-01T10:00:08",
        latest_event: "completed",
      },
    ],
    fan_out: {
      stage: "competitor_analysis",
      dispatch_count: 2,
      started_count: 2,
      terminal_count: 2,
      in_flight_count: 0,
      total_duration_ms: 6_000,
      average_duration_ms: 3_000,
      max_duration_ms: 4_000,
      critical_path_duration_ms: 4_000,
    },
    ...overrides,
  };
}

function createEvents(overrides: Partial<AuditTimelineEventsResponse> = {}): AuditTimelineEventsResponse {
  return {
    audit_id: "audit-1",
    processing_version: 1,
    events: [
      {
        id: 1,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "app.process_audit_run_heavy_analysis",
        event: "dispatched",
        duration_ms: null,
        details: { queue: "audits.heavy_analysis" },
        created_at: "2026-01-01T10:00:01",
      },
      {
        id: 2,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "heavy_analysis",
        event: "completed",
        duration_ms: 3_000,
        details: { status: "success", overall_score: 72, risk_level: "medium", duration_ms: 3_000 },
        created_at: "2026-01-01T10:00:04",
      },
      {
        id: 3,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "competitor_analysis",
        event: "dispatched",
        duration_ms: null,
        details: { queue: "audits.competitor_analysis", domain: "competitor.example" },
        created_at: "2026-01-01T10:00:04",
      },
      {
        id: 4,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "competitor_analysis",
        event: "completed",
        duration_ms: 4_000,
        details: { domain: "competitor.example", score: 80 },
        created_at: "2026-01-01T10:00:08",
      },
    ],
    ...overrides,
  };
}

describe("audit timeline model", () => {
  it("normalizes backend task names to logical stage names", () => {
    expect(normalizeTimelineStage("app.process_audit_run_heavy_analysis")).toBe("heavy_analysis");
    expect(normalizeTimelineStage("app.process_audit_analyze_competitor_page")).toBe("competitor_analysis");
  });

  it("orders stages, keeps queue evidence and marks critical-path contribution stages", () => {
    const model = buildAuditTimelineModel({
      audit: createAudit(),
      results: createResults(),
      diagnostics: createDiagnostics(),
      events: createEvents(),
      failureContext: null,
    });

    const stageNames = model.stageRows.map((stage) => stage.stage);
    expect(stageNames.indexOf("heavy_analysis")).toBeLessThan(stageNames.indexOf("competitor_analysis"));
    expect(model.summaryMetrics.find((metric) => metric.label === "Критический путь")?.value).toBe("7 с");
    expect(model.summaryMetrics.find((metric) => metric.label === "Критический путь")?.note).toContain("Оценка");

    const heavyAnalysis = model.stageRows.find((stage) => stage.stage === "heavy_analysis");
    expect(heavyAnalysis?.queueLabel).toBe("audits.heavy_analysis");
    expect(heavyAnalysis?.status).toBe("completed");
    expect(heavyAnalysis?.isCriticalPath).toBe(true);

    const heavyAnalysisEvent = model.eventRows.find((event) => event.id === 2);
    expect(heavyAnalysisEvent?.detailSummary).toContain("Статус: успешно");
    expect(heavyAnalysisEvent?.detailSummary).toContain("Риск: средний");
    expect(heavyAnalysisEvent?.detailSummary).not.toContain("duration_ms");
  });

  it("summarizes fan-out with max branch duration", () => {
    const model = buildAuditTimelineModel({
      audit: createAudit(),
      results: createResults(),
      diagnostics: createDiagnostics(),
      events: createEvents(),
      failureContext: null,
    });

    expect(model.fanOut?.stage).toBe("competitor_analysis");
    expect(model.fanOutStages).toHaveLength(1);
    expect(model.fanOut?.branchCount).toBe(2);
    expect(model.fanOut?.maxDurationLabel).toBe("4 с");
    expect(model.fanOut?.note).toContain("свободных worker-процессов");
  });

  it("surfaces every observed fan-out stage when diagnostics names only one", () => {
    const baseDiagnostics = createDiagnostics();
    const baseEvents = createEvents();
    const model = buildAuditTimelineModel({
      audit: createAudit(),
      results: createResults(),
      diagnostics: createDiagnostics({
        fan_out: {
          stage: "competitor_page",
          dispatch_count: 2,
          started_count: 2,
          terminal_count: 2,
          in_flight_count: 0,
          total_duration_ms: 5_000,
          average_duration_ms: 2_500,
          max_duration_ms: 3_000,
          critical_path_duration_ms: 3_000,
        },
        stage_breakdown: [
          ...baseDiagnostics.stage_breakdown,
          {
            stage: "competitor_page",
            dispatch_count: 2,
            started_count: 2,
            completed_count: 2,
            failed_count: 0,
            aborted_count: 0,
            terminal_count: 2,
            total_duration_ms: 5_000,
            average_duration_ms: 2_500,
            max_duration_ms: 3_000,
            critical_path_mode: "fan_out_max",
            critical_path_duration_ms: 3_000,
            first_event_at: "2026-01-01T10:00:03",
            last_event_at: "2026-01-01T10:00:07",
            latest_event: "completed",
          },
        ],
      }),
      events: createEvents({
        events: [
          {
            id: 5,
            audit_id: "audit-1",
            processing_version: 1,
            stage: "competitor_page",
            event: "dispatched",
            duration_ms: null,
            details: { queue: "audits.competitor_pages" },
            created_at: "2026-01-01T10:00:03",
          },
          ...baseEvents.events,
        ],
      }),
      failureContext: null,
    });

    expect(model.fanOutStages.map((fanOut) => fanOut.stage)).toEqual(["competitor_page", "competitor_analysis"]);
  });

  it("surfaces warnings and failed stage context", () => {
    const failureContext: FailureContext = {
      stage: "fetch",
      code: "http_403",
      message: "HTTP 403",
      details: { fetch_method: "browser", http_status: 403 },
    };
    const diagnostics = createDiagnostics({
      status: "failed",
      stage_breakdown: [
        {
          stage: "fetch",
          dispatch_count: 1,
          started_count: 1,
          completed_count: 0,
          failed_count: 1,
          aborted_count: 0,
          terminal_count: 1,
          total_duration_ms: 120,
          average_duration_ms: 120,
          max_duration_ms: 120,
          critical_path_mode: "serial_sum",
          critical_path_duration_ms: 120,
          first_event_at: "2026-01-01T10:00:01",
          last_event_at: "2026-01-01T10:00:02",
          latest_event: "failed",
        },
      ],
      fan_out: null,
    });
    const model = buildAuditTimelineModel({
      audit: createAudit({ status: "failed", warnings: ["Target fetch degraded"] }),
      results: createResults({ status: "failed", warnings: ["Target fetch degraded"] }),
      diagnostics,
      events: createEvents({ events: [] }),
      failureContext,
    });

    expect(model.warnings).toEqual(["Target fetch degraded"]);
    expect(model.failure?.message).toBe("HTTP 403");
    expect(model.stageRows.find((stage) => stage.stage === "fetch")?.status).toBe("failed");
  });

  it("surfaces query relevance early stop diagnostics without competitor fan-out", () => {
    const earlyStop = {
      schema_version: "early-stop-summary-v1",
      active: true,
      type: "query_relevance_full_mismatch",
      reason: "confident_full_query_mismatch",
      status: "completed",
      title: "Страница не соответствует запросу",
      message: "Сравнение с конкурентами не запускалось, потому что страница не отвечает теме запроса.",
      score: 3,
      score_floor: 0,
      score_ceiling: 5,
      score_basis: "query_relevance_early_stop",
      safe_to_skip_competitors: true,
      skipped_stages: ["heavy_analysis", "competitors"],
      competitor_processing_status: "skipped_early_stop",
    };
    const model = buildAuditTimelineModel({
      audit: createAudit({ score: 3, early_stop: earlyStop }),
      results: createResults({ score: 3, early_stop: earlyStop }),
      diagnostics: createDiagnostics({
        critical_path_stages: [],
        stage_breakdown: [
          {
            stage: "features",
            dispatch_count: 0,
            started_count: 1,
            completed_count: 0,
            failed_count: 0,
            aborted_count: 0,
            terminal_count: 0,
            total_duration_ms: null,
            average_duration_ms: null,
            max_duration_ms: null,
            critical_path_mode: "serial_sum",
            critical_path_duration_ms: null,
            first_event_at: "2026-01-01T10:00:01",
            last_event_at: "2026-01-01T10:00:01",
            latest_event: "preflight_stop",
          },
        ],
        fan_out: null,
        early_stop: earlyStop,
      }),
      events: createEvents({
        events: [
          {
            id: 10,
            audit_id: "audit-1",
            processing_version: 1,
            stage: "features",
            event: "preflight_stop",
            duration_ms: null,
            details: {
              early_stop: true,
              score_ceiling: 5,
              safe_to_skip_competitors: true,
              skipped_stages: ["heavy_analysis", "competitors"],
            },
            created_at: "2026-01-01T10:00:01",
          },
        ],
      }),
      failureContext: null,
    });

    expect(model.earlyStop?.title).toBe("Страница не соответствует запросу");
    expect(model.fanOutStages).toEqual([]);
    expect(model.summaryMetrics.find((metric) => metric.label === "Остановка аудита")?.value).toBe("До конкурентов");
    expect(model.eventRows[0]?.eventLabel).toBe("Остановлено по соответствию запросу");
    expect(model.eventRows[0]?.detailSummary).toContain("Пропущенные этапы: heavy_analysis, competitors");
  });
});
