import type { RuntimeModelMonitoringResponse } from "../types";
import type { RuntimeMetric, RuntimeTone } from "./runtimeHealth";

export type RuntimeModelUsageRow = {
  key: string;
  tone: RuntimeTone;
  isActiveModel: boolean;
  modelLabel: string;
  datasetLabel: string;
  artifactLabel: string;
  auditCountLabel: string;
  statusCountsLabel: string;
  warningFailureLabel: string;
  scoreLabel: string;
  competitorCoverageLabel: string;
  lastAuditAtLabel: string;
};

export type RuntimeModelMonitoringView = {
  status: string;
  statusLabel: string;
  tone: RuntimeTone;
  empty: boolean;
  shortLabel: string;
  detail: string;
  checkedAtLabel: string;
  windowLabel: string;
  legacyLabel: string;
  statusCountsLabel: string;
  summaryMetrics: RuntimeMetric[];
  scoreMetrics: RuntimeMetric[];
  competitorMetrics: RuntimeMetric[];
  usageRows: RuntimeModelUsageRow[];
};

const STATUS_LABELS: Record<string, string> = {
  ok: "в норме",
  ready: "готов",
  not_ready: "не готов",
  degraded: "деградация",
  warning: "внимание",
  error: "ошибка",
  skipped: "пропущено",
};
const AUDIT_STATUS_LABELS: Record<string, string> = {
  queued: "в очереди",
  processing: "в обработке",
  completed: "завершено",
  completed_with_warnings: "с предупреждениями",
  failed: "ошибка",
};

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "—";
}

function formatPercent(value: unknown): string {
  const numberValue = asNumber(value);
  return numberValue === null ? "—" : `${Math.round(numberValue * 100)}%`;
}

function formatDecimal(value: unknown, digits = 1): string {
  const numberValue = asNumber(value);
  return numberValue === null ? "—" : numberValue.toFixed(digits).replace(/\.?0+$/, "");
}

function formatCheckedAt(value: string | null | undefined): string {
  if (!value) {
    return "нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function getStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return "нет данных";
  }
  return STATUS_LABELS[status] ?? status;
}

function getAuditStatusLabel(status: string): string {
  return AUDIT_STATUS_LABELS[status] ?? status;
}

function getStatusTone(status: string | null | undefined): RuntimeTone {
  if (status === "ok" || status === "ready" || status === "skipped") {
    return "ok";
  }
  if (status === "warning" || status === "degraded" || status === "not_ready") {
    return "warning";
  }
  if (status === "error" || status === "stuck" || status === "backlogged") {
    return "error";
  }
  return "muted";
}

function getMonitoringStatusLabel(status: string | null | undefined): string {
  if (status === "ok") {
    return "Использование штатно";
  }
  if (status === "warning") {
    return "Есть предупреждения";
  }
  if (status === "error") {
    return "Есть ошибки аудитов";
  }
  if (status === "empty") {
    return "Нет runtime-данных";
  }
  return status ? getStatusLabel(status) : "Нет данных";
}

function getMonitoringTone(status: string | null | undefined): RuntimeTone {
  if (status === "empty") {
    return "muted";
  }
  return getStatusTone(status);
}

function buildStatusCountsLabel(statusCounts: Record<string, number> | null | undefined): string {
  const entries = Object.entries(statusCounts ?? {}).filter(([, count]) => count > 0);
  if (entries.length === 0) {
    return "нет статусов";
  }
  return entries.map(([status, count]) => `${getAuditStatusLabel(status)} ${count}`).join(", ");
}

function buildModelUsageRows(monitoring: RuntimeModelMonitoringResponse): RuntimeModelUsageRow[] {
  return monitoring.model_usage.map((usage) => {
    const score = usage.score_distribution;
    const coverage = usage.competitor_coverage;
    const tone: RuntimeTone = usage.failure_count > 0 ? "error" : usage.warning_count > 0 ? "warning" : "ok";
    const modelLabel = `${usage.model_type ?? "модель не указана"} · ${usage.model_schema_version ?? "схема не указана"}`;
    const coverageLabel =
      coverage.total_found > 0
        ? `${coverage.total_analyzed}/${coverage.total_found} проанализировано · ${formatPercent(coverage.coverage_ratio)}`
        : "конкуренты не найдены";

    return {
      key: usage.key,
      tone,
      isActiveModel: usage.is_active_model,
      modelLabel,
      datasetLabel: usage.dataset_version ?? "датасет не указан",
      artifactLabel: usage.artifact_version ?? "artifact не указан",
      auditCountLabel: formatCount(usage.audit_count),
      statusCountsLabel: buildStatusCountsLabel(usage.status_counts),
      warningFailureLabel: `${usage.warning_count} предупреждений · ${usage.failure_count} ошибок`,
      scoreLabel: `p50 ${formatDecimal(score.p50)} · avg ${formatDecimal(score.average)}`,
      competitorCoverageLabel: coverageLabel,
      lastAuditAtLabel: formatCheckedAt(usage.last_audit_at),
    };
  });
}

function buildMonitoringSummaryMetrics(monitoring: RuntimeModelMonitoringResponse): RuntimeMetric[] {
  return [
    {
      label: "Аудиты в окне",
      value: formatCount(monitoring.total_audits),
      note: `Последние ${monitoring.window_days} дней.`,
      tone: monitoring.total_audits > 0 ? "ok" : "muted",
    },
    {
      label: "С model_info",
      value: formatCount(monitoring.audits_with_model_info),
      note: "Аудиты, где score_breakdown сохранил metadata runtime-модели.",
      tone: monitoring.audits_with_model_info > 0 ? "ok" : "warning",
    },
    {
      label: "Legacy/unknown",
      value: formatCount(monitoring.legacy_or_unknown_count),
      note: "Старые записи без model_info учитываются отдельно.",
      tone: monitoring.legacy_or_unknown_count > 0 ? "warning" : "ok",
    },
    {
      label: "Warnings/failures",
      value: `${formatCount(monitoring.warning_count)}/${formatCount(monitoring.failure_count)}`,
      note: "Аудиты с предупреждениями и ошибки в выбранном окне.",
      tone: monitoring.failure_count > 0 ? "error" : monitoring.warning_count > 0 ? "warning" : "ok",
    },
  ];
}

function buildMonitoringScoreMetrics(monitoring: RuntimeModelMonitoringResponse): RuntimeMetric[] {
  const distribution = monitoring.score_distribution;
  return [
    {
      label: "Score avg",
      value: formatDecimal(distribution.average),
      note: `Активная модель, ${formatCount(distribution.sample_size)} score-сэмплов.`,
      tone: distribution.sample_size > 0 ? "ok" : "muted",
    },
    {
      label: "Score p50",
      value: formatDecimal(distribution.p50),
      note: "Медиана recent-аудитов активной модели.",
      tone: distribution.sample_size > 0 ? "ok" : "muted",
    },
    {
      label: "Низкие score",
      value: formatCount(distribution.low_score_count),
      note: `Ниже ${formatDecimal(distribution.low_score_threshold)} баллов.`,
      tone: distribution.low_score_count > 0 ? "warning" : "ok",
    },
    {
      label: "Высокие score",
      value: formatCount(distribution.high_score_count),
      note: `От ${formatDecimal(distribution.high_score_threshold)} баллов.`,
      tone: "ok",
    },
  ];
}

function buildMonitoringCompetitorMetrics(monitoring: RuntimeModelMonitoringResponse): RuntimeMetric[] {
  const coverage = monitoring.competitor_coverage;
  return [
    {
      label: "Конкуренты найдены",
      value: formatCount(coverage.total_found),
      note: `Среднее на аудит: ${formatDecimal(coverage.average_found)}.`,
      tone: coverage.total_found > 0 ? "ok" : "warning",
    },
    {
      label: "Проанализировано",
      value: formatCount(coverage.total_analyzed),
      note: `Среднее на аудит: ${formatDecimal(coverage.average_analyzed)}.`,
      tone: coverage.total_analyzed > 0 ? "ok" : "warning",
    },
    {
      label: "Ошибки конкурентов",
      value: formatCount(coverage.total_failed),
      note: `Среднее на аудит: ${formatDecimal(coverage.average_failed)}.`,
      tone: coverage.total_failed > 0 ? "warning" : "ok",
    },
    {
      label: "Coverage",
      value: formatPercent(coverage.coverage_ratio),
      note: "Доля найденных конкурентов, дошедших до анализа.",
      tone: coverage.coverage_ratio !== null && coverage.coverage_ratio >= 0.5 ? "ok" : "warning",
    },
  ];
}

export function buildModelMonitoringView(
  monitoring: RuntimeModelMonitoringResponse | null | undefined,
): RuntimeModelMonitoringView | null {
  if (!monitoring) {
    return null;
  }

  const status = asString(monitoring.status) ?? "unknown";
  const usageRows = buildModelUsageRows(monitoring);
  const activeUsage = monitoring.model_usage.find((usage) => usage.is_active_model);
  const empty = monitoring.audits_with_model_info === 0 || monitoring.status === "empty";
  const activeAuditCount = activeUsage?.audit_count ?? 0;

  return {
    status,
    statusLabel: getMonitoringStatusLabel(status),
    tone: getMonitoringTone(status),
    empty,
    shortLabel: empty
      ? "Нет аудитов с model_info"
      : `model_info в ${formatCount(monitoring.audits_with_model_info)} из ${formatCount(monitoring.total_audits)} аудитов`,
    detail: empty
      ? "За выбранное окно нет завершённых audit-записей с runtime model_info; legacy/unknown строки показаны отдельно и не ломают мониторинг."
      : activeAuditCount > 0
        ? `Активная модель найдена в ${formatCount(activeAuditCount)} recent-аудитах; score и competitor coverage рассчитаны по этим записям.`
        : "Recent-аудиты содержат model_info, но активный artifact из /health/model среди них пока не найден.",
    checkedAtLabel: formatCheckedAt(monitoring.checked_at),
    windowLabel: `${monitoring.window_days} дней · с ${formatCheckedAt(monitoring.window_start)}`,
    legacyLabel: `${formatCount(monitoring.legacy_or_unknown_count)} legacy/unknown`,
    statusCountsLabel: buildStatusCountsLabel(monitoring.status_counts),
    summaryMetrics: buildMonitoringSummaryMetrics(monitoring),
    scoreMetrics: buildMonitoringScoreMetrics(monitoring),
    competitorMetrics: buildMonitoringCompetitorMetrics(monitoring),
    usageRows,
  };
}
