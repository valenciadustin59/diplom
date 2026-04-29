import { describe, expect, it } from "vitest";
import type {
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  RecommendationsBundle,
} from "../types";
import {
  buildAuditReportFilename,
  buildAuditReportModel,
  createAuditReportMarkdown,
  formatReportDuration,
} from "./auditReport";
import { createAuditReportHtml } from "./auditReportHtml";

function createAudit(): AuditStatusResponse {
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
    heavy_analysis: { analyzed: true },
    query_intent: { label: "commercial" },
    features: {
      technical_seo_score: 0.8,
      commercial_trust_score: 0.6,
      semantic_similarity: 0.7,
      intent_alignment_score: 0.75,
    },
    score: 72.4,
    score_breakdown: {
      final_score: 72.4,
      rule_score: 70,
      ml_score: 74,
    },
    competitor_results: null,
    comparison_summary: {
      user_score: 72.4,
      competitors_average_score: 78.2,
      score_difference: -5.8,
      competitors_count: 1,
      competitors_found: 1,
      competitors_analyzed: 1,
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
  };
}

function createResults(): AuditResultsResponse {
  return {
    audit_id: "audit-1",
    status: "completed",
    score: 72.4,
    extracted_text: "landing text",
    feature_schema_version: "v2",
    target_snapshot_summary: {
      status_code: 200,
      fetch_method: "http",
    },
    heavy_analysis: { analyzed: true },
    query_intent: { label: "commercial" },
    features: {
      technical_seo_score: 0.8,
      commercial_trust_score: 0.6,
      semantic_similarity: 0.7,
      intent_alignment_score: 0.75,
    },
    score_breakdown: {
      final_score: 72.4,
      rule_score: 70,
      ml_score: 74,
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
    comparison_summary: {
      user_score: 72.4,
      competitors_average_score: 78.2,
      score_difference: -5.8,
      competitors_count: 1,
      competitors_found: 1,
      competitors_analyzed: 1,
      competitors_failed: 0,
    },
    target_fetch_status: "success",
    target_fetch_method: "http",
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
  };
}

function createRecommendations(): RecommendationsBundle {
  return {
    schema_version: "recommendations-v2",
    summary: {
      total_recommendations: 6,
      high_priority_count: 2,
      medium_priority_count: 3,
      low_priority_count: 1,
      groups_with_issues: 1,
      competitor_context: true,
      score_gap_vs_competitors: -5.8,
    },
    groups: [
      {
        key: "technical_seo",
        label: "Technical SEO",
        description: "Technical issues",
        status: "critical",
        items: [
          {
            code: "TECHNICAL_TITLE",
            priority: "high",
            impact: "high",
            title: "Усилить title",
            message: "Title слабее конкурентов.",
            expected_outcome: "Повысить релевантность сниппета.",
            evidence: [],
            related_metrics: ["title_length"],
          },
          {
            code: "TECHNICAL_INDEXING",
            priority: "high",
            impact: "high",
            title: "Открыть индексацию",
            message: "Проверить robots, canonical и HTTP-статус.",
            expected_outcome: "Снять блокирующий технический риск.",
            evidence: [],
            related_metrics: ["page_indexable"],
          },
          {
            code: "TECHNICAL_CANONICAL",
            priority: "medium",
            impact: "medium",
            title: "Уточнить canonical",
            message: "Canonical должен указывать на целевую посадочную.",
            expected_outcome: "Снизить риск дублей в выдаче.",
            evidence: [],
            related_metrics: ["canonical_present"],
          },
          {
            code: "TECHNICAL_HEADINGS",
            priority: "medium",
            impact: "medium",
            title: "Пересобрать H1/H2",
            message: "Заголовки должны явно покрывать поисковое намерение.",
            expected_outcome: "Усилить смысловое соответствие.",
            evidence: [],
            related_metrics: ["heading_semantic_alignment"],
          },
          {
            code: "TECHNICAL_SNIPPET",
            priority: "medium",
            impact: "medium",
            title: "Усилить мета-описание",
            message: "Добавить обещание, УТП и формулировку под запрос.",
            expected_outcome: "Повысить CTR сниппета.",
            evidence: [],
            related_metrics: ["meta_description_length"],
          },
          {
            code: "TECHNICAL_LOW",
            priority: "low",
            impact: "low",
            title: "Почистить вторичные SEO-сигналы",
            message: "Убрать мелкие несоответствия в служебных тегах.",
            expected_outcome: "Закрыть остаточные точки роста.",
            evidence: [],
            related_metrics: ["secondary_seo_score"],
          },
        ],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "commercial_trust",
        label: "Commercial and Trust",
        description: "Commercial issues",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "semantic_intent",
        label: "Semantic and Intent",
        description: "Semantic issues",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "competitor_gap",
        label: "Competitor Gap",
        description: "Gap issues",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
    ],
  };
}

function createDiagnostics(): AuditTimelineDiagnosticsResponse {
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
    critical_path_stages: [],
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
  };
}

describe("audit report export", () => {
  it("builds a compact report model with SEO, recommendations, competitors and runtime evidence", () => {
    const model = buildAuditReportModel({
      audit: createAudit(),
      results: createResults(),
      recommendations: createRecommendations(),
      diagnostics: createDiagnostics(),
      generatedAt: new Date("2026-01-01T12:00:00Z"),
    });

    expect(model.domain).toBe("example.com");
    expect(model.scoreLabel).toBe("72.4");
    expect(model.seoMetrics.map((metric) => metric.label)).toContain("Углублённый анализ");
    expect(model.recommendationActions.map((item) => item.title)).toContain("Усилить title");
    expect(model.recommendationActions).toHaveLength(6);
    expect(model.stageRows[0].stage).toBe("Углублённый анализ");
  });

  it("builds report recommendations from stored audit payloads when endpoint data is unavailable", () => {
    const model = buildAuditReportModel({
      audit: {
        ...createAudit(),
        recommendations: createRecommendations(),
      },
      results: null,
      recommendations: null,
      diagnostics: null,
      generatedAt: new Date("2026-01-01T12:00:00Z"),
    });

    expect(model.recommendationMetrics[0].value).toBe("6");
    expect(model.recommendationActions.map((item) => item.code)).toContain("TECHNICAL_TITLE");
  });

  it("exports markdown and printable html without repeating audit execution", () => {
    const input = {
      audit: createAudit(),
      results: createResults(),
      recommendations: createRecommendations(),
      diagnostics: createDiagnostics(),
      generatedAt: new Date("2026-01-01T12:00:00Z"),
    };

    const markdown = createAuditReportMarkdown(input);
    const html = createAuditReportHtml(input, { autoPrint: true });

    expect(markdown).toContain("## Доказательство распределённого выполнения");
    expect(markdown).toContain("### Список действий");
    expect(markdown).toContain("TECHNICAL_LOW");
    expect(markdown.split("\n").filter((line) => line.startsWith("- ["))).toHaveLength(6);
    expect(markdown.indexOf("TECHNICAL_INDEXING")).toBeLessThan(markdown.indexOf("TECHNICAL_CANONICAL"));
    expect(markdown.indexOf("TECHNICAL_SNIPPET")).toBeLessThan(markdown.indexOf("TECHNICAL_LOW"));
    expect(html).toContain("<!doctype html>");
    expect(html).toContain("window.print");
    expect(html).toContain("SEO-сигналы");
    expect(html).toContain("TECHNICAL_LOW");
    expect(html.match(/TECHNICAL_/g)).toHaveLength(6);
  });

  it("creates stable filenames and human-readable durations", () => {
    expect(buildAuditReportFilename(createAudit(), "md")).toBe("site-audit-report-example.com-2026-01-01.md");
    expect(formatReportDuration(850)).toBe("850 мс");
    expect(formatReportDuration(8_500)).toBe("8.5 с");
  });
});
