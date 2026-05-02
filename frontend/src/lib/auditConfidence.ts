import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  ComparisonSummary,
  RecommendationsBundle,
} from "../types";
import {
  buildScoreConfidenceContext,
  buildScoreConfidenceMetrics,
} from "./auditConfidenceContext";
import {
  buildScoreConfidenceReasons,
} from "./auditConfidenceInternals";

export type ScoreConfidenceLevel = "high" | "medium" | "low" | "unknown";
export type ScoreConfidenceTone = "ok" | "warning" | "error" | "muted";

export type ScoreConfidenceReason = {
  code: string;
  label: string;
  detail: string;
  tone: ScoreConfidenceTone;
};

export type ScoreConfidenceMetric = {
  label: string;
  value: string;
  note: string;
  tone: ScoreConfidenceTone;
};

export type ScoreConfidenceView = {
  level: ScoreConfidenceLevel;
  tone: ScoreConfidenceTone;
  label: string;
  compactLabel: string;
  summary: string;
  detail: string;
  reasons: ScoreConfidenceReason[];
  metrics: ScoreConfidenceMetric[];
  errorCount: number;
  warningCount: number;
  passedCount: number;
};

export type ScoreConfidenceInput = {
  audit: AuditStatusResponse | null;
  results?: AuditResultsResponse | null;
  recommendations?: RecommendationsBundle | null;
  comparisonSummary?: ComparisonSummary | null;
};

const IN_FLIGHT_STATUSES = new Set<AuditStatus>(["queued", "processing"]);

const levelLabels: Record<ScoreConfidenceLevel, string> = {
  high: "Высокая уверенность",
  medium: "Средняя уверенность",
  low: "Низкая уверенность",
  unknown: "Уверенность неизвестна",
};

const compactLevelLabels: Record<ScoreConfidenceLevel, string> = {
  high: "Данные: полные",
  medium: "Данные: частичные",
  low: "Данные: требуют проверки",
  unknown: "Данные: проверяются",
};

const toneOrder: Record<ScoreConfidenceTone, number> = {
  error: 0,
  warning: 1,
  muted: 2,
  ok: 3,
};

function deriveLevel(
  status: AuditStatus | null,
  score: number | null,
  reasons: ScoreConfidenceReason[],
): ScoreConfidenceLevel {
  if (!status || IN_FLIGHT_STATUSES.has(status)) {
    return "unknown";
  }
  if (status === "failed" || reasons.some((reason) => reason.tone === "error")) {
    return "low";
  }
  if (typeof score !== "number") {
    return "unknown";
  }
  if (reasons.some((reason) => reason.tone === "warning")) {
    return "medium";
  }
  return "high";
}

function levelTone(level: ScoreConfidenceLevel): ScoreConfidenceTone {
  if (level === "high") {
    return "ok";
  }
  if (level === "medium") {
    return "warning";
  }
  if (level === "low") {
    return "error";
  }
  return "muted";
}

function buildSummary(level: ScoreConfidenceLevel): string {
  if (level === "high") {
    return "Score опирается на полный payload целевой страницы: страница загружена, признаки и модель идентифицированы; конкуренты и рекомендации доступны отдельным контекстом.";
  }
  if (level === "medium") {
    return "Score рассчитан, но часть входных данных неполная или содержит предупреждения. Используйте оценку вместе с reason list.";
  }
  if (level === "low") {
    return "Score нельзя считать надёжным без ручной проверки: есть блокирующие проблемы данных или pipeline завершился ошибкой.";
  }
  return "Уверенность пока нельзя оценить: аудит ещё выполняется или score отсутствует.";
}

function orderReasons(
  reasons: ScoreConfidenceReason[],
  level: ScoreConfidenceLevel,
): ScoreConfidenceReason[] {
  const order =
    level === "unknown"
      ? ({ muted: 0, error: 1, warning: 2, ok: 3 } as Record<ScoreConfidenceTone, number>)
      : toneOrder;
  return reasons
    .map((reason, index) => ({ reason, index }))
    .sort((left, right) => order[left.reason.tone] - order[right.reason.tone] || left.index - right.index)
    .map(({ reason }) => reason);
}

export function buildScoreConfidenceView(input: ScoreConfidenceInput): ScoreConfidenceView {
  const context = buildScoreConfidenceContext(input);
  const rawReasons = buildScoreConfidenceReasons(input, context);
  const level = deriveLevel(context.status, context.score, rawReasons);
  const reasons = orderReasons(rawReasons, level);
  const warningCount = reasons.filter((reason) => reason.tone === "warning").length;
  const errorCount = reasons.filter((reason) => reason.tone === "error").length;
  const passedCount = reasons.filter((reason) => reason.tone === "ok").length;
  const tone = levelTone(level);
  const label = levelLabels[level];
  const summary = buildSummary(level);

  return {
    level,
    tone,
    label,
    compactLabel: compactLevelLabels[level],
    summary,
    detail: "Проверяются fetch status, feature schema, heavy analysis, competitor coverage, рекомендации, model_info и runtime warnings.",
    reasons,
    metrics: buildScoreConfidenceMetrics(context, label, tone, summary, warningCount, errorCount),
    errorCount,
    warningCount,
    passedCount,
  };
}
