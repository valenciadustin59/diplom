import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuditWorkspace } from "../components/AuditWorkspace";
import { RecommendationsPage } from "../pages/RecommendationsPage";
import type {
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  FailureContext,
  RecommendationsBundle,
} from "../types";
import { resolveAuditFailureContext } from "./ui";

function createAudit(overrides: Partial<AuditStatusResponse> = {}): AuditStatusResponse {
  return {
    id: "audit-1",
    query: "seo audit",
    target_url: "https://example.com",
    top_n: 10,
    status: "queued",
    created_at: "2026-01-01T10:00:00",
    updated_at: null,
    extracted_text: null,
    feature_schema_version: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score: null,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    recommendations: null,
    target_fetch_status: null,
    target_fetch_method: null,
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
    status: "queued",
    score: null,
    extracted_text: null,
    feature_schema_version: null,
    target_snapshot_summary: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    target_fetch_status: null,
    target_fetch_method: null,
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
    ...overrides,
  };
}

function createTimelineDiagnostics(
  overrides: Partial<AuditTimelineDiagnosticsResponse> = {},
): AuditTimelineDiagnosticsResponse {
  return {
    audit_id: "audit-1",
    processing_version: 1,
    status: "completed",
    event_count: 18,
    dispatch_count: 9,
    started_at: "2026-01-01T10:00:01",
    finished_at: "2026-01-01T10:00:11",
    total_duration_ms: 10_000,
    terminal_stage: "finalize",
    terminal_event: "completed",
    critical_path_duration_ms: 8_500,
    critical_path_stages: [
      {
        stage: "heavy_analysis",
        contribution_duration_ms: 3_200,
        mode: "serial",
        terminal_count: 1,
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
        total_duration_ms: 3_200,
        average_duration_ms: 3_200,
        max_duration_ms: 3_200,
        critical_path_mode: "serial",
        critical_path_duration_ms: 3_200,
        first_event_at: "2026-01-01T10:00:02",
        last_event_at: "2026-01-01T10:00:05",
        latest_event: "completed",
      },
    ],
    fan_out: null,
    ...overrides,
  };
}

function createRecommendationsBundle(): RecommendationsBundle {
  return {
    schema_version: "recommendations-v2",
    summary: {
      total_recommendations: 1,
      high_priority_count: 1,
      medium_priority_count: 0,
      low_priority_count: 0,
      groups_with_issues: 1,
      competitor_context: true,
      score_gap_vs_competitors: -5.4,
    },
    groups: [
      {
        key: "technical_seo",
        label: "Technical SEO",
        description: "Technical description",
        status: "critical",
        items: [
          {
            code: "TECHNICAL_INDEXING_BLOCK",
            priority: "high",
            impact: "high",
            title: "Есть блокирующая проблема индексации",
            message: "Страница закрыта от индексации.",
            expected_outcome: "Исправление может заметно поднять итоговый score.",
            evidence: [
              {
                label: "Индексируемость страницы",
                value: "Нет",
                benchmark: "Да",
                benchmark_label: "Среднее по конкурентам",
              },
            ],
            related_metrics: ["page_indexable"],
          },
        ],
        deviations: [
          {
            code: "page_indexable",
            label: "Индексируемость страницы",
            unit: "binary",
            current_value: 0,
            benchmark_value: 1,
            benchmark_label: "Среднее по конкурентам",
            delta: -1,
            gap: 1,
            trend: "behind",
            priority: "high",
            summary: "Страница отстаёт от среднего по конкурентам.",
          },
        ],
        empty_state: "No issues",
      },
      {
        key: "commercial_trust",
        label: "Commercial and Trust",
        description: "Commercial description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "semantic_intent",
        label: "Semantic and Intent",
        description: "Semantic description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "competitor_gap",
        label: "Competitor Gap",
        description: "Gap description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
    ],
  };
}

describe("resolveAuditFailureContext", () => {
  it("prefers explicit failure_context from results", () => {
    const context: FailureContext = {
      stage: "scoring",
      code: "runtime_error",
      message: "model calibration failed",
      details: null,
    };

    const audit = createAudit({
      status: "failed",
      error_message: "stale audit error",
    });
    const results = createResults({
      status: "failed",
      failure_context: context,
      error_message: "model calibration failed",
    });

    expect(resolveAuditFailureContext(audit, results)).toEqual(context);
  });

  it("builds fallback fetch context when structured failure_context is absent", () => {
    const audit = createAudit({
      status: "failed",
      target_fetch_status: "failed",
      target_fetch_method: "browser",
      target_fetch_error_code: "http_403",
      target_fetch_error_message: "HTTP 403",
      error_message: "HTTP 403",
    });

    expect(resolveAuditFailureContext(audit, null)).toEqual({
      stage: "fetch",
      code: "http_403",
      message: "HTTP 403",
      details: {
        fetch_method: "browser",
      },
    });
  });
});

describe("RecommendationsPage", () => {
  it("renders failure diagnostics for failed audit", () => {
    const context: FailureContext = {
      stage: "search",
      code: "runtime_error",
      message: "SERP provider unavailable",
      details: null,
    };

    const markup = renderToStaticMarkup(
      <RecommendationsPage
        recommendations={null}
        auditStatus="failed"
        loading={false}
        error={null}
        failureContext={context}
      />,
    );

    expect(markup).toContain("Рекомендации не сформированы");
    expect(markup).toContain("поиск и анализ конкурентов");
    expect(markup).toContain("SERP provider unavailable");
    expect(markup).toContain("runtime_error");
  });

  it("renders grouped recommendation sections", () => {
    const markup = renderToStaticMarkup(
      <RecommendationsPage
        recommendations={createRecommendationsBundle()}
        auditStatus="completed"
        loading={false}
        error={null}
        failureContext={null}
      />,
    );

    expect(markup).toContain("Technical SEO");
    expect(markup).toContain("Commercial and Trust");
    expect(markup).toContain("Есть блокирующая проблема индексации");
    expect(markup).toContain("Среднее по конкурентам");
  });
});

describe("AuditWorkspace", () => {
  it("renders score breakdowns that use top factor fields", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        currentAudit={createAudit({
          status: "completed",
          score: 48.3,
          comparison_summary: {
            user_score: 48.3,
            competitors_average_score: 68.7,
            score_difference: -20.4,
            competitors_count: 2,
          },
        })}
        currentResults={createResults({
          status: "completed",
          score: 48.3,
          score_breakdown: {
            final_score: 48.3,
            rule_score: 23.8,
            ml_score: 68.4,
            top_positive_factors: [
              {
                key: "semantic_relevance",
                label: "Semantic relevance",
                impact: 5.6,
                value: 0.28,
              },
            ],
            top_negative_factors: [
              {
                key: "commercial_completeness",
                label: "Commercial completeness",
                impact: -3.5,
                value: 0,
              },
            ],
          },
        })}
        recommendations={null}
        timelineDiagnostics={null}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 48.3,
          competitors_average_score: 68.7,
          score_difference: -20.4,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="overview"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Semantic relevance");
    expect(markup).toContain("Commercial completeness");
  });

  it("renders audit report dashboard with export actions and runtime evidence", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        currentAudit={createAudit({
          status: "completed",
          score: 72.4,
          feature_schema_version: "v2",
          query_intent: { label: "commercial", confidence: 0.8 },
          heavy_analysis: { summary: "ok" },
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
          },
        })}
        currentResults={createResults({
          status: "completed",
          score: 72.4,
          feature_schema_version: "v2",
          target_snapshot_summary: {
            status_code: 200,
            fetch_method: "http",
          },
          heavy_analysis: { summary: "ok" },
          query_intent: { label: "commercial", confidence: 0.8 },
          features: {
            technical_seo_score: 0.8,
            commercial_trust_score: 0.6,
            semantic_similarity: 0.72,
            intent_alignment_score: 0.68,
          },
          score_breakdown: {
            final_score: 72.4,
            rule_score: 70,
            ml_score: 74,
          },
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
            competitors_found: 2,
            competitors_analyzed: 2,
            competitors_failed: 0,
          },
          competitor_results: [
            {
              url: "https://competitor.example/",
              domain: "competitor.example",
              title: "Competitor",
              fetch_status: "success",
              fetch_method: "http",
              fetch_error_code: null,
              fetch_error_message: null,
              score: 78.2,
              features: null,
            },
          ],
        })}
        recommendations={createRecommendationsBundle()}
        timelineDiagnostics={createTimelineDiagnostics()}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 72.4,
          competitors_average_score: 78.2,
          score_difference: -5.8,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="report"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Отчёт аудита");
    expect(markup).toContain("Скачать Markdown");
    expect(markup).toContain("SEO evidence");
    expect(markup).toContain("Distributed runtime evidence");
    expect(markup).toContain("Heavy analysis");
  });

  it("renders report recommendations from the stored audit payload when endpoint data is absent", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        currentAudit={createAudit({
          status: "completed",
          score: 72.4,
          recommendations: createRecommendationsBundle(),
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
          },
        })}
        currentResults={null}
        recommendations={null}
        timelineDiagnostics={null}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 72.4,
          competitors_average_score: 78.2,
          score_difference: -5.8,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="report"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Recommendation plan");
    expect(markup).toContain("Есть блокирующая проблема индексации");
    expect(markup).toContain("1");
  });
});
