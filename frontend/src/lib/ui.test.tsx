import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RecommendationsPage } from "../pages/RecommendationsPage";
import type { AuditResultsResponse, AuditStatusResponse, FailureContext, RecommendationsBundle } from "../types";
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
    heavy_analysis: null,
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
    heavy_analysis: null,
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
