import { describe, expect, it } from "vitest";
import type { AuditResultsResponse, AuditStatusResponse, RecommendationsBundle } from "../types";
import { buildScoreConfidenceView } from "./auditConfidence";

const modelInfo = {
  model_type: "CatBoostRegressor",
  model_schema_version: "v3",
  dataset_version: "dataset-v3-d37",
  artifact_version: "dataset-v3-d37-20260501200434",
};

function createAudit(overrides: Partial<AuditStatusResponse> = {}): AuditStatusResponse {
  return {
    id: "audit-1",
    query: "купить диван",
    target_url: "https://example.com/landing",
    top_n: 3,
    status: "completed",
    created_at: "2026-01-01T10:00:00",
    updated_at: "2026-01-01T10:01:00",
    extracted_text: "landing text",
    feature_schema_version: "v2",
    heavy_analysis: { schema_version: "heavy-analysis-v1" },
    query_intent: { label: "commercial" },
    features: { semantic_similarity: 0.72 },
    score: 72.4,
    score_breakdown: {
      final_score: 72.4,
      rule_score: 70,
      ml_score: 74,
      model_info: modelInfo,
    },
    competitor_results: null,
    comparison_summary: {
      user_score: 72.4,
      competitors_average_score: 78.2,
      score_difference: -5.8,
      competitors_count: 2,
      competitors_found: 2,
      competitors_analyzed: 2,
      competitors_failed: 0,
    },
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
    score: 72.4,
    extracted_text: "landing text",
    feature_schema_version: "v2",
    target_snapshot_summary: { status_code: 200, fetch_method: "http" },
    heavy_analysis: { schema_version: "heavy-analysis-v1" },
    query_intent: { label: "commercial" },
    features: { semantic_similarity: 0.72 },
    score_breakdown: {
      final_score: 72.4,
      rule_score: 70,
      ml_score: 74,
      model_info: modelInfo,
    },
    competitor_results: null,
    comparison_summary: {
      user_score: 72.4,
      competitors_average_score: 78.2,
      score_difference: -5.8,
      competitors_count: 2,
      competitors_found: 2,
      competitors_analyzed: 2,
      competitors_failed: 0,
    },
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

function createRecommendations(overrides: Partial<RecommendationsBundle> = {}): RecommendationsBundle {
  return {
    schema_version: "recommendations-v2",
    summary: {
      total_recommendations: 2,
      high_priority_count: 1,
      medium_priority_count: 1,
      low_priority_count: 0,
      groups_with_issues: 1,
      competitor_context: true,
      score_gap_vs_competitors: -5.8,
    },
    groups: [
      {
        key: "technical_seo",
        label: "Техническое SEO",
        description: "Техническая пригодность страницы.",
        status: "attention",
        items: [
          {
            code: "TECHNICAL_TITLE",
            priority: "high",
            impact: "high",
            title: "Усилить title",
            message: "Добавить коммерческий интент.",
            expected_outcome: "Выше релевантность.",
            evidence: [],
            related_metrics: ["semantic_similarity"],
          },
          {
            code: "TECHNICAL_META",
            priority: "medium",
            impact: "medium",
            title: "Уточнить description",
            message: "Сделать сниппет конкретнее.",
            expected_outcome: "Выше CTR.",
            evidence: [],
            related_metrics: ["technical_seo_score"],
          },
        ],
        deviations: [],
        empty_state: "Технические рекомендации не требуются.",
      },
    ],
    ...overrides,
  };
}

describe("buildScoreConfidenceView", () => {
  it("classifies completed audits with full data as high confidence", () => {
    const confidence = buildScoreConfidenceView({
      audit: createAudit(),
      results: createResults(),
      recommendations: createRecommendations(),
    });

    expect(confidence.level).toBe("high");
    expect(confidence.tone).toBe("ok");
    expect(confidence.errorCount).toBe(0);
    expect(confidence.warningCount).toBe(0);
    expect(confidence.reasons.map((reason) => reason.code)).toContain("model_metadata_present");
    expect(confidence.metrics.find((metric) => metric.label === "Конкуренты")?.value).toBe("2/2");
  });

  it("keeps primary score at medium confidence when only competitor context is incomplete", () => {
    const longWarning =
      "Очень длинное предупреждение о том, что несколько конкурентных страниц ограничили автоматический доступ и требуют ручной проверки.";
    const confidence = buildScoreConfidenceView({
      audit: createAudit({
        status: "completed_with_warnings",
        feature_schema_version: null,
        heavy_analysis: null,
        warnings: [longWarning],
      }),
      results: createResults({
        status: "completed_with_warnings",
        feature_schema_version: null,
        heavy_analysis: null,
        score_breakdown: {
          final_score: 58,
          rule_score: 55,
          ml_score: 61,
        },
        comparison_summary: {
          user_score: 58,
          competitors_average_score: 0,
          score_difference: 0,
          competitors_count: 3,
          competitors_found: 3,
          competitors_analyzed: 0,
          competitors_failed: 3,
        },
        target_fetch_status: "success",
        target_fetch_method: "browser",
        warnings: [longWarning],
      }),
      recommendations: null,
    });

    expect(confidence.level).toBe("medium");
    expect(confidence.warningCount).toBeGreaterThan(0);
    expect(confidence.reasons.map((reason) => reason.code)).toContain("no_competitors_analyzed");
    expect(confidence.reasons.map((reason) => reason.code)).toContain("target_fetch_fallback");
    expect(confidence.reasons.map((reason) => reason.code)).toContain("missing_model_metadata");
    expect(confidence.reasons.some((reason) => reason.detail === longWarning)).toBe(true);
  });

  it("keeps processing audits in unknown confidence state", () => {
    const confidence = buildScoreConfidenceView({
      audit: createAudit({
        status: "processing",
        score: null,
        score_breakdown: null,
      }),
      results: createResults({
        status: "processing",
        score: null,
        score_breakdown: null,
        comparison_summary: null,
        target_fetch_status: null,
        target_fetch_method: null,
      }),
      recommendations: null,
    });

    expect(confidence.level).toBe("unknown");
    expect(confidence.tone).toBe("muted");
    expect(confidence.reasons[0].code).toBe("audit_in_progress");
  });

  it("treats legacy completed scores without model metadata as warnings, not crashes", () => {
    const confidence = buildScoreConfidenceView({
      audit: createAudit({
        score_breakdown: {
          final_score: 70,
          rule_score: 68,
          ml_score: 72,
        },
      }),
      results: null,
      recommendations: createRecommendations(),
    });

    expect(confidence.level).toBe("medium");
    expect(confidence.tone).toBe("warning");
    expect(confidence.reasons.map((reason) => reason.code)).toContain("missing_model_metadata");
    expect(confidence.metrics.find((metric) => metric.label === "Runtime-модель")?.tone).toBe("warning");
  });
});
