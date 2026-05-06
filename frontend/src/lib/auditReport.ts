import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  CompetitorResult,
  RecommendationsBundle,
} from "../types";
import { buildAuditLowScoreReason, type AuditLowScoreReason } from "./auditLowScoreReason";
import {
  buildCompetitorContextStats,
  formatCompetitorContextSummary,
  getAcceptedCompetitors,
} from "./competitorContext";
import { getEarlyStopMismatchView } from "./earlyStop";
import { flattenRecommendationItems } from "./recommendations";
import { getFetchMethodLabel, getIntentLabel, getRecommendationGroupLabel } from "./terminology";

export type AuditReportInput = {
  audit: AuditStatusResponse;
  results: AuditResultsResponse | null;
  recommendations: RecommendationsBundle | null;
  diagnostics: AuditTimelineDiagnosticsResponse | null;
  generatedAt?: Date;
};

export type ReportMetric = {
  label: string;
  value: string;
  note?: string;
};

export type ReportRecommendation = {
  code: string;
  groupLabel: string;
  priorityLabel: string;
  title: string;
  message: string;
  expectedOutcome: string;
};

export type ReportStageRow = {
  stage: string;
  completed: number;
  failed: number;
  terminal: number;
  duration: string;
  criticalPath: string;
};

export type AuditReportModel = {
  title: string;
  domain: string;
  targetUrl: string;
  query: string;
  generatedAt: string;
  createdAt: string;
  statusLabel: string;
  scoreLabel: string;
  scoreVerdict: string;
  scoreBreakdown: {
    finalScore: string;
    ruleScore: string;
    mlScore: string;
    methodology: string;
  };
  lowScoreReason: AuditLowScoreReason;
  recoveryActions: string[];
  summary: string[];
  seoMetrics: ReportMetric[];
  recommendationMetrics: ReportMetric[];
  competitorMetrics: ReportMetric[];
  runtimeMetrics: ReportMetric[];
  recommendationActions: ReportRecommendation[];
  groupSummaries: ReportMetric[];
  competitors: Array<{
    domain: string;
    url: string;
    score: string;
    status: string;
  }>;
  stageRows: ReportStageRow[];
};

const statusLabels: Record<AuditStatus, string> = {
  queued: "Запускается",
  processing: "Обработка",
  completed: "Завершён",
  completed_with_warnings: "Завершён с предупреждениями",
  failed: "Ошибка",
};

const priorityLabels = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
} as const;

const groupStatusLabels = {
  critical: "Критично",
  attention: "Требует внимания",
  monitor: "Есть точки роста",
  competitive: "Конкурентно",
  not_enough_data: "Недостаточно данных",
} as const;

const stageLabels: Record<string, string> = {
  fetch: "Загрузка целевой страницы",
  heavy_analysis: "Углублённый анализ",
  features: "Проверка страницы",
  scoring: "Расчёт оценки",
  competitors: "Поиск конкурентов",
  competitor_page: "Загрузка конкурентов",
  competitor_analysis: "Анализ конкурентов",
  competitor_aggregation: "Сводка конкурентов",
  recommendations: "Формирование рекомендаций",
  finalize: "Финализация",
  pipeline: "Конвейер аудита",
};

function getDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatDateTime(value: Date | string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return String(Math.round(value * 10) / 10);
}

function formatSignedScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function formatSignalScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  if (value >= 0 && value <= 1) {
    return `${Math.round(value * 100)}%`;
  }
  return formatScore(value);
}

function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return String(Math.round(value));
}

export function formatReportDuration(ms: number | null | undefined): string {
  if (typeof ms !== "number" || Number.isNaN(ms)) {
    return "—";
  }
  if (ms < 1000) {
    return `${Math.round(ms)} мс`;
  }
  if (ms < 60_000) {
    return `${Math.round(ms / 100) / 10} с`;
  }
  return `${Math.round(ms / 6000) / 10} мин`;
}

function getStatusLabel(status: AuditStatus): string {
  return statusLabels[status] ?? status;
}

function getStageLabel(stage: string | null | undefined): string {
  if (!stage) {
    return "—";
  }
  return stageLabels[stage] ?? stage;
}

function getRecordNumber(record: Record<string, unknown> | null | undefined, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getRecordString(record: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function getScoreVerdict(score: number | null | undefined): string {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "Итоговая оценка ещё не рассчитана. Отчёт можно открыть, но выводы появятся после завершения аудита.";
  }
  if (score >= 80) {
    return "Страница хорошо подходит под запрос и выглядит конкурентоспособной: дальше важны точечные улучшения.";
  }
  if (score >= 60) {
    return "Страница в целом отвечает запросу, но видны зоны роста относительно конкурентов.";
  }
  return "Страница слабо закрывает запрос или заметно уступает конкурентам по важным для пользователя элементам.";
}

function getScoreBreakdown(
  results: AuditResultsResponse | null,
  audit: AuditStatusResponse,
  lowScoreReason: AuditLowScoreReason,
) {
  const breakdown = results?.score_breakdown ?? audit.score_breakdown ?? null;
  if (lowScoreReason.isBlocking || lowScoreReason.category === "query_mismatch") {
    return {
      finalScore: formatScore(breakdown?.final_score ?? results?.score ?? audit.score),
      ruleScore: lowScoreReason.isBlocking ? "—" : formatScore(breakdown?.rule_score),
      mlScore: lowScoreReason.isBlocking ? "—" : formatScore(breakdown?.ml_score),
      methodology: lowScoreReason.message,
    };
  }

  const earlyStopView = getEarlyStopMismatchView(breakdown);
  if (earlyStopView) {
    return {
      finalScore: formatScore(breakdown?.final_score ?? earlyStopView.score ?? results?.score ?? audit.score),
      ruleScore: "—",
      mlScore: "—",
      methodology: earlyStopView.message,
    };
  }

  const competitiveness = breakdown?.competitiveness;
  const hasCompetitivenessContext = Boolean(
    competitiveness &&
      typeof competitiveness === "object" &&
      "context_available" in competitiveness &&
      competitiveness.context_available === true,
  );
  return {
    finalScore: formatScore(breakdown?.final_score ?? results?.score ?? audit.score),
    ruleScore: formatScore(breakdown?.rule_score),
    mlScore: formatScore(breakdown?.ml_score),
    methodology:
      breakdown?.methodology ??
      (hasCompetitivenessContext
        ? "Итоговая оценка показывает, насколько страница подходит под запрос и выглядит сильной на фоне обработанных конкурентов из выдачи."
        : "Итоговая оценка сначала показывает, насколько сама страница отвечает запросу. Сравнение с конкурентами появится после обработки страниц из выдачи."),
  };
}

function getReportComparisonSummary(input: AuditReportInput) {
  return input.results?.comparison_summary ?? input.audit.comparison_summary ?? null;
}

function getReportScoreBreakdown(input: AuditReportInput) {
  return input.results?.score_breakdown ?? input.audit.score_breakdown ?? null;
}

function getReportCompetitivenessMetric(input: AuditReportInput, key: string): number | null {
  const competitiveness = getReportScoreBreakdown(input)?.competitiveness;
  return getRecordNumber(competitiveness, key);
}

function getReportFinalScore(input: AuditReportInput): number | null {
  const summary = getReportComparisonSummary(input);
  const breakdown = getReportScoreBreakdown(input);
  return (
    breakdown?.final_score ??
    breakdown?.competitiveness_score ??
    input.results?.score ??
    input.audit.score ??
    summary?.competitiveness_score ??
    summary?.user_score ??
    null
  );
}

function getReportPrimaryScore(input: AuditReportInput): number | null {
  const summary = getReportComparisonSummary(input);
  const breakdown = getReportScoreBreakdown(input);
  return breakdown?.primary_page_score ?? summary?.primary_page_score ?? getReportFinalScore(input);
}

function getReportCompetitorAverageScore(input: AuditReportInput): number | null {
  const summary = getReportComparisonSummary(input);
  return getReportCompetitivenessMetric(input, "competitor_average_score") ?? summary?.competitors_average_score ?? null;
}

function getReportMarketDifference(input: AuditReportInput): number | null {
  const finalScore = getReportFinalScore(input);
  const averageScore = getReportCompetitorAverageScore(input);
  if (typeof finalScore === "number" && typeof averageScore === "number") {
    return finalScore - averageScore;
  }
  return getReportComparisonSummary(input)?.score_difference ?? null;
}

function buildSeoMetrics(input: AuditReportInput): ReportMetric[] {
  const features = input.results?.features ?? input.audit.features ?? {};
  const queryIntent = input.results?.query_intent ?? input.audit.query_intent ?? null;
  const snapshot = input.results?.target_snapshot_summary ?? null;
  const heavyAnalysis = input.results?.heavy_analysis ?? input.audit.heavy_analysis ?? null;

  return [
    {
      label: "Намерение запроса",
      value: getIntentLabel(getRecordString(queryIntent, "label")),
      note: "Тип поискового намерения, с которым сверяется посадочная страница.",
    },
    {
      label: "Техническое SEO",
      value: formatSignalScore(getRecordNumber(features, "technical_seo_score")),
      note: "Индексируемость, canonical, метаданные, редиректы и техническая пригодность.",
    },
    {
      label: "Коммерция и доверие",
      value: formatSignalScore(getRecordNumber(features, "commercial_trust_score")),
      note: "Контакты, призывы к действию, условия, доказательства доверия и коммерческая полнота.",
    },
    {
      label: "Смысловое соответствие",
      value: formatSignalScore(getRecordNumber(features, "semantic_similarity")),
      note: "Насколько содержание страницы отвечает введённому запросу.",
    },
    {
      label: "Соответствие намерению",
      value: formatSignalScore(getRecordNumber(features, "intent_alignment_score")),
      note: "Соответствие страницы доминирующему поисковому намерению.",
    },
    {
      label: "Статус снимка страницы",
      value: String(snapshot?.status_code ?? "—"),
      note: `Способ загрузки: ${getFetchMethodLabel(String(snapshot?.fetch_method ?? input.results?.target_fetch_method ?? input.audit.target_fetch_method ?? ""))}`,
    },
    {
      label: "Углублённый анализ",
      value: heavyAnalysis ? "Есть" : "—",
      note: "Углублённые сигналы сохранены как часть распределённого конвейера.",
    },
  ];
}

function buildRecommendationMetrics(
  recommendations: RecommendationsBundle | null,
  lowScoreReason: AuditLowScoreReason,
): ReportMetric[] {
  if (lowScoreReason.isBlocking) {
    return [
      {
        label: "Главный план",
        value: "Восстановить доступ",
        note: "Обычные SEO-рекомендации не являются главным выводом, пока целевая страница не открывается.",
      },
      {
        label: "Действий восстановления",
        value: formatCount(lowScoreReason.recoveryActions.length),
        note: "Проверьте URL, редирект, доступность и индексируемость.",
      },
    ];
  }

  const summary = recommendations?.summary;
  return [
    {
      label: "Всего рекомендаций",
      value: formatCount(summary?.total_recommendations),
      note: "Все действия, сгруппированные по SEO-направлениям.",
    },
    {
      label: "Высокий приоритет",
      value: formatCount(summary?.high_priority_count),
      note: "Что стоит исправлять первым.",
    },
    {
      label: "Проблемных групп",
      value: formatCount(summary?.groups_with_issues),
      note: "Сколько блоков анализа требуют внимания.",
    },
    {
      label: "Разница с конкурентами",
      value: formatSignedScore(summary?.score_gap_vs_competitors),
      note: summary?.competitor_context ? "Показывает отрыв или отставание от найденных страниц." : "Недостаточно данных по конкурентам.",
    },
  ];
}

function getEffectiveRecommendations(input: AuditReportInput): RecommendationsBundle | null {
  return input.recommendations ?? input.audit.recommendations ?? null;
}

function buildCompetitorMetrics(input: AuditReportInput): ReportMetric[] {
  const earlyStopView = getEarlyStopMismatchView(getReportScoreBreakdown(input));
  if (earlyStopView) {
    return [
      {
        label: "Конкурентный контекст",
        value: "Не запускалось",
        note: earlyStopView.message,
      },
      {
        label: "Причина",
        value: earlyStopView.title,
      },
    ];
  }

  const summary = getReportComparisonSummary(input);
  const competitors = input.results?.competitor_results ?? input.audit.competitor_results;
  const contextStats = buildCompetitorContextStats(summary, competitors);
  const contextSummary = formatCompetitorContextSummary(contextStats);
  const found = contextStats.collected;
  const analyzed = contextStats.accepted;
  const failed = contextStats.failed;
  const finalScore = getReportFinalScore(input);
  const primaryScore = getReportPrimaryScore(input);
  const averageScore = getReportCompetitorAverageScore(input);
  const marketDifference = getReportMarketDifference(input);

  return [
    {
      label: "Конкурентная оценка",
      value: formatScore(finalScore),
    },
    {
      label: "Оценка самой страницы",
      value: formatScore(primaryScore),
    },
    {
      label: "Средняя оценка конкурентов",
      value: formatScore(averageScore),
    },
    {
      label: "Разница",
      value: formatSignedScore(marketDifference),
      note: "Положительное значение означает преимущество целевой страницы.",
    },
    {
      label: "Конкуренты",
      value: `${analyzed}/${found}`,
      note:
        contextSummary ??
        (failed > 0 ? `${failed} страниц не удалось обработать автоматически.` : "Все найденные конкуренты обработаны."),
    },
  ];
}

function buildRuntimeMetrics(diagnostics: AuditTimelineDiagnosticsResponse | null): ReportMetric[] {
  return [
    {
      label: "События таймлайна",
      value: formatCount(diagnostics?.event_count),
      note: "События распределённого конвейера аудита.",
    },
    {
      label: "Отправлено этапов",
      value: formatCount(diagnostics?.dispatch_count),
      note: "Сколько задач этапов было отправлено в очереди.",
    },
    {
      label: "Общее время",
      value: formatReportDuration(diagnostics?.total_duration_ms),
      note: "Время между первым и последним событием выбранной обработки.",
    },
    {
      label: "Критический путь",
      value: formatReportDuration(diagnostics?.critical_path_duration_ms),
      note: diagnostics?.terminal_stage ? `Финальный этап: ${getStageLabel(diagnostics.terminal_stage)}.` : undefined,
    },
  ];
}

function buildRecommendationActions(
  recommendations: RecommendationsBundle | null,
  lowScoreReason: AuditLowScoreReason,
): ReportRecommendation[] {
  if (lowScoreReason.isBlocking) {
    return [];
  }

  return flattenRecommendationItems(recommendations).map((item) => ({
    code: item.code,
    groupLabel: item.groupLabel,
    priorityLabel: priorityLabels[item.priority],
    title: item.title,
    message: item.message,
    expectedOutcome: item.expected_outcome,
  }));
}

function buildGroupSummaries(
  recommendations: RecommendationsBundle | null,
  lowScoreReason: AuditLowScoreReason,
): ReportMetric[] {
  if (lowScoreReason.isBlocking) {
    return [
      {
        label: "Доступность страницы",
        value: "Требует восстановления",
        note: "Сначала страница должна открываться и быть доступной для индексации.",
      },
    ];
  }

  return (recommendations?.groups ?? []).map((group) => ({
    label: getRecommendationGroupLabel(group.key),
    value: groupStatusLabels[group.status],
    note: `${group.items.length} рекомендаций, ${group.deviations.length} отклонений от конкурентов.`,
  }));
}

function buildCompetitorRows(competitors: CompetitorResult[] | null | undefined) {
  return getAcceptedCompetitors(competitors).map((competitor) => ({
    domain: competitor.domain || getDomainFromUrl(competitor.url),
    url: competitor.url,
    score: formatScore(competitor.score),
    status: competitor.fetch_status === "success" ? "Обработан" : competitor.fetch_error_message ?? "Недоступен",
  }));
}

function buildStageRows(diagnostics: AuditTimelineDiagnosticsResponse | null): ReportStageRow[] {
  return (diagnostics?.stage_breakdown ?? []).map((stage) => ({
    stage: getStageLabel(stage.stage),
    completed: stage.completed_count,
    failed: stage.failed_count + stage.aborted_count,
    terminal: stage.terminal_count,
    duration: formatReportDuration(stage.total_duration_ms),
    criticalPath: formatReportDuration(stage.critical_path_duration_ms),
  }));
}

export function buildAuditReportModel(input: AuditReportInput): AuditReportModel {
  const generatedAt = input.generatedAt ?? new Date();
  const score = getReportFinalScore(input);
  const lowScoreReason = buildAuditLowScoreReason(input);
  const scoreBreakdown = getScoreBreakdown(input.results, input.audit, lowScoreReason);
  const earlyStopView = getEarlyStopMismatchView(getReportScoreBreakdown(input));
  const comparisonSummary = getReportComparisonSummary(input);
  const marketDifference = getReportMarketDifference(input);
  const recommendations = getEffectiveRecommendations(input);
  const recommendationsSummary = recommendations?.summary ?? null;
  const domain = getDomainFromUrl(input.audit.target_url);
  const competitorContextStats = buildCompetitorContextStats(
    comparisonSummary,
    input.results?.competitor_results ?? input.audit.competitor_results,
  );
  const competitorContextSummary = formatCompetitorContextSummary(competitorContextStats);
  const competitorContextSummaryText = competitorContextSummary?.replace(/\.$/, "");
  const analyzedCompetitors = competitorContextStats.accepted;

  return {
    title: `SEO-отчёт: ${domain}`,
    domain,
    targetUrl: input.audit.target_url,
    query: input.audit.query,
    generatedAt: formatDateTime(generatedAt),
    createdAt: formatDateTime(input.audit.created_at),
    statusLabel: getStatusLabel(input.audit.status),
    scoreLabel: formatScore(score),
    scoreVerdict: lowScoreReason.kind !== "unknown" ? lowScoreReason.title : earlyStopView?.title ?? getScoreVerdict(score),
    scoreBreakdown,
    lowScoreReason,
    recoveryActions: lowScoreReason.recoveryActions,
    summary: lowScoreReason.kind !== "unknown"
      ? [
          `Аудит по запросу "${input.audit.query}" для ${domain}.`,
          lowScoreReason.title,
          lowScoreReason.message,
          ...(lowScoreReason.recoveryActions.length > 0
            ? [`Что сделать: ${lowScoreReason.recoveryActions.join(" ")}`]
            : []),
        ]
      : earlyStopView
      ? [
          `Аудит по запросу "${input.audit.query}" для ${domain}.`,
          earlyStopView.title,
          earlyStopView.message,
        ]
      : [
          `Аудит по запросу "${input.audit.query}" для ${domain}.`,
          `Итоговая оценка: ${formatScore(score)}. ${getScoreVerdict(score)}`,
          `Конкурентный контекст: ${
            competitorContextSummaryText ?? `обработано ${analyzedCompetitors} страниц`
          }, разница с конкурентами ${formatSignedScore(
            marketDifference,
          )}.`,
          `Рекомендации: ${formatCount(recommendationsSummary?.total_recommendations)} всего, ${formatCount(
            recommendationsSummary?.high_priority_count,
          )} высокого приоритета.`,
          `Распределённое выполнение: ${formatCount(input.diagnostics?.event_count)} событий таймлайна, критический путь ${formatReportDuration(
            input.diagnostics?.critical_path_duration_ms,
          )}.`,
        ],
    seoMetrics: buildSeoMetrics(input),
    recommendationMetrics: buildRecommendationMetrics(recommendations, lowScoreReason),
    competitorMetrics: buildCompetitorMetrics(input),
    runtimeMetrics: buildRuntimeMetrics(input.diagnostics),
    recommendationActions: buildRecommendationActions(recommendations, lowScoreReason),
    groupSummaries: buildGroupSummaries(recommendations, lowScoreReason),
    competitors: buildCompetitorRows(input.results?.competitor_results ?? input.audit.competitor_results),
    stageRows: buildStageRows(input.diagnostics),
  };
}

function renderMetricMarkdown(metric: ReportMetric): string {
  return `- ${metric.label}: ${metric.value}${metric.note ? ` (${metric.note})` : ""}`;
}

export function createAuditReportMarkdown(input: AuditReportInput): string {
  const report = buildAuditReportModel(input);
  const recommendationActions =
    report.recoveryActions.length > 0
      ? report.recoveryActions.map((action) => `- ${action}`).join("\n")
      : report.recommendationActions.length > 0
      ? report.recommendationActions
          .map(
            (item) =>
              `- [${item.priorityLabel}] ${item.title} (${item.groupLabel}, код ${item.code}): ${item.message} Ожидаемый эффект: ${item.expectedOutcome}`,
          )
          .join("\n")
      : "- Рекомендации пока не сформированы.";
  const groupSummaries =
    report.groupSummaries.length > 0
      ? report.groupSummaries.map(renderMetricMarkdown).join("\n")
      : "- Группы рекомендаций пока не сформированы.";
  const competitors =
    report.competitors.length > 0
      ? report.competitors
          .map((competitor) => `- ${competitor.domain}: оценка ${competitor.score}, статус ${competitor.status}, ${competitor.url}`)
          .join("\n")
      : "- Конкурентные страницы пока не обработаны.";
  const stages =
    report.stageRows.length > 0
      ? report.stageRows
          .map(
            (stage) =>
              `- ${stage.stage}: завершено ${stage.completed}, ошибок ${stage.failed}, длительность ${stage.duration}, критический путь ${stage.criticalPath}`,
          )
          .join("\n")
      : "- Диагностика таймлайна пока недоступна.";

  return [
    `# ${report.title}`,
    "",
    `Сформирован: ${report.generatedAt}`,
    `Аудит создан: ${report.createdAt}`,
    `Статус: ${report.statusLabel}`,
    `Запрос: ${report.query}`,
    `Целевая страница: ${report.targetUrl}`,
    "",
    "## Краткий вывод",
    ...report.summary.map((item) => `- ${item}`),
    "",
    "## Объяснение оценки",
    `- Итоговая оценка: ${report.scoreBreakdown.finalScore}`,
    `- Пояснение: ${report.scoreBreakdown.methodology}`,
    "",
    "## Ключевые проверки страницы",
    ...report.seoMetrics.map(renderMetricMarkdown),
    "",
    "## Конкурентный контекст",
    ...report.competitorMetrics.map(renderMetricMarkdown),
    "",
    "## План рекомендаций",
    ...report.recommendationMetrics.map(renderMetricMarkdown),
    "",
    "### Группы рекомендаций",
    groupSummaries,
    "",
    "### Список действий",
    recommendationActions,
    "",
    "## Страницы конкурентов",
    competitors,
    "",
    "## Доказательство распределённого выполнения",
    ...report.runtimeMetrics.map(renderMetricMarkdown),
    "",
    "### Разбор этапов",
    stages,
    "",
  ].join("\n");
}

export function buildAuditReportFilename(audit: AuditStatusResponse, extension: "html" | "md"): string {
  const domain = getDomainFromUrl(audit.target_url)
    .toLowerCase()
    .replace(/[^a-z0-9а-яё.-]+/gi, "-")
    .replace(/^-+|-+$/g, "");
  const date = audit.created_at.slice(0, 10) || "audit";
  return `site-audit-report-${domain || "target"}-${date}.${extension}`;
}
