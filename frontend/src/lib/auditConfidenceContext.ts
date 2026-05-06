import type {
  AuditStatus,
  ComparisonSummary,
  CompetitorResult,
  RecommendationsBundle,
  ScoreBreakdown,
} from "../types";
import type {
  ScoreConfidenceInput,
  ScoreConfidenceMetric,
  ScoreConfidenceTone,
} from "./auditConfidence";
import { buildCompetitorContextStats } from "./competitorContext";
import { flattenRecommendationItems } from "./recommendations";

export type CompetitorCoverage = {
  found: number;
  analyzed: number;
  failed: number;
  ratio: number | null;
};

export type ScoreConfidenceContext = {
  status: AuditStatus | null;
  breakdown: ScoreBreakdown | null;
  score: number | null;
  coverage: CompetitorCoverage;
  recommendationCount: number | null;
  modelInfo: Record<string, unknown> | null;
};

export const MIN_COMPETITORS_ANALYZED = 1;
export const MIN_COMPETITOR_COVERAGE_RATIO = 0.5;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function hasRecordValues(value: unknown): value is Record<string, unknown> {
  return isRecord(value) && Object.keys(value).length > 0;
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(Math.round(value)) : "—";
}

export function formatScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return String(Math.round(value * 10) / 10);
}

export function formatPercent(value: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return `${Math.round(value * 100)}%`;
}

function getEffectiveStatus(input: ScoreConfidenceInput): AuditStatus | null {
  return input.results?.status ?? input.audit?.status ?? null;
}

function getEffectiveBreakdown(input: ScoreConfidenceInput): ScoreBreakdown | null {
  return input.results?.score_breakdown ?? input.audit?.score_breakdown ?? null;
}

function getEffectiveScore(input: ScoreConfidenceInput, breakdown: ScoreBreakdown | null): number | null {
  return (
    asFiniteNumber(input.results?.score) ??
    asFiniteNumber(input.audit?.score) ??
    asFiniteNumber(breakdown?.final_score)
  );
}

export function getEffectiveFeatureSchema(input: ScoreConfidenceInput): string | null {
  return asNonEmptyString(input.results?.feature_schema_version) ?? asNonEmptyString(input.audit?.feature_schema_version);
}

export function getEffectiveHeavyAnalysis(input: ScoreConfidenceInput): Record<string, unknown> | null {
  if (hasRecordValues(input.results?.heavy_analysis)) {
    return input.results.heavy_analysis;
  }
  if (hasRecordValues(input.audit?.heavy_analysis)) {
    return input.audit.heavy_analysis;
  }
  return null;
}

function getEffectiveRecommendations(input: ScoreConfidenceInput): RecommendationsBundle | null {
  return input.recommendations ?? input.audit?.recommendations ?? null;
}

function getRecommendationCount(recommendations: RecommendationsBundle | null): number | null {
  if (!recommendations) {
    return null;
  }
  const summaryCount = asFiniteNumber(recommendations.summary?.total_recommendations);
  return summaryCount ?? flattenRecommendationItems(recommendations).length;
}

function getEffectiveComparisonSummary(input: ScoreConfidenceInput): ComparisonSummary | null {
  return input.comparisonSummary ?? input.results?.comparison_summary ?? input.audit?.comparison_summary ?? null;
}

function getEffectiveCompetitors(input: ScoreConfidenceInput): CompetitorResult[] {
  return input.results?.competitor_results ?? input.audit?.competitor_results ?? [];
}

function buildCompetitorCoverage(input: ScoreConfidenceInput): CompetitorCoverage {
  const summary = getEffectiveComparisonSummary(input);
  const competitors = getEffectiveCompetitors(input);
  const stats = buildCompetitorContextStats(summary, competitors);
  const found = stats.collected;
  const analyzed = stats.accepted;
  const failed = stats.hasQualityV2 ? stats.discarded + stats.replacements : stats.failed;

  return {
    found: Math.max(0, Math.round(found)),
    analyzed: Math.max(0, Math.round(analyzed)),
    failed: Math.max(0, Math.round(failed)),
    ratio: found > 0 ? Math.max(0, Math.min(1, analyzed / found)) : null,
  };
}

export function getWarnings(input: ScoreConfidenceInput): string[] {
  const warnings = [...(input.audit?.warnings ?? []), ...(input.results?.warnings ?? [])]
    .filter((warning): warning is string => typeof warning === "string" && warning.trim().length > 0)
    .map((warning) => warning.trim());
  return Array.from(new Set(warnings));
}

export function getModelLabel(modelInfo: Record<string, unknown> | null): string {
  if (!modelInfo) {
    return "model_info отсутствует";
  }
  const modelType = asNonEmptyString(modelInfo.model_type) ?? "модель не указана";
  const schema = asNonEmptyString(modelInfo.model_schema_version) ?? "схема не указана";
  return `${modelType} · ${schema}`;
}

export function getFailureLabel(input: ScoreConfidenceInput): string {
  const failureContext = input.results?.failure_context ?? input.audit?.failure_context ?? null;
  const errorMessage = asNonEmptyString(input.results?.error_message) ?? asNonEmptyString(input.audit?.error_message);
  const stage = asNonEmptyString(failureContext?.stage);
  const message = asNonEmptyString(failureContext?.message) ?? errorMessage ?? "причина не указана";
  return stage ? `${stage}: ${message}` : message;
}

export function buildScoreConfidenceContext(input: ScoreConfidenceInput): ScoreConfidenceContext {
  const breakdown = getEffectiveBreakdown(input);
  const recommendations = getEffectiveRecommendations(input);

  return {
    status: getEffectiveStatus(input),
    breakdown,
    score: getEffectiveScore(input, breakdown),
    coverage: buildCompetitorCoverage(input),
    recommendationCount: getRecommendationCount(recommendations),
    modelInfo: hasRecordValues(breakdown?.model_info) ? breakdown.model_info : null,
  };
}

export function buildScoreConfidenceMetrics(
  context: ScoreConfidenceContext,
  levelLabel: string,
  tone: ScoreConfidenceTone,
  summary: string,
  warningCount: number,
  errorCount: number,
): ScoreConfidenceMetric[] {
  return [
    {
      label: "Уровень",
      value: levelLabel,
      note: summary,
      tone,
    },
    {
      label: "Конкуренты",
      value: `${formatCount(context.coverage.analyzed)}/${formatCount(context.coverage.found)}`,
      note: `Покрытие: ${formatPercent(context.coverage.ratio)}; ошибок: ${formatCount(context.coverage.failed)}.`,
      tone:
        context.coverage.analyzed < MIN_COMPETITORS_ANALYZED
          ? "error"
          : context.coverage.ratio !== null && context.coverage.ratio < MIN_COMPETITOR_COVERAGE_RATIO
            ? "warning"
            : "ok",
    },
    {
      label: "Рекомендации",
      value: formatCount(context.recommendationCount),
      note:
        context.recommendationCount && context.recommendationCount > 0
          ? "План действий сформирован."
          : "План действий не подтверждает score.",
      tone: context.recommendationCount && context.recommendationCount > 0 ? "ok" : "warning",
    },
    {
      label: "Runtime-модель",
      value: getModelLabel(context.modelInfo),
      note: context.modelInfo ? "score_breakdown.model_info сохранён." : "Нет metadata модели для legacy/runtime проверки.",
      tone: context.modelInfo ? "ok" : "warning",
    },
    {
      label: "Warnings/errors",
      value: `${warningCount}/${errorCount}`,
      note: "Количество предупреждений и блокирующих причин в confidence reason list.",
      tone: errorCount > 0 ? "error" : warningCount > 0 ? "warning" : "ok",
    },
  ];
}
