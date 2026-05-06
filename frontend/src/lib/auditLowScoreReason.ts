import type {
  AuditResultsResponse,
  AuditStatusResponse,
  ComparisonSummary,
  FailureContext,
  RecommendationsBundle,
  ScoreBreakdown,
} from "../types";
import { getEarlyStopMismatchView } from "./earlyStop";

export type LowScoreReasonKind =
  | "page_unavailable"
  | "http_404"
  | "http_error"
  | "noindex"
  | "unusable"
  | "query_mismatch"
  | "competitor_gap"
  | "seo_gaps"
  | "unknown";

export type LowScoreReasonCategory =
  | "page_unavailable"
  | "query_mismatch"
  | "competitor_gap"
  | "seo_gaps"
  | "unknown";

export type LowScoreReasonTone = "error" | "warning" | "info" | "neutral";

export type AuditLowScoreReason = {
  kind: LowScoreReasonKind;
  category: LowScoreReasonCategory;
  tone: LowScoreReasonTone;
  title: string;
  message: string;
  badge: string;
  isBlocking: boolean;
  recoveryActions: string[];
};

export type AuditLowScoreReasonInput = {
  audit: AuditStatusResponse | null;
  results?: AuditResultsResponse | null;
  recommendations?: RecommendationsBundle | null;
  comparisonSummary?: ComparisonSummary | null;
};

const unknownReason: AuditLowScoreReason = {
  kind: "unknown",
  category: "unknown",
  tone: "neutral",
  title: "Причина низкой оценки не определена",
  message: "Когда аудит завершится, здесь появится понятное объяснение результата.",
  badge: "Оценка",
  isBlocking: false,
  recoveryActions: [],
};

const unavailableRecoveryActions = [
  "Проверьте, что URL открывается в браузере без ошибки.",
  "Настройте корректный редирект на рабочую посадочную страницу, если адрес изменился.",
  "Убедитесь, что сервер отдаёт успешный HTTP-ответ для целевой страницы.",
  "Проверьте, что страница доступна для индексации и не закрыта служебными правилами.",
];

function getFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getRecordNumber(record: Record<string, unknown> | null | undefined, key: string): number | null {
  return getFiniteNumber(record?.[key]);
}

function getFeatures(input: AuditLowScoreReasonInput): Record<string, unknown> {
  return input.results?.features ?? input.audit?.features ?? {};
}

function getBreakdown(input: AuditLowScoreReasonInput): ScoreBreakdown | null {
  return input.results?.score_breakdown ?? input.audit?.score_breakdown ?? null;
}

function getComparisonSummary(input: AuditLowScoreReasonInput): ComparisonSummary | null {
  return input.comparisonSummary ?? input.results?.comparison_summary ?? input.audit?.comparison_summary ?? null;
}

function getFinalScore(input: AuditLowScoreReasonInput): number | null {
  const breakdown = getBreakdown(input);
  const summary = getComparisonSummary(input);
  return (
    getFiniteNumber(breakdown?.final_score) ??
    getFiniteNumber(breakdown?.competitiveness_score) ??
    getFiniteNumber(input.results?.score) ??
    getFiniteNumber(input.audit?.score) ??
    getFiniteNumber(summary?.competitiveness_score) ??
    getFiniteNumber(summary?.user_score)
  );
}

function getFailureContext(input: AuditLowScoreReasonInput): FailureContext | null {
  return input.results?.failure_context ?? input.audit?.failure_context ?? null;
}

function getHttpStatus(input: AuditLowScoreReasonInput): number | null {
  const snapshot = input.results?.target_snapshot_summary;
  const fromSnapshot = getRecordNumber(snapshot, "status_code") ?? getRecordNumber(snapshot, "http_status");
  const fromFeatures = getRecordNumber(getFeatures(input), "http_status_code");
  const fromFailure = getRecordNumber(getFailureContext(input)?.details, "http_status");
  return fromSnapshot ?? fromFeatures ?? fromFailure;
}

function hasFetchFailure(input: AuditLowScoreReasonInput): boolean {
  const failureContext = getFailureContext(input);
  const targetFetchStatus = input.results?.target_fetch_status ?? input.audit?.target_fetch_status;
  return targetFetchStatus === "failed" || failureContext?.stage === "fetch";
}

function buildUnavailableReason(kind: LowScoreReasonKind, title: string, message: string): AuditLowScoreReason {
  return {
    kind,
    category: "page_unavailable",
    tone: "error",
    title,
    message,
    badge: "Доступность",
    isBlocking: true,
    recoveryActions: unavailableRecoveryActions,
  };
}

function getUnavailableReason(input: AuditLowScoreReasonInput): AuditLowScoreReason | null {
  const features = getFeatures(input);
  const httpStatus = getHttpStatus(input);
  const httpStatusOk = getRecordNumber(features, "http_status_ok");
  const pageIndexable = getRecordNumber(features, "page_indexable");
  const robotsNoindex = getRecordNumber(features, "robots_noindex");
  const wordCount = getRecordNumber(features, "word_count");
  const textLength = getRecordNumber(features, "text_length_chars");
  const guardrail = getBreakdown(input)?.relevance_guardrail;
  const guardrailReason = typeof guardrail?.reason === "string" ? guardrail.reason : null;
  const guardrailBand = typeof guardrail?.band === "string" ? guardrail.band : null;

  if (httpStatus === 404) {
    return buildUnavailableReason(
      "http_404",
      "Страница недоступна: HTTP 404",
      "Система получила ответ 404 для целевой страницы. Это проблема доступности URL, а не обычная SEO-просадка.",
    );
  }

  if ((httpStatus !== null && httpStatus >= 400) || hasFetchFailure(input) || httpStatusOk === 0) {
    const statusText = httpStatus !== null ? `HTTP ${httpStatus}` : "ошибка загрузки";
    return buildUnavailableReason(
      "http_error",
      `Страница недоступна: ${statusText}`,
      "Целевая страница не открылась как рабочая посадочная. Сначала восстановите доступность, затем повторите аудит.",
    );
  }

  if (pageIndexable === 0 || robotsNoindex === 1) {
    return buildUnavailableReason(
      "noindex",
      "Страница закрыта от индексации",
      "Страница может быть доступна пользователю, но поисковые системы не смогут нормально учитывать её в выдаче.",
    );
  }

  if (
    guardrailReason === "page_unusable" ||
    guardrailBand === "unusable" ||
    (wordCount !== null && textLength !== null && wordCount < 20 && textLength < 200)
  ) {
    return buildUnavailableReason(
      "unusable",
      "Страница не пригодна для полноценной оценки",
      "На странице слишком мало доступного содержимого или она не прошла базовую проверку пригодности.",
    );
  }

  return null;
}

function getQueryMismatchReason(input: AuditLowScoreReasonInput): AuditLowScoreReason | null {
  const breakdown = getBreakdown(input);
  const earlyStopView = getEarlyStopMismatchView(breakdown);
  const guardrail = breakdown?.relevance_guardrail;
  const guardrailReason = typeof guardrail?.reason === "string" ? guardrail.reason : null;
  const guardrailBand = typeof guardrail?.band === "string" ? guardrail.band : null;

  if (
    earlyStopView ||
    guardrailReason === "confident_full_query_mismatch" ||
    guardrailReason === "probable_query_topic_mismatch" ||
    guardrailBand === "full_mismatch" ||
    guardrailBand === "probable_mismatch"
  ) {
    return {
      kind: "query_mismatch",
      category: "query_mismatch",
      tone: "warning",
      title: earlyStopView?.title ?? "Страница не соответствует запросу",
      message:
        earlyStopView?.message ??
        "Страница отвечает другой теме или другому намерению пользователя, поэтому итоговая оценка ограничена.",
      badge: "Запрос",
      isBlocking: false,
      recoveryActions: [
        "Проверьте, что выбранная посадочная страница действительно отвечает этому запросу.",
        "Если страница про другой товар или услугу, запустите аудит с более точным URL.",
        "Если URL верный, усилите заголовок, основной текст и оффер вокруг темы запроса.",
      ],
    };
  }

  return null;
}

function getCompetitorGapReason(input: AuditLowScoreReasonInput): AuditLowScoreReason | null {
  const score = getFinalScore(input);
  const summary = getComparisonSummary(input);
  const scoreGap =
    getFiniteNumber(summary?.score_difference) ??
    getFiniteNumber(summary?.primary_score_difference) ??
    getFiniteNumber(input.recommendations?.summary.score_gap_vs_competitors);

  if (score !== null && score < 80 && scoreGap !== null && scoreGap <= -5) {
    return {
      kind: "competitor_gap",
      category: "competitor_gap",
      tone: "info",
      title: "Страница релевантна, но уступает конкурентам",
      message: "Страница отвечает запросу, однако обработанные конкуренты выглядят сильнее по важным для пользователя сигналам.",
      badge: "Конкуренты",
      isBlocking: false,
      recoveryActions: [],
    };
  }

  return null;
}

function getSeoGapsReason(input: AuditLowScoreReasonInput): AuditLowScoreReason | null {
  const score = getFinalScore(input);
  const recommendationsCount = input.recommendations?.summary.total_recommendations ?? input.audit?.recommendations?.summary.total_recommendations ?? 0;
  const groupsWithIssues = input.recommendations?.summary.groups_with_issues ?? input.audit?.recommendations?.summary.groups_with_issues ?? 0;
  const negativeFactors =
    (getBreakdown(input)?.negatives ?? getBreakdown(input)?.top_negative_factors ?? []).length +
    (getBreakdown(input)?.factor_groups ?? []).filter((group) => group.items.some((item) => item.impact < 0)).length;

  if (score !== null && score < 80 && (recommendationsCount > 0 || groupsWithIssues > 0 || negativeFactors > 0)) {
    return {
      kind: "seo_gaps",
      category: "seo_gaps",
      tone: "info",
      title: "Есть SEO-пробелы, которые снижают оценку",
      message: "Страница открывается и соответствует запросу, но в проверках видны технические, смысловые или коммерческие зоны роста.",
      badge: "SEO-пробелы",
      isBlocking: false,
      recoveryActions: [],
    };
  }

  return null;
}

export function buildAuditLowScoreReason(input: AuditLowScoreReasonInput): AuditLowScoreReason {
  const score = getFinalScore(input);
  const unavailable = getUnavailableReason(input);
  if (unavailable) {
    return unavailable;
  }

  if (score !== null && score >= 80) {
    return unknownReason;
  }

  return getQueryMismatchReason(input) ?? getCompetitorGapReason(input) ?? getSeoGapsReason(input) ?? unknownReason;
}
