import type {
  AuditEarlyStopSummary,
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEvent,
  AuditTimelineEventsResponse,
  AuditTimelineFanOut,
  AuditTimelineStageDiagnostics,
  FailureContext,
} from "../types";
import { getAuditStatusLabel, getFailureDetailEntries, getFailureStageLabel } from "./ui";

export const TIMELINE_STAGE_ORDER = [
  "pipeline",
  "fetch",
  "heavy_analysis",
  "features",
  "scoring",
  "competitors",
  "competitor_page",
  "competitor_analysis",
  "competitor_aggregation",
  "recommendations",
  "finalize",
] as const;

type TimelineStageStatus = "pending" | "dispatched" | "running" | "completed" | "failed" | "aborted";

export type TimelineMetric = {
  label: string;
  value: string;
  note?: string;
};

export type TimelineStageRow = {
  stage: string;
  label: string;
  description: string;
  status: TimelineStageStatus;
  statusLabel: string;
  queueLabel: string;
  queues: string[];
  eventCount: number;
  dispatchCount: number;
  startedCount: number;
  completedCount: number;
  failedCount: number;
  abortedCount: number;
  terminalCount: number;
  durationLabel: string;
  averageDurationLabel: string;
  maxDurationLabel: string;
  criticalPathDurationLabel: string;
  criticalPathModeLabel: string;
  isCriticalPath: boolean;
  latestEventLabel: string;
  latestEventTone: TimelineStageStatus;
  firstEventLabel: string;
  lastEventLabel: string;
};

export type TimelineFanOutModel = {
  stage: string;
  stageLabel: string;
  dispatchCount: number;
  startedCount: number;
  terminalCount: number;
  inFlightCount: number;
  branchCount: number;
  totalDurationLabel: string;
  averageDurationLabel: string;
  maxDurationLabel: string;
  criticalPathDurationLabel: string;
  note: string;
};

export type TimelineEventRow = {
  id: number;
  timestampLabel: string;
  stage: string;
  stageLabel: string;
  event: string;
  eventLabel: string;
  durationLabel: string;
  queueLabel: string;
  detailSummary: string;
  tone: TimelineStageStatus;
};

export type TimelineFailureModel = {
  stageLabel: string;
  code: string | null;
  message: string;
  details: Array<{ label: string; value: string }>;
};

export type AuditTimelineInput = {
  audit: AuditStatusResponse;
  results: AuditResultsResponse | null;
  diagnostics: AuditTimelineDiagnosticsResponse | null;
  events: AuditTimelineEventsResponse | null;
  failureContext: FailureContext | null;
};

export type AuditTimelineModel = {
  title: string;
  targetUrl: string;
  query: string;
  statusLabel: string;
  processingVersionLabel: string;
  hasData: boolean;
  rangeLabel: string;
  summaryMetrics: TimelineMetric[];
  stageRows: TimelineStageRow[];
  fanOut: TimelineFanOutModel | null;
  fanOutStages: TimelineFanOutModel[];
  eventRows: TimelineEventRow[];
  warnings: string[];
  failure: TimelineFailureModel | null;
  earlyStop: AuditEarlyStopSummary | null;
};

const TASK_STAGE_MAP: Record<string, string> = {
  "app.process_audit": "pipeline",
  "app.process_audit_fetch_target": "fetch",
  "app.process_audit_run_heavy_analysis": "heavy_analysis",
  "app.process_audit_extract_features": "features",
  "app.process_audit_score_target": "scoring",
  "app.process_audit_collect_competitors": "competitors",
  "app.process_audit_collect_competitor_page": "competitor_page",
  "app.process_audit_analyze_competitor_page": "competitor_analysis",
  "app.process_audit_aggregate_competitors": "competitor_aggregation",
  "app.process_audit_generate_recommendations": "recommendations",
  "app.process_audit_finalize": "finalize",
};

const TERMINAL_EVENTS = new Set(["completed", "failed", "aborted"]);
const FAN_OUT_STAGES = new Set(["competitor_page", "competitor_analysis"]);

const STAGE_LABELS: Record<string, string> = {
  pipeline: "Старт аудита",
  fetch: "Загрузка страницы",
  heavy_analysis: "Глубокий анализ",
  features: "Сигналы страницы",
  scoring: "Расчёт score",
  competitors: "Подбор конкурентов",
  competitor_page: "Загрузка страниц",
  competitor_analysis: "Оценка конкурентов",
  competitor_aggregation: "Сравнение",
  recommendations: "Рекомендации",
  finalize: "Готовый результат",
};

const STAGE_DESCRIPTIONS: Record<string, string> = {
  pipeline: "Запускает аудит и распределяет работу по очередям.",
  fetch: "Загружает страницу, которую проверяет пользователь.",
  heavy_analysis: "Разбирает контент, структуру, технические и смысловые сигналы страницы.",
  features: "Готовит понятные системе сигналы для расчёта оценки.",
  scoring: "Считает score страницы по запросу.",
  competitors: "Подбирает страницы из выдачи для сравнения.",
  competitor_page: "Загружает страницы конкурентов из выдачи.",
  competitor_analysis: "Считает score и основные сигналы для загруженных конкурентов.",
  competitor_aggregation: "Сравнивает целевую страницу с обработанными конкурентами.",
  recommendations: "Готовит список действий для улучшения страницы.",
  finalize: "Сохраняет итоговый статус, score и данные отчёта.",
};

const EVENT_LABELS: Record<string, string> = {
  dispatched: "Отправлено в очередь",
  started: "Запущено воркером",
  completed: "Завершено",
  failed: "Ошибка",
  aborted: "Прервано",
};

EVENT_LABELS.preflight_stop = "Остановлено по соответствию запросу";
EVENT_LABELS.preflight_continue = "Проверка соответствия пройдена";

const STAGE_STATUS_LABELS: Record<TimelineStageStatus, string> = {
  pending: "Не запущено",
  dispatched: "В очереди",
  running: "Выполняется",
  completed: "Завершено",
  failed: "Ошибка",
  aborted: "Прервано",
};

const CRITICAL_PATH_MODE_LABELS: Record<string, string> = {
  serial: "последовательный вклад",
  serial_sum: "сумма последовательных задач",
  fan_out_max: "самая долгая параллельная ветка",
};

const DETAIL_LABELS: Record<string, string> = {
  queue: "Очередь",
  status: "Статус",
  final_status: "Финальный статус",
  fetch_method: "Способ загрузки",
  fetch_status: "Статус загрузки",
  error_code: "Ошибка",
  http_status: "HTTP",
  text_length: "Длина текста",
  text_length_chars: "Символов текста",
  schema_version: "Схема",
  overall_score: "Общая оценка",
  risk_level: "Риск",
  feature_count: "Признаков",
  final_score: "Итоговая оценка",
  rule_score: "Оценка по правилам",
  ml_score: "ML-оценка",
  model_source: "Модель",
  competitors_found: "Найдено",
  competitor_tasks_planned: "Запланировано веток",
  competitors_analyzed: "Проанализировано",
  competitors_failed: "Ошибки конкурентов",
  recommendations_count: "Рекомендаций",
  warnings_count: "Предупреждений",
  competitor_id: "ID конкурента",
  domain: "Домен",
  score: "Оценка",
  semantic_similarity: "Смысловое соответствие",
  intent_alignment_score: "Соответствие намерению",
};

Object.assign(DETAIL_LABELS, {
  early_stop: "Ранняя остановка",
  early_stop_reason: "Причина остановки",
  score_floor: "Минимум score",
  score_ceiling: "Потолок score",
  safe_to_skip_competitors: "Конкуренты пропущены безопасно",
  skipped_stages: "Пропущенные этапы",
});

const PRIORITY_DETAIL_KEYS = [
  "queue",
  "status",
  "final_status",
  "fetch_method",
  "fetch_status",
  "error_code",
  "http_status",
  "domain",
  "competitor_id",
  "competitors_found",
  "competitor_tasks_planned",
  "competitors_analyzed",
  "competitors_failed",
  "feature_count",
  "overall_score",
  "final_score",
  "rule_score",
  "ml_score",
  "score",
  "recommendations_count",
  "warnings_count",
  "text_length",
  "text_length_chars",
  "schema_version",
  "model_source",
  "semantic_similarity",
  "intent_alignment_score",
  "risk_level",
] as const;

const D72_PRIORITY_DETAIL_KEYS = [
  "early_stop",
  "early_stop_reason",
  "score_floor",
  "score_ceiling",
  "safe_to_skip_competitors",
  "skipped_stages",
] as const;

const IGNORED_DETAIL_KEYS = new Set(["duration_ms"]);

const DETAIL_VALUE_LABELS: Record<string, Record<string, string>> = {
  status: {
    success: "успешно",
    failed: "ошибка",
    completed: "завершён",
    completed_with_warnings: "завершён с предупреждениями",
    processing: "в обработке",
    queued: "в очереди",
  },
  final_status: {
    completed: "завершён",
    completed_with_warnings: "завершён с предупреждениями",
    failed: "ошибка",
  },
  fetch_status: {
    success: "успешно",
    failed: "ошибка",
  },
  fetch_method: {
    browser: "браузер",
    http: "HTTP",
    http_retry: "повтор HTTP",
  },
  risk_level: {
    low: "низкий",
    medium: "средний",
    high: "высокий",
  },
  model_source: {
    local_dataset: "локальный набор данных",
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return String(Math.round(value));
}

export function formatTimelineDuration(ms: number | null | undefined): string {
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

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
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

function formatEventTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function normalizeTimelineStage(stage: string | null | undefined): string {
  if (!stage) {
    return "unknown";
  }
  return TASK_STAGE_MAP[stage] ?? stage;
}

export function getTimelineStageLabel(stage: string | null | undefined): string {
  if (!stage) {
    return "—";
  }
  const normalizedStage = normalizeTimelineStage(stage);
  return STAGE_LABELS[normalizedStage] ?? normalizedStage;
}

function getStageDescription(stage: string): string {
  return STAGE_DESCRIPTIONS[stage] ?? "Дополнительный серверный этап из журнала событий аудита.";
}

function getStageOrderIndex(stage: string): number {
  const index = TIMELINE_STAGE_ORDER.indexOf(stage as (typeof TIMELINE_STAGE_ORDER)[number]);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

function sortStages(left: string, right: string): number {
  const orderDelta = getStageOrderIndex(left) - getStageOrderIndex(right);
  if (orderDelta !== 0) {
    return orderDelta;
  }
  return left.localeCompare(right);
}

function getQueueLabel(queues: string[]): string {
  if (queues.length === 0) {
    return "—";
  }
  return queues.join(", ");
}

function getEventLabel(event: string | null | undefined): string {
  if (!event) {
    return "—";
  }
  return EVENT_LABELS[event] ?? event;
}

function getEventTone(event: string | null | undefined): TimelineStageStatus {
  switch (event) {
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "aborted":
      return "aborted";
    case "started":
      return "running";
    case "dispatched":
      return "dispatched";
    default:
      return "pending";
  }
}

function getDetailString(details: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = details?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function formatDetailValue(key: string, value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const trimmedValue = value.trim();
    if (!trimmedValue) {
      return null;
    }
    return DETAIL_VALUE_LABELS[key]?.[trimmedValue] ?? trimmedValue;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return null;
    }
    if (key.includes("score") || key.includes("similarity") || key.includes("alignment")) {
      return String(Math.round(value * 100) / 100);
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    const entries = value
      .map((item) => (typeof item === "string" || typeof item === "number" ? String(item) : null))
      .filter((item): item is string => Boolean(item));
    return entries.length > 0 ? entries.join(", ") : null;
  }
  if (typeof value === "boolean") {
    return value ? "да" : "нет";
  }
  return null;
}

function buildDetailSummary(details: Record<string, unknown> | null | undefined): string {
  if (!details) {
    return "—";
  }

  const usedKeys = new Set<string>();
  const entries: string[] = [];
  for (const key of [...D72_PRIORITY_DETAIL_KEYS, ...PRIORITY_DETAIL_KEYS]) {
    const value = formatDetailValue(key, details[key]);
    if (value) {
      usedKeys.add(key);
      entries.push(`${DETAIL_LABELS[key] ?? key}: ${value}`);
    }
  }

  if (entries.length < 5) {
    for (const [key, rawValue] of Object.entries(details)) {
      if (usedKeys.has(key) || IGNORED_DETAIL_KEYS.has(key)) {
        continue;
      }
      const value = formatDetailValue(key, rawValue);
      if (value) {
        entries.push(`${DETAIL_LABELS[key] ?? key}: ${value}`);
      }
      if (entries.length >= 5) {
        break;
      }
    }
  }

  return entries.length > 0 ? entries.join("; ") : "детали записаны";
}

function getRawEventDetails(event: AuditTimelineEvent): Record<string, unknown> | null {
  return isRecord(event.details) ? event.details : null;
}

function groupEventsByStage(events: AuditTimelineEvent[]): Map<string, AuditTimelineEvent[]> {
  const groups = new Map<string, AuditTimelineEvent[]>();
  for (const event of events) {
    const stage = normalizeTimelineStage(event.stage);
    groups.set(stage, [...(groups.get(stage) ?? []), event]);
  }
  return groups;
}

function getLastEvent(events: AuditTimelineEvent[]): AuditTimelineEvent | undefined {
  return events.length > 0 ? events[events.length - 1] : undefined;
}

function deriveStageDiagnosticsFromEvents(
  stage: string,
  events: AuditTimelineEvent[],
): AuditTimelineStageDiagnostics {
  const terminalDurations = events
    .filter((event) => TERMINAL_EVENTS.has(event.event) && typeof event.duration_ms === "number")
    .map((event) => Number(event.duration_ms));
  const dispatchCount = events.filter((event) => event.event === "dispatched").length;
  const startedCount = events.filter((event) => event.event === "started").length;
  const completedCount = events.filter((event) => event.event === "completed").length;
  const failedCount = events.filter((event) => event.event === "failed").length;
  const abortedCount = events.filter((event) => event.event === "aborted").length;
  const totalDurationMs =
    terminalDurations.length > 0 ? terminalDurations.reduce((sum, duration) => sum + duration, 0) : null;
  const maxDurationMs = terminalDurations.length > 0 ? Math.max(...terminalDurations) : null;
  const criticalPathMode = FAN_OUT_STAGES.has(stage) ? "fan_out_max" : "serial_sum";
  const criticalPathDurationMs =
    terminalDurations.length > 0 ? (FAN_OUT_STAGES.has(stage) ? maxDurationMs : totalDurationMs) : null;
  const latestEvent = getLastEvent(events) ?? null;

  return {
    stage,
    dispatch_count: dispatchCount,
    started_count: startedCount,
    completed_count: completedCount,
    failed_count: failedCount,
    aborted_count: abortedCount,
    terminal_count: completedCount + failedCount + abortedCount,
    total_duration_ms: totalDurationMs,
    average_duration_ms:
      terminalDurations.length > 0 && totalDurationMs !== null ? totalDurationMs / terminalDurations.length : null,
    max_duration_ms: maxDurationMs,
    critical_path_mode: criticalPathMode,
    critical_path_duration_ms: criticalPathDurationMs,
    first_event_at: events[0]?.created_at ?? null,
    last_event_at: latestEvent?.created_at ?? null,
    latest_event: latestEvent?.event ?? null,
  };
}

function getStageDiagnostics(
  stage: string,
  diagnosticsByStage: Map<string, AuditTimelineStageDiagnostics>,
  eventsByStage: Map<string, AuditTimelineEvent[]>,
): AuditTimelineStageDiagnostics {
  const diagnostics = diagnosticsByStage.get(stage);
  if (diagnostics) {
    return diagnostics;
  }
  return deriveStageDiagnosticsFromEvents(stage, eventsByStage.get(stage) ?? []);
}

function getStageQueues(events: AuditTimelineEvent[]): string[] {
  const queues = new Set<string>();
  for (const event of events) {
    const queue = getDetailString(getRawEventDetails(event), "queue");
    if (queue) {
      queues.add(queue);
    }
  }
  return Array.from(queues).sort();
}

function deriveStageStatus(
  diagnostics: AuditTimelineStageDiagnostics,
  events: AuditTimelineEvent[],
): TimelineStageStatus {
  const latestEvent = diagnostics.latest_event ?? getLastEvent(events)?.event ?? null;
  if (diagnostics.failed_count > 0 || latestEvent === "failed") {
    return "failed";
  }
  if (diagnostics.aborted_count > 0 || latestEvent === "aborted") {
    return "aborted";
  }
  if (diagnostics.completed_count > 0 || latestEvent === "completed") {
    return "completed";
  }
  if (diagnostics.started_count > diagnostics.terminal_count || latestEvent === "started") {
    return "running";
  }
  if (diagnostics.dispatch_count > 0 || latestEvent === "dispatched") {
    return "dispatched";
  }
  return "pending";
}

function buildCriticalPathStageSet(diagnostics: AuditTimelineDiagnosticsResponse | null): Set<string> {
  return new Set((diagnostics?.critical_path_stages ?? []).map((stage) => normalizeTimelineStage(stage.stage)));
}

function buildStageRows(
  diagnostics: AuditTimelineDiagnosticsResponse | null,
  events: AuditTimelineEvent[],
): TimelineStageRow[] {
  const eventsByStage = groupEventsByStage(events);
  const diagnosticsByStage = new Map(
    (diagnostics?.stage_breakdown ?? []).map((stage) => [normalizeTimelineStage(stage.stage), stage]),
  );
  const criticalPathStages = buildCriticalPathStageSet(diagnostics);
  const stageNames = new Set<string>(TIMELINE_STAGE_ORDER);
  for (const stage of diagnosticsByStage.keys()) {
    stageNames.add(stage);
  }
  for (const stage of eventsByStage.keys()) {
    stageNames.add(stage);
  }

  return Array.from(stageNames)
    .sort(sortStages)
    .map((stage) => {
      const stageEvents = eventsByStage.get(stage) ?? [];
      const stageDiagnostics = getStageDiagnostics(stage, diagnosticsByStage, eventsByStage);
      const queues = getStageQueues(stageEvents);
      const status = deriveStageStatus(stageDiagnostics, stageEvents);
      const latestEventTone = getEventTone(stageDiagnostics.latest_event);

      return {
        stage,
        label: getTimelineStageLabel(stage),
        description: getStageDescription(stage),
        status,
        statusLabel: STAGE_STATUS_LABELS[status],
        queueLabel: getQueueLabel(queues),
        queues,
        eventCount: stageEvents.length,
        dispatchCount: stageDiagnostics.dispatch_count,
        startedCount: stageDiagnostics.started_count,
        completedCount: stageDiagnostics.completed_count,
        failedCount: stageDiagnostics.failed_count,
        abortedCount: stageDiagnostics.aborted_count,
        terminalCount: stageDiagnostics.terminal_count,
        durationLabel: formatTimelineDuration(stageDiagnostics.total_duration_ms),
        averageDurationLabel: formatTimelineDuration(stageDiagnostics.average_duration_ms),
        maxDurationLabel: formatTimelineDuration(stageDiagnostics.max_duration_ms),
        criticalPathDurationLabel: formatTimelineDuration(stageDiagnostics.critical_path_duration_ms),
        criticalPathModeLabel:
          CRITICAL_PATH_MODE_LABELS[stageDiagnostics.critical_path_mode] ?? stageDiagnostics.critical_path_mode,
        isCriticalPath: criticalPathStages.has(stage),
        latestEventLabel: getEventLabel(stageDiagnostics.latest_event),
        latestEventTone,
        firstEventLabel: formatDateTime(stageDiagnostics.first_event_at),
        lastEventLabel: formatDateTime(stageDiagnostics.last_event_at),
      };
    });
}

function getRawEventCount(diagnostics: AuditTimelineDiagnosticsResponse | null, events: AuditTimelineEvent[]): number {
  return Math.max(diagnostics?.event_count ?? 0, events.length);
}

function getRawDispatchCount(diagnostics: AuditTimelineDiagnosticsResponse | null, events: AuditTimelineEvent[]): number {
  return Math.max(diagnostics?.dispatch_count ?? 0, events.filter((event) => event.event === "dispatched").length);
}

function getEventRangeDurationMs(events: AuditTimelineEvent[]): number | null {
  if (events.length === 0) {
    return null;
  }
  if (events.length === 1) {
    return 0;
  }
  const startedAt = new Date(events[0]?.created_at ?? "").getTime();
  const finishedAt = new Date(getLastEvent(events)?.created_at ?? "").getTime();
  if (Number.isNaN(startedAt) || Number.isNaN(finishedAt)) {
    return null;
  }
  return Math.max(finishedAt - startedAt, 0);
}

function getRangeLabel(diagnostics: AuditTimelineDiagnosticsResponse | null, events: AuditTimelineEvent[]): string {
  const firstEventAt = diagnostics?.started_at ?? events[0]?.created_at ?? null;
  const lastEventAt = diagnostics?.finished_at ?? getLastEvent(events)?.created_at ?? null;
  if (!firstEventAt && !lastEventAt) {
    return "Нет меток времени событий";
  }
  return `с ${formatDateTime(firstEventAt)} по ${formatDateTime(lastEventAt)}`;
}

function buildSummaryMetrics(
  diagnostics: AuditTimelineDiagnosticsResponse | null,
  events: AuditTimelineEvent[],
  earlyStop: AuditEarlyStopSummary | null,
): TimelineMetric[] {
  const terminalStage = diagnostics?.terminal_stage ? getTimelineStageLabel(diagnostics.terminal_stage) : "—";
  const terminalEvent = diagnostics?.terminal_event ? getEventLabel(diagnostics.terminal_event) : "—";
  const totalDurationMs = diagnostics?.total_duration_ms ?? getEventRangeDurationMs(events);
  const metrics: TimelineMetric[] = [
    {
      label: "События таймлайна",
      value: formatCount(getRawEventCount(diagnostics, events)),
      note: "Записи журнала событий для выбранной версии обработки аудита.",
    },
    {
      label: "Отправлено в очереди",
      value: formatCount(getRawDispatchCount(diagnostics, events)),
      note: "Сколько задач этапов было отправлено в очереди Celery.",
    },
    {
      label: "Общая длительность",
      value: formatTimelineDuration(totalDurationMs),
      note: "Фактическое время между первым и последним событием аудита.",
    },
    {
      label: "Критический путь",
      value: formatTimelineDuration(diagnostics?.critical_path_duration_ms),
      note: `Оценка вклада из серверной диагностики; финальное событие: ${terminalStage} / ${terminalEvent}.`,
    },
  ];
  if (earlyStop) {
    metrics.push({
      label: "Остановка аудита",
      value: "До конкурентов",
      note: earlyStop.message,
    });
  }
  return metrics;
}

function buildFanOutFromDiagnostics(fanOut: AuditTimelineFanOut): TimelineFanOutModel {
  const stage = normalizeTimelineStage(fanOut.stage);
  const branchCount = Math.max(fanOut.dispatch_count, fanOut.started_count, fanOut.terminal_count);
  return {
    stage,
    stageLabel: getTimelineStageLabel(stage),
    dispatchCount: fanOut.dispatch_count,
    startedCount: fanOut.started_count,
    terminalCount: fanOut.terminal_count,
    inFlightCount: fanOut.in_flight_count,
    branchCount,
    totalDurationLabel: formatTimelineDuration(fanOut.total_duration_ms),
    averageDurationLabel: formatTimelineDuration(fanOut.average_duration_ms),
    maxDurationLabel: formatTimelineDuration(fanOut.max_duration_ms),
    criticalPathDurationLabel: formatTimelineDuration(fanOut.critical_path_duration_ms),
    note: "Задачи создаются отдельными ветками. Разные секунды старта в журнале означают ожидание свободных worker-процессов или разную скорость загрузки страниц, а не что конвейер стал последовательным.",
  };
}

function buildFanOutFromStageRow(row: TimelineStageRow): TimelineFanOutModel {
  return {
    stage: row.stage,
    stageLabel: row.label,
    dispatchCount: row.dispatchCount,
    startedCount: row.startedCount,
    terminalCount: row.terminalCount,
    inFlightCount: Math.max(row.startedCount - row.terminalCount, 0),
    branchCount: Math.max(row.dispatchCount, row.startedCount, row.terminalCount),
    totalDurationLabel: row.durationLabel,
    averageDurationLabel: row.averageDurationLabel,
    maxDurationLabel: row.maxDurationLabel,
    criticalPathDurationLabel: row.criticalPathDurationLabel,
    note: "Задачи создаются отдельными ветками. Разные секунды старта в журнале означают ожидание свободных worker-процессов или разную скорость загрузки страниц, а не что конвейер стал последовательным.",
  };
}

function hasFanOutEvidence(stageRow: TimelineStageRow): boolean {
  return (
    FAN_OUT_STAGES.has(stageRow.stage) &&
    (stageRow.eventCount > 0 || stageRow.dispatchCount > 0 || stageRow.startedCount > 0 || stageRow.terminalCount > 0)
  );
}

function buildFanOutStages(
  diagnostics: AuditTimelineDiagnosticsResponse | null,
  stageRows: TimelineStageRow[],
): TimelineFanOutModel[] {
  const fanOutStages: TimelineFanOutModel[] = [];
  const knownStages = new Set<string>();

  if (diagnostics?.fan_out) {
    const fanOut = buildFanOutFromDiagnostics(diagnostics.fan_out);
    fanOutStages.push(fanOut);
    knownStages.add(fanOut.stage);
  }

  for (const stageRow of stageRows) {
    if (!hasFanOutEvidence(stageRow) || knownStages.has(stageRow.stage)) {
      continue;
    }
    const fanOut = buildFanOutFromStageRow(stageRow);
    fanOutStages.push(fanOut);
    knownStages.add(fanOut.stage);
  }

  return fanOutStages.sort((left, right) => sortStages(left.stage, right.stage));
}

function buildEventRows(events: AuditTimelineEvent[]): TimelineEventRow[] {
  return events.map((event) => {
    const details = getRawEventDetails(event);
    const stage = normalizeTimelineStage(event.stage);
    return {
      id: event.id,
      timestampLabel: formatEventTime(event.created_at),
      stage,
      stageLabel: getTimelineStageLabel(stage),
      event: event.event,
      eventLabel: getEventLabel(event.event),
      durationLabel: formatTimelineDuration(event.duration_ms),
      queueLabel: getDetailString(details, "queue") ?? "—",
      detailSummary: buildDetailSummary(details),
      tone: getEventTone(event.event),
    };
  });
}

function buildWarnings(audit: AuditStatusResponse, results: AuditResultsResponse | null): string[] {
  return Array.from(new Set([...(audit.warnings ?? []), ...(results?.warnings ?? [])]));
}

function buildFailure(failureContext: FailureContext | null): TimelineFailureModel | null {
  if (!failureContext) {
    return null;
  }
  return {
    stageLabel: getFailureStageLabel(failureContext.stage),
    code: failureContext.code,
    message: failureContext.message,
    details: getFailureDetailEntries(failureContext),
  };
}

export function buildAuditTimelineModel(input: AuditTimelineInput): AuditTimelineModel {
  const events = input.events?.events ?? [];
  const earlyStop = input.diagnostics?.early_stop ?? input.results?.early_stop ?? input.audit.early_stop ?? null;
  const stageRows = buildStageRows(input.diagnostics, events);
  const diagnosticsProcessingVersion = input.diagnostics?.processing_version ?? null;
  const eventProcessingVersion = input.events?.processing_version ?? null;
  const processingVersion = diagnosticsProcessingVersion ?? eventProcessingVersion;
  const domain = getDomainFromUrl(input.audit.target_url);
  const status = input.diagnostics?.status ?? input.results?.status ?? input.audit.status;
  const eventCount = getRawEventCount(input.diagnostics, events);
  const fanOutStages = buildFanOutStages(input.diagnostics, stageRows);
  const fanOut = fanOutStages[0] ?? null;

  return {
    title: domain,
    targetUrl: input.audit.target_url,
    query: input.audit.query,
    statusLabel: getAuditStatusLabel(status),
    processingVersionLabel: processingVersion === null ? "—" : `v${processingVersion}`,
    hasData: eventCount > 0 || (input.diagnostics?.stage_breakdown.length ?? 0) > 0,
    rangeLabel: getRangeLabel(input.diagnostics, events),
    summaryMetrics: buildSummaryMetrics(input.diagnostics, events, earlyStop),
    stageRows,
    fanOut,
    fanOutStages,
    eventRows: buildEventRows(events),
    warnings: buildWarnings(input.audit, input.results),
    failure: buildFailure(input.failureContext),
    earlyStop,
  };
}
