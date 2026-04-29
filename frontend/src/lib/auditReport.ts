import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  CompetitorResult,
  RecommendationsBundle,
} from "../types";
import { flattenRecommendationItems } from "./recommendations";

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
  topRecommendations: ReportRecommendation[];
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
  fetch: "Target fetch",
  heavy_analysis: "Heavy analysis",
  features: "Feature extraction",
  scoring: "Scoring",
  competitors: "SERP competitors",
  competitor_page: "Competitor fetch",
  competitor_analysis: "Competitor analysis",
  recommendations: "Recommendations",
  finalize: "Finalize",
  pipeline: "Pipeline",
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
    return "Score ещё не рассчитан. Отчёт можно открыть, но итоговые выводы появятся после завершения аудита.";
  }
  if (score >= 80) {
    return "Страница выглядит конкурентоспособной: дальше важны точечные улучшения и удержание сильных факторов.";
  }
  if (score >= 60) {
    return "Страница находится в рабочем диапазоне, но видны зоны роста относительно лидеров выдачи.";
  }
  return "Страница заметно отстаёт по совокупности SEO, semantic, commercial/trust и competitor-relative сигналов.";
}

function getScoreBreakdown(results: AuditResultsResponse | null, audit: AuditStatusResponse) {
  const breakdown = results?.score_breakdown ?? audit.score_breakdown ?? null;
  return {
    breakdown,
    finalScore: formatScore(breakdown?.final_score ?? results?.score ?? audit.score),
    ruleScore: formatScore(breakdown?.rule_score),
    mlScore: formatScore(breakdown?.ml_score),
    methodology:
      breakdown?.methodology ??
      "Гибридная оценка: rule-based SEO/semantic факторы дополняются ML-калибровкой по сохранённым признакам страницы.",
  };
}

function buildSeoMetrics(input: AuditReportInput): ReportMetric[] {
  const features = input.results?.features ?? input.audit.features ?? {};
  const queryIntent = input.results?.query_intent ?? input.audit.query_intent ?? null;
  const snapshot = input.results?.target_snapshot_summary ?? null;
  const heavyAnalysis = input.results?.heavy_analysis ?? input.audit.heavy_analysis ?? null;

  return [
    {
      label: "Feature schema",
      value: input.results?.feature_schema_version ?? input.audit.feature_schema_version ?? "—",
      note: "Версия набора признаков, по которому построен score.",
    },
    {
      label: "Query intent",
      value: getRecordString(queryIntent, "label") ?? "—",
      note: "Тип поискового намерения, с которым сверяется посадочная страница.",
    },
    {
      label: "Technical SEO",
      value: formatSignalScore(getRecordNumber(features, "technical_seo_score")),
      note: "Индексируемость, canonical, metadata, redirects и техническая пригодность.",
    },
    {
      label: "Commercial / trust",
      value: formatSignalScore(getRecordNumber(features, "commercial_trust_score")),
      note: "Контакты, CTA, условия, доказательства доверия и коммерческая полнота.",
    },
    {
      label: "Semantic relevance",
      value: formatSignalScore(getRecordNumber(features, "semantic_similarity")),
      note: "Насколько текст страницы соответствует поисковому запросу.",
    },
    {
      label: "Intent alignment",
      value: formatSignalScore(getRecordNumber(features, "intent_alignment_score")),
      note: "Соответствие страницы доминирующему intent запроса.",
    },
    {
      label: "Snapshot status",
      value: String(snapshot?.status_code ?? "—"),
      note: `Fetch: ${String(snapshot?.fetch_method ?? input.results?.target_fetch_method ?? input.audit.target_fetch_method ?? "—")}`,
    },
    {
      label: "Heavy analysis",
      value: heavyAnalysis ? "Есть" : "—",
      note: "Snapshot-based тяжёлые analyzer-сигналы сохранены как часть distributed pipeline.",
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
      label: "Gap vs competitors",
      value: formatSignedScore(summary?.score_gap_vs_competitors),
      note: summary?.competitor_context ? "Расчёт использует competitor-relative evidence." : "Недостаточно competitor context.",
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
      label: "Score target",
      value: formatScore(summary?.user_score ?? input.results?.score ?? input.audit.score),
    },
    {
      label: "Средний score конкурентов",
      value: formatScore(summary?.competitors_average_score),
    },
    {
      label: "Разница",
      value: formatSignedScore(summary?.score_difference),
      note: "Положительное значение означает преимущество target.",
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
      label: "Timeline events",
      value: formatCount(diagnostics?.event_count),
      note: "События распределённого audit pipeline.",
    },
    {
      label: "Dispatch events",
      value: formatCount(diagnostics?.dispatch_count),
      note: "Сколько stage-задач было отправлено в очереди.",
    },
    {
      label: "Total duration",
      value: formatReportDuration(diagnostics?.total_duration_ms),
      note: "Время между первым и последним событием выбранной обработки.",
    },
    {
      label: "Critical path",
      value: formatReportDuration(diagnostics?.critical_path_duration_ms),
      note: diagnostics?.terminal_stage ? `Финальный этап: ${getStageLabel(diagnostics.terminal_stage)}.` : undefined,
    },
  ];
}

function buildTopRecommendations(recommendations: RecommendationsBundle | null): ReportRecommendation[] {
  return flattenRecommendationItems(recommendations)
    .slice(0, 5)
    .map((item) => ({
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
    label: group.label,
    value: groupStatusLabels[group.status],
    note: `${group.items.length} рекомендаций, ${group.deviations.length} competitor-relative отклонений.`,
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
  const comparisonSummary = input.results?.comparison_summary ?? input.audit.comparison_summary ?? null;
  const recommendations = getEffectiveRecommendations(input);
  const recommendationsSummary = recommendations?.summary ?? null;
  const domain = getDomainFromUrl(input.audit.target_url);
  const analyzedCompetitors =
    comparisonSummary?.competitors_analyzed ??
    comparisonSummary?.competitors_count ??
    input.results?.competitor_results?.filter((competitor) => competitor.fetch_status === "success").length ??
    0;

  return {
    title: `SEO audit report: ${domain}`,
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
      `Итоговый score: ${formatScore(score)}. ${getScoreVerdict(score)}`,
      `Competitor context: обработано ${analyzedCompetitors} страниц, gap target vs competitors ${formatSignedScore(
        comparisonSummary?.score_difference,
      )}.`,
      `Рекомендации: ${formatCount(recommendationsSummary?.total_recommendations)} всего, ${formatCount(
        recommendationsSummary?.high_priority_count,
      )} высокого приоритета.`,
      `Distributed evidence: ${formatCount(input.diagnostics?.event_count)} timeline events, critical path ${formatReportDuration(
        input.diagnostics?.critical_path_duration_ms,
      )}.`,
    ],
    seoMetrics: buildSeoMetrics(input),
    recommendationMetrics: buildRecommendationMetrics(recommendations),
    competitorMetrics: buildCompetitorMetrics(input),
    runtimeMetrics: buildRuntimeMetrics(input.diagnostics),
    topRecommendations: buildTopRecommendations(recommendations),
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
  const topRecommendations =
    report.topRecommendations.length > 0
      ? report.topRecommendations
          .map(
            (item) =>
              `- [${item.priorityLabel}] ${item.title} (${item.groupLabel}, ${item.code}): ${item.message} Expected: ${item.expectedOutcome}`,
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
          .map((competitor) => `- ${competitor.domain}: score ${competitor.score}, status ${competitor.status}, ${competitor.url}`)
          .join("\n")
      : "- Конкурентные страницы пока не обработаны.";
  const stages =
    report.stageRows.length > 0
      ? report.stageRows
          .map(
            (stage) =>
              `- ${stage.stage}: completed ${stage.completed}, failed ${stage.failed}, duration ${stage.duration}, critical path ${stage.criticalPath}`,
          )
          .join("\n")
      : "- Timeline diagnostics пока недоступны.";

  return [
    `# ${report.title}`,
    "",
    `Generated: ${report.generatedAt}`,
    `Audit created: ${report.createdAt}`,
    `Status: ${report.statusLabel}`,
    `Query: ${report.query}`,
    `Target URL: ${report.targetUrl}`,
    "",
    "## Executive Summary",
    ...report.summary.map((item) => `- ${item}`),
    "",
    "## Score And ML Explanation",
    `- Final score: ${report.scoreBreakdown.finalScore}`,
    `- Rule-based score: ${report.scoreBreakdown.ruleScore}`,
    `- ML score: ${report.scoreBreakdown.mlScore}`,
    `- Methodology: ${report.scoreBreakdown.methodology}`,
    "",
    "## SEO Evidence",
    ...report.seoMetrics.map(renderMetricMarkdown),
    "",
    "## Competitor Evidence",
    ...report.competitorMetrics.map(renderMetricMarkdown),
    "",
    "## Recommendation Plan",
    ...report.recommendationMetrics.map(renderMetricMarkdown),
    "",
    "### Recommendation Groups",
    groupSummaries,
    "",
    "### Top Actions",
    topRecommendations,
    "",
    "## Competitor Pages",
    competitors,
    "",
    "## Distributed Runtime Evidence",
    ...report.runtimeMetrics.map(renderMetricMarkdown),
    "",
    "### Stage Breakdown",
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
