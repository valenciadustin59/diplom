import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  CompetitorResult,
  RecommendationsBundle,
} from "../types";
import { buildScoreConfidenceView, type ScoreConfidenceView } from "./auditConfidence";
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
  summary: string[];
  seoMetrics: ReportMetric[];
  recommendationMetrics: ReportMetric[];
  competitorMetrics: ReportMetric[];
  runtimeMetrics: ReportMetric[];
  modelMetrics: ReportMetric[];
  scoreConfidence: ScoreConfidenceView;
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
  features: "Извлечение признаков",
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
    return "Страница выглядит конкурентоспособной: дальше важны точечные улучшения и удержание сильных факторов.";
  }
  if (score >= 60) {
    return "Страница находится в рабочем диапазоне, но видны зоны роста относительно лидеров выдачи.";
  }
  return "Страница заметно отстаёт по совокупности SEO, смысловых, коммерческих, доверительных и конкурентных сигналов.";
}

function getScoreBreakdown(results: AuditResultsResponse | null, audit: AuditStatusResponse) {
  const breakdown = results?.score_breakdown ?? audit.score_breakdown ?? null;
  return {
    breakdown,
    modelInfo: breakdown?.model_info ?? null,
    finalScore: formatScore(breakdown?.final_score ?? results?.score ?? audit.score),
    ruleScore: formatScore(breakdown?.rule_score),
    mlScore: formatScore(breakdown?.ml_score),
    methodology:
      breakdown?.methodology ??
      "Итоговая оценка рассчитывается опубликованной ML-моделью по признакам самой страницы и её соответствию запросу. Конкурентный контекст используется отдельно для сравнения и рекомендаций; факторы ниже не складываются в финальный score.",
  };
}

function getModelMetric(modelInfo: Record<string, unknown> | null, key: string): number | null {
  const metrics = modelInfo?.metrics_summary;
  if (!metrics || typeof metrics !== "object" || Array.isArray(metrics)) {
    return null;
  }
  const value = (metrics as Record<string, unknown>)[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildModelMetrics(modelInfo: Record<string, unknown> | null): ReportMetric[] {
  if (!modelInfo) {
    return [];
  }

  const modelType = getRecordString(modelInfo, "model_type") ?? "—";
  const schema = getRecordString(modelInfo, "model_schema_version") ?? "—";
  const dataset = getRecordString(modelInfo, "dataset_version") ?? "—";
  const artifact = getRecordString(modelInfo, "artifact_version") ?? "—";
  const featureCount = getRecordNumber(modelInfo, "feature_count");
  const datasetRows = getRecordNumber(modelInfo, "dataset_rows");

  return [
    {
      label: "Активная модель",
      value: `${modelType} · ${schema}`,
      note: "Runtime artifact, который считал score этого аудита.",
    },
    {
      label: "Датасет модели",
      value: dataset,
      note: `${formatCount(datasetRows)} строк, ${formatCount(featureCount)} признаков.`,
    },
    {
      label: "Artifact",
      value: artifact,
      note: "Версия опубликованного файла модели.",
    },
    {
      label: "Top-3 / NDCG / MAE",
      value: `${formatSignalScore(getModelMetric(modelInfo, "top_3_hit_rate"))} · ${formatScore(getModelMetric(modelInfo, "ndcg_at_10"))} · ${formatScore(getModelMetric(modelInfo, "mae"))}`,
      note: "Ключевые offline-метрики publish guardrail.",
    },
  ];
}

function buildSeoMetrics(input: AuditReportInput): ReportMetric[] {
  const features = input.results?.features ?? input.audit.features ?? {};
  const queryIntent = input.results?.query_intent ?? input.audit.query_intent ?? null;
  const snapshot = input.results?.target_snapshot_summary ?? null;
  const heavyAnalysis = input.results?.heavy_analysis ?? input.audit.heavy_analysis ?? null;

  return [
    {
      label: "Версия признаков",
      value: input.results?.feature_schema_version ?? input.audit.feature_schema_version ?? "—",
      note: "Версия набора признаков, по которому построена итоговая оценка.",
    },
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
      note: "Насколько текст страницы соответствует поисковому запросу.",
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

function buildRecommendationMetrics(recommendations: RecommendationsBundle | null): ReportMetric[] {
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
      note: summary?.competitor_context ? "Расчёт учитывает сравнение с конкурентами." : "Недостаточно данных по конкурентам.",
    },
  ];
}

function getEffectiveRecommendations(input: AuditReportInput): RecommendationsBundle | null {
  return input.recommendations ?? input.audit.recommendations ?? null;
}

function buildCompetitorMetrics(input: AuditReportInput): ReportMetric[] {
  const summary = input.results?.comparison_summary ?? input.audit.comparison_summary ?? null;
  const found = summary?.competitors_found ?? summary?.competitors_count ?? 0;
  const analyzed = summary?.competitors_analyzed ?? summary?.competitors_count ?? 0;
  const failed = summary?.competitors_failed ?? Math.max(0, found - analyzed);

  return [
    {
      label: "Оценка страницы",
      value: formatScore(summary?.user_score ?? input.results?.score ?? input.audit.score),
    },
    {
      label: "Средняя оценка конкурентов",
      value: formatScore(summary?.competitors_average_score),
    },
    {
      label: "Разница",
      value: formatSignedScore(summary?.score_difference),
      note: "Положительное значение означает преимущество целевой страницы.",
    },
    {
      label: "Конкуренты",
      value: `${analyzed}/${found}`,
      note: failed > 0 ? `${failed} страниц не удалось обработать автоматически.` : "Все найденные конкуренты обработаны.",
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

function buildRecommendationActions(recommendations: RecommendationsBundle | null): ReportRecommendation[] {
  return flattenRecommendationItems(recommendations).map((item) => ({
    code: item.code,
    groupLabel: item.groupLabel,
    priorityLabel: priorityLabels[item.priority],
    title: item.title,
    message: item.message,
    expectedOutcome: item.expected_outcome,
  }));
}

function buildGroupSummaries(recommendations: RecommendationsBundle | null): ReportMetric[] {
  return (recommendations?.groups ?? []).map((group) => ({
    label: getRecommendationGroupLabel(group.key),
    value: groupStatusLabels[group.status],
    note: `${group.items.length} рекомендаций, ${group.deviations.length} отклонений от конкурентов.`,
  }));
}

function buildCompetitorRows(competitors: CompetitorResult[] | null | undefined) {
  return (competitors ?? []).map((competitor) => ({
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
  const score = input.results?.score ?? input.audit.score;
  const scoreBreakdown = getScoreBreakdown(input.results, input.audit);
  const modelMetrics = buildModelMetrics(scoreBreakdown.modelInfo);
  const comparisonSummary = input.results?.comparison_summary ?? input.audit.comparison_summary ?? null;
  const recommendations = getEffectiveRecommendations(input);
  const scoreConfidence = buildScoreConfidenceView({
    audit: input.audit,
    results: input.results,
    recommendations,
    comparisonSummary,
  });
  const recommendationsSummary = recommendations?.summary ?? null;
  const domain = getDomainFromUrl(input.audit.target_url);
  const analyzedCompetitors =
    comparisonSummary?.competitors_analyzed ??
    comparisonSummary?.competitors_count ??
    input.results?.competitor_results?.filter((competitor) => competitor.fetch_status === "success").length ??
    0;

  return {
    title: `SEO-отчёт: ${domain}`,
    domain,
    targetUrl: input.audit.target_url,
    query: input.audit.query,
    generatedAt: formatDateTime(generatedAt),
    createdAt: formatDateTime(input.audit.created_at),
    statusLabel: getStatusLabel(input.audit.status),
    scoreLabel: formatScore(score),
    scoreVerdict: getScoreVerdict(score),
    scoreBreakdown,
    summary: [
      `Аудит по запросу "${input.audit.query}" для ${domain}.`,
      `Итоговая оценка: ${formatScore(score)}. ${getScoreVerdict(score)}`,
      `Конкурентный контекст: обработано ${analyzedCompetitors} страниц, разница с конкурентами ${formatSignedScore(
        comparisonSummary?.score_difference,
      )}.`,
      `Рекомендации: ${formatCount(recommendationsSummary?.total_recommendations)} всего, ${formatCount(
        recommendationsSummary?.high_priority_count,
      )} высокого приоритета.`,
      `Доверие к score: ${scoreConfidence.label}. ${scoreConfidence.summary}`,
      `Распределённое выполнение: ${formatCount(input.diagnostics?.event_count)} событий таймлайна, критический путь ${formatReportDuration(
        input.diagnostics?.critical_path_duration_ms,
      )}.`,
    ],
    seoMetrics: buildSeoMetrics(input),
    recommendationMetrics: buildRecommendationMetrics(recommendations),
    competitorMetrics: buildCompetitorMetrics(input),
    runtimeMetrics: buildRuntimeMetrics(input.diagnostics),
    modelMetrics,
    scoreConfidence,
    recommendationActions: buildRecommendationActions(recommendations),
    groupSummaries: buildGroupSummaries(recommendations),
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
    report.recommendationActions.length > 0
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
    "## Доверие к score",
    `- Уровень: ${report.scoreConfidence.label}`,
    `- Вывод: ${report.scoreConfidence.summary}`,
    `- Проверки: ${report.scoreConfidence.passedCount} ok, ${report.scoreConfidence.warningCount} warning, ${report.scoreConfidence.errorCount} error`,
    ...report.scoreConfidence.reasons.map((reason) => `- ${reason.label}: ${reason.detail}`),
    "",
    "## Объяснение оценки",
    `- Итоговая оценка: ${report.scoreBreakdown.finalScore}`,
    `- Методика: ${report.scoreBreakdown.methodology}`,
    ...(report.modelMetrics.length > 0
      ? ["", "### Статус модели", ...report.modelMetrics.map(renderMetricMarkdown)]
      : []),
    "",
    "## SEO-сигналы",
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
