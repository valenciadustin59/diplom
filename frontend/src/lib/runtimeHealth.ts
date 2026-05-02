import type {
  RuntimeHealthCheck,
  RuntimeLivenessResponse,
  RuntimeMetricsResponse,
  RuntimeModelRegistryResponse,
  RuntimeModelMonitoringResponse,
  RuntimeModelStatusResponse,
  RuntimeQueueSnapshot,
  RuntimeReadinessResponse,
  RuntimeWorkerTopologyContract,
  RuntimeWorkerTopologyCoverage,
  RuntimeWorkerTopologyProfile,
} from "../types";
import { buildModelRegistryView, type RuntimeModelRegistryView } from "./runtimeModelRegistry";
import { buildModelMonitoringView, type RuntimeModelMonitoringView } from "./runtimeModelMonitoring";

export type {
  RuntimeModelRegistryRecordRow,
  RuntimeModelRegistryView,
  RuntimeRollbackChecklistRow,
} from "./runtimeModelRegistry";
export type { RuntimeModelMonitoringView, RuntimeModelUsageRow } from "./runtimeModelMonitoring";

export type RuntimeTone = "ok" | "warning" | "error" | "muted";

export type RuntimeMetric = {
  label: string;
  value: string;
  note: string;
  tone: RuntimeTone;
};

export type RuntimeComponentRow = {
  id: string;
  label: string;
  status: string;
  statusLabel: string;
  tone: RuntimeTone;
  detail: string;
};

export type RuntimeWorkerProfileRow = {
  name: string;
  label: string;
  description: string;
  statusLabel: string;
  tone: RuntimeTone;
  workerCount: number;
  workersLabel: string;
  queuesLabel: string;
  missingQueues: string[];
  recommendedConcurrencyLabel: string;
};

export type RuntimeQueueRow = {
  name: string;
  profileName: string;
  profileLabel: string;
  pressureStatus: string;
  pressureLabel: string;
  tone: RuntimeTone;
  depth: number;
  workerCount: number;
  workersLabel: string;
  activeTasks: number;
  reservedTasks: number;
  scheduledTasks: number;
  inflightTasks: number;
  availableCapacity: number;
  reasonLabels: string[];
};

export type RuntimeIssue = {
  key: string;
  title: string;
  detail: string;
  tone: RuntimeTone;
};

export type RuntimeModelStatusView = {
  status: string;
  statusLabel: string;
  tone: RuntimeTone;
  shortLabel: string;
  detail: string;
  checkedAtLabel: string;
  artifactVersion: string | null;
  artifactSha1: string | null;
  datasetVersion: string | null;
  modelSchemaVersion: string | null;
  publishedAt: string | null;
  modelTypeLabel: string;
  schemaLabel: string;
  featureCountLabel: string;
  datasetLabel: string;
  artifactLabel: string;
  publishedAtLabel: string;
  publishLabel: string;
  rollbackLabel: string;
  artifactShaLabel: string;
  metricRows: RuntimeMetric[];
};

export type RuntimeHealthModel = {
  checkedAtLabel: string;
  appLabel: string;
  environmentLabel: string;
  ready: boolean;
  statusLabel: string;
  statusDetail: string;
  statusTone: RuntimeTone;
  metrics: RuntimeMetric[];
  modelStatus: RuntimeModelStatusView | null;
  modelRegistry: RuntimeModelRegistryView | null;
  modelMonitoring: RuntimeModelMonitoringView | null;
  components: RuntimeComponentRow[];
  workerProfiles: RuntimeWorkerProfileRow[];
  queues: RuntimeQueueRow[];
  issues: RuntimeIssue[];
  queueDepthTotal: number;
  workerCount: number;
  backloggedQueueCount: number;
  stuckQueueCount: number;
};
type RuntimeHealthInput = {
  live: RuntimeLivenessResponse | null;
  readiness: RuntimeReadinessResponse | null;
  metrics: RuntimeMetricsResponse | null;
  modelStatus?: RuntimeModelStatusResponse | null;
  modelRegistry?: RuntimeModelRegistryResponse | null;
  modelMonitoring?: RuntimeModelMonitoringResponse | null;
};
const PROFILE_LABELS: Record<string, string> = {
  pipeline: "Оркестратор",
  network: "Сетевой профиль",
  heavy_analysis: "Углублённый анализ",
  cpu_ml: "CPU/ML профиль",
};
const PROFILE_DESCRIPTIONS: Record<string, string> = {
  pipeline: "Запускает аудит, координирует этапы и контроль допуска.",
  network: "Обслуживает загрузку целевой страницы, поиск и сбор страниц конкурентов.",
  heavy_analysis: "Изолирует углублённый анализ страницы, смысловые сигналы и ML-анализ конкурентов.",
  cpu_ml: "Собирает признаки, считает оценку, рекомендации и финализацию.",
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
const PRESSURE_LABELS: Record<string, string> = {
  idle: "простаивает",
  busy: "занята",
  waiting: "ожидает воркер",
  draining: "разбирается",
  backlogged: "накопление задач",
  stuck: "без воркеров",
};
const REASON_LABELS: Record<string, string> = {
  inflight_without_backlog: "есть задачи в работе без накопления в очереди",
  no_workers_serving_queue: "очередь не обслуживается активными воркерами",
  queued_tasks_without_drain_activity: "накопились задачи без признаков разбора",
  queued_tasks_pending_pickup: "задачи ждут подхвата воркером",
  depth_exceeds_estimated_capacity: "глубина очереди выше оценочной пропускной способности",
  queue_is_draining: "воркеры разбирают накопленные задачи",
};
const ALERT_LABELS: Record<string, string> = {
  stuck_processing_audits: "Зависшие аудиты в обработке",
  queued_audits_waiting_too_long: "Аудиты слишком долго ждут старта",
  dispatched_stages_waiting_too_long: "Этапы слишком долго ждут выполнения",
  queue_without_workers: "Очередь без воркеров",
  queue_backlog_detected: "Накопление задач в очереди",
};
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}
function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.flatMap((item) => (typeof item === "string" ? [item] : [])) : [];
}
function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "—";
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
function formatDurationSeconds(value: unknown): string {
  const seconds = asNumber(value);
  if (seconds === null) {
    return "—";
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} с`;
  }
  return `${Math.round(seconds / 6) / 10} мин`;
}
function getStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return "нет данных";
  }
  return STATUS_LABELS[status] ?? status;
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
function getQueueTone(status: string): RuntimeTone {
  if (status === "idle" || status === "busy" || status === "draining") {
    return "ok";
  }
  if (status === "waiting" || status === "backlogged") {
    return "warning";
  }
  if (status === "stuck") {
    return "error";
  }
  return getStatusTone(status);
}
function getProfileLabel(profileName: string): string {
  return PROFILE_LABELS[profileName] ?? profileName;
}
function getProfileDescription(profileName: string, fallback: string | null | undefined): string {
  return PROFILE_DESCRIPTIONS[profileName] ?? fallback ?? "Профиль распределённого рабочего стека.";
}
function getHealthCheckDetail(check: RuntimeHealthCheck | undefined, fallback: string): string {
  if (!check) {
    return "Нет данных диагностики.";
  }
  const error = asString(check.error);
  if (error) {
    return error;
  }
  const workerCount = asNumber(check.worker_count);
  if (workerCount !== null) {
    const missingQueues = asStringArray(check.missing_queues);
    return missingQueues.length > 0
      ? `${workerCount} воркеров, не покрыты очереди: ${missingQueues.join(", ")}.`
      : `${workerCount} воркеров, все ожидаемые очереди покрыты.`;
  }
  const brokerUrl = asString(check.broker_url);
  if (brokerUrl) {
    return brokerUrl;
  }
  const baseUrl = asString(check.base_url);
  const healthEndpoint = asString(check.health_endpoint);
  if (baseUrl && healthEndpoint) {
    return `${baseUrl}; проверка готовности: ${healthEndpoint}.`;
  }
  if (healthEndpoint) {
    return healthEndpoint;
  }
  if (baseUrl) {
    return baseUrl;
  }
  const databaseUrl = asString(check.database_url);
  if (databaseUrl) {
    return databaseUrl;
  }
  return fallback;
}
function getTopologyContract(input: RuntimeHealthInput): RuntimeWorkerTopologyContract | null {
  return (
    input.metrics?.workers.topology_contract ??
    input.metrics?.orchestration.worker_topology ??
    input.readiness?.orchestration.worker_topology ??
    null
  );
}
function getExpectedQueues(input: RuntimeHealthInput): string[] {
  return [
    ...(input.metrics?.orchestration.expected_queues ?? []),
    ...(input.metrics?.workers.expected_queues ?? []),
    ...(input.readiness?.orchestration.expected_queues ?? []),
    ...(getTopologyContract(input)?.expected_queues ?? []),
    ...Object.keys(input.metrics?.queue_pressure.queues ?? {}),
  ].filter((queue, index, queues) => queue && queues.indexOf(queue) === index);
}
function buildQueueProfileMap(contract: RuntimeWorkerTopologyContract | null): Map<string, RuntimeWorkerTopologyProfile> {
  return new Map(
    (contract?.profiles ?? []).flatMap((profile) => profile.queues.map((queueName) => [queueName, profile] as const)),
  );
}
function buildComponentRows(input: RuntimeHealthInput): RuntimeComponentRow[] {
  const liveStatus = input.live?.status ?? null;
  const checks = input.readiness?.checks ?? {};
  const queuePressureStatus = input.metrics?.queue_pressure.status ?? null;
  const brokerStatus = input.metrics?.broker.status ?? checks.redis?.status ?? null;

  return [
    {
      id: "api",
      label: "API",
      status: liveStatus ?? "unknown",
      statusLabel: getStatusLabel(liveStatus),
      tone: getStatusTone(liveStatus),
      detail: input.live ? `FastAPI отвечает, окружение: ${input.live.environment}.` : "Проверка жизнеспособности пока недоступна.",
    },
    {
      id: "database",
      label: "База данных",
      status: checks.database?.status ?? input.metrics?.database.status ?? "unknown",
      statusLabel: getStatusLabel(checks.database?.status ?? input.metrics?.database.status),
      tone: getStatusTone(checks.database?.status ?? input.metrics?.database.status),
      detail: getHealthCheckDetail(checks.database ?? input.metrics?.database, "SQLite/PostgreSQL доступна серверному API."),
    },
    {
      id: "redis",
      label: "Redis-брокер",
      status: brokerStatus ?? "unknown",
      statusLabel: getStatusLabel(brokerStatus),
      tone: getStatusTone(brokerStatus),
      detail: getHealthCheckDetail(checks.redis ?? input.metrics?.broker, "Брокер Redis отвечает на диагностику рабочего стека."),
    },
    {
      id: "serp",
      label: "SearXNG",
      status: checks.serp?.status ?? "unknown",
      statusLabel: getStatusLabel(checks.serp?.status),
      tone: getStatusTone(checks.serp?.status),
      detail: getHealthCheckDetail(checks.serp, "Поисковый провайдер доступен для сбора конкурентов."),
    },
    {
      id: "workers",
      label: "Воркеры Celery",
      status: checks.celery_workers?.status ?? input.metrics?.workers.status ?? "unknown",
      statusLabel: getStatusLabel(checks.celery_workers?.status ?? input.metrics?.workers.status),
      tone: getStatusTone(checks.celery_workers?.status ?? input.metrics?.workers.status),
      detail: getHealthCheckDetail(checks.celery_workers ?? input.metrics?.workers, "Воркеры отвечают на диагностический опрос."),
    },
    {
      id: "queues",
      label: "Очереди",
      status: queuePressureStatus ?? "unknown",
      statusLabel: getStatusLabel(queuePressureStatus),
      tone: getStatusTone(queuePressureStatus),
      detail: input.metrics?.queue_pressure
        ? `Накопление задач: ${(input.metrics.queue_pressure.backlogged_queues ?? []).length}, без воркеров: ${(input.metrics.queue_pressure.stuck_queues ?? []).length}.`
        : "Данные нагрузки очередей пока недоступны.",
    },
  ];
}
function buildProfileRows(input: RuntimeHealthInput): RuntimeWorkerProfileRow[] {
  const contractProfiles = getTopologyContract(input)?.profiles ?? [];
  const topologyProfiles = input.metrics?.workers.topology?.profiles ?? {};

  return contractProfiles.map((profile) => {
    const coverage = topologyProfiles[profile.name] as RuntimeWorkerTopologyCoverage | undefined;
    const queues = coverage?.queues ?? profile.queues;
    const workers = coverage?.workers ?? [];
    const missingQueues = coverage?.missing_queues ?? queues;
    const workerCount = coverage?.worker_count ?? workers.length;
    const tone: RuntimeTone = missingQueues.length > 0 || workerCount === 0 ? "error" : "ok";

    return {
      name: profile.name,
      label: getProfileLabel(profile.name),
      description: getProfileDescription(profile.name, coverage?.description ?? profile.description),
      statusLabel: tone === "ok" ? "очереди покрыты" : "требуется воркер",
      tone,
      workerCount,
      workersLabel: workers.length > 0 ? workers.join(", ") : "нет активных воркеров",
      queuesLabel: queues.join(", "),
      missingQueues,
      recommendedConcurrencyLabel: `${coverage?.recommended_concurrency ?? profile.recommended_concurrency}`,
    };
  });
}
function buildQueueRows(input: RuntimeHealthInput): RuntimeQueueRow[] {
  const expectedQueues = getExpectedQueues(input);
  const queueProfileMap = buildQueueProfileMap(getTopologyContract(input));
  const queueSnapshots = input.metrics?.queue_pressure.queues ?? {};
  const profileOrder = new Map((getTopologyContract(input)?.profiles ?? []).map((profile, index) => [profile.name, index]));

  return expectedQueues
    .map((queueName) => {
      const snapshot = queueSnapshots[queueName] as RuntimeQueueSnapshot | undefined;
      const profile = queueProfileMap.get(queueName);
      const pressureStatus = snapshot?.pressure_status ?? "unknown";
      return {
        name: queueName,
        profileName: profile?.name ?? "unassigned",
        profileLabel: profile ? getProfileLabel(profile.name) : "Не назначена",
        pressureStatus,
        pressureLabel: PRESSURE_LABELS[pressureStatus] ?? pressureStatus,
        tone: getQueueTone(pressureStatus),
        depth: snapshot?.depth ?? 0,
        workerCount: snapshot?.worker_count ?? 0,
        workersLabel: snapshot && snapshot.workers.length > 0 ? snapshot.workers.join(", ") : "нет",
        activeTasks: snapshot?.active_tasks ?? 0,
        reservedTasks: snapshot?.reserved_tasks ?? 0,
        scheduledTasks: snapshot?.scheduled_tasks ?? 0,
        inflightTasks: snapshot?.inflight_tasks ?? 0,
        availableCapacity: snapshot?.available_capacity_estimate ?? 0,
        reasonLabels: (snapshot?.reasons ?? []).map((reason) => REASON_LABELS[reason] ?? reason),
      };
    })
    .sort((left, right) => {
      const leftProfileOrder = profileOrder.get(left.profileName) ?? Number.MAX_SAFE_INTEGER;
      const rightProfileOrder = profileOrder.get(right.profileName) ?? Number.MAX_SAFE_INTEGER;
      return leftProfileOrder - rightProfileOrder || left.name.localeCompare(right.name);
    });
}
function buildAlertIssue(alert: Record<string, unknown>): RuntimeIssue | null {
  const code = asString(alert.code);
  if (!code) {
    return null;
  }
  const queue = asString(alert.queue);
  const severity = asString(alert.severity) ?? "warning";
  const count = asNumber(alert.count);
  const depth = asNumber(alert.depth);

  if (code === "queue_without_workers" && queue) {
    return {
      key: `${code}:${queue}`,
      title: "Очередь без активных воркеров",
      detail: `Запустите профиль, который обслуживает ${queue}. Глубина очереди: ${formatCount(depth)}.`,
      tone: "error",
    };
  }
  if (code === "queue_backlog_detected" && queue) {
    return {
      key: `${code}:${queue}`,
      title: "Накопление задач в очереди",
      detail: `Очередь ${queue} накопила ${formatCount(depth)} задач. Увеличьте число воркеров профиля или дождитесь разбора очереди.`,
      tone: "warning",
    };
  }
  if (code === "queued_audits_waiting_too_long") {
    return {
      key: code,
      title: "Аудиты слишком долго ждут запуска",
      detail: `Самый старый аудит ждёт ${formatDurationSeconds(alert.oldest_age_seconds)}. Проверьте очередь audits.pipeline и профиль оркестратора.`,
      tone: "warning",
    };
  }
  if (code === "dispatched_stages_waiting_too_long") {
    return {
      key: code,
      title: "Этапы ожидают выполнения дольше нормы",
      detail: `${formatCount(count)} этапов ожидают воркеры. Проверьте очереди из примеров в диагностике рабочего стека.`,
      tone: "warning",
    };
  }
  if (code === "stuck_processing_audits") {
    return null;
  }

  return {
    key: code,
    title: ALERT_LABELS[code] ?? code,
    detail: `Детектор рабочего стека сообщил важность=${severity}.`,
    tone: severity === "error" ? "error" : "warning",
  };
}
function dedupeIssues(issues: RuntimeIssue[]): RuntimeIssue[] {
  return Array.from(new Map(issues.map((issue) => [issue.key, issue])).values());
}
function buildIssues(input: RuntimeHealthInput, profileRows: RuntimeWorkerProfileRow[], queueRows: RuntimeQueueRow[]): RuntimeIssue[] {
  const componentIssues = buildComponentRows(input).flatMap((component) =>
    component.tone === "ok" || component.id === "queues"
      ? []
      : [
          {
            key: `component:${component.id}`,
            title: `${component.label}: ${component.statusLabel}`,
            detail: component.detail,
            tone: component.tone,
          },
        ],
  );

  const profileIssues = profileRows.flatMap((profile): RuntimeIssue[] =>
    profile.tone === "ok"
      ? []
      : [
          {
            key: `profile:${profile.name}`,
            title: `Не покрыт профиль "${profile.label}"`,
            detail:
              profile.missingQueues.length > 0
                ? `Запустите воркер профиля. Не покрыты очереди: ${profile.missingQueues.join(", ")}.`
                : "Профиль не видит активных воркеров.",
            tone: "error" as const,
          },
        ],
  );

  const queueIssues = queueRows.flatMap((queue): RuntimeIssue[] => {
    if (queue.pressureStatus === "stuck") {
      return [
        {
          key: `queue:stuck:${queue.name}`,
          title: `Очередь ${queue.name} без воркеров`,
          detail: `Запустите профиль "${queue.profileLabel}". Сейчас в очереди ${queue.depth} задач.`,
          tone: "error" as const,
        },
      ];
    }
    if (queue.pressureStatus === "backlogged") {
      return [
        {
          key: `queue:backlogged:${queue.name}`,
          title: `Накопление задач в ${queue.name}`,
          detail: `Глубина ${queue.depth}, активных задач ${queue.activeTasks}. Увеличьте число воркеров профиля "${queue.profileLabel}" или дождитесь освобождения пропускной способности.`,
          tone: "warning" as const,
        },
      ];
    }
    return [];
  });

  const alertIssues = (input.metrics?.execution_detector.alerts ?? []).flatMap((alert): RuntimeIssue[] => {
    const issue = isRecord(alert) ? buildAlertIssue(alert) : null;
    return issue ? [issue] : [];
  });

  const issues = dedupeIssues([...componentIssues, ...profileIssues, ...queueIssues, ...alertIssues]);
  return issues.length > 0
    ? issues
    : [
        {
          key: "runtime-ready",
          title: "Рабочий стек готов к новым аудитам",
          detail: "API, Redis, SearXNG, воркеры и очереди отвечают штатно.",
          tone: "ok",
        },
      ];
}
function buildMetrics(input: RuntimeHealthInput, issues: RuntimeIssue[]): RuntimeMetric[] {
  const workerCount = input.metrics?.workers.online_count ?? 0;
  const queueDepthTotal = input.metrics?.broker.total_depth ?? 0;
  const backloggedQueueCount = input.metrics?.queue_pressure.backlogged_queues?.length ?? 0;
  const stuckQueueCount = input.metrics?.queue_pressure.stuck_queues?.length ?? 0;
  const ready = input.readiness?.status === "ready";

  return [
    {
      label: "Готовность",
      value: ready ? "готов" : "не готов",
      note: ready ? "Проверка готовности допускает новые аудиты." : "Есть обязательные компоненты рабочего стека с ошибкой.",
      tone: ready ? "ok" : "error",
    },
    {
      label: "Воркеры",
      value: formatCount(workerCount),
      note: "Активные Celery-воркеры, отвечающие на диагностический опрос.",
      tone: workerCount > 0 ? "ok" : "error",
    },
    {
      label: "Глубина очередей",
      value: formatCount(queueDepthTotal),
      note: "Сумма задач в Redis-очередях аудита.",
      tone: queueDepthTotal === 0 ? "ok" : "warning",
    },
    {
      label: "Проблемы",
      value: formatCount(issues.filter((issue) => issue.tone !== "ok").length),
      note: `Накопление задач: ${backloggedQueueCount}, без воркеров: ${stuckQueueCount}.`,
      tone: issues.some((issue) => issue.tone === "error")
        ? "error"
        : issues.some((issue) => issue.tone === "warning")
          ? "warning"
          : "ok",
    },
  ];
}

function getModelStatusLabel(status: string | null | undefined): string {
  if (status === "active") {
    return "Расчёт score доступен";
  }
  if (status === "fallback") {
    return "Расчёт score в резервном режиме";
  }
  if (status === "error") {
    return "Ошибка расчёта score";
  }
  return status ? getStatusLabel(status) : "Нет данных";
}

function buildModelStatusView(status: RuntimeModelStatusResponse | null | undefined): RuntimeModelStatusView | null {
  if (!status) {
    return null;
  }
  const model = isRecord(status.model) ? status.model : {};
  const dataset = isRecord(status.dataset) ? status.dataset : {};
  const publish = isRecord(status.publish) ? status.publish : {};
  const rollback = isRecord(status.rollback) ? status.rollback : {};
  const statusValue = asString(status.status) ?? "unknown";
  const modelType = asString(model.model_type) ?? "модель не определена";
  const schemaVersionRaw = asString(model.model_schema_version);
  const schemaVersion = schemaVersionRaw ?? "схема не указана";
  const featureCount = asNumber(model.feature_count);
  const artifactVersionRaw = asString(model.artifact_version);
  const artifactVersion = artifactVersionRaw ?? asString(status.artifact_path) ?? "артефакт не указан";
  const artifactSha = asString(status.artifact_sha1);
  const datasetVersionRaw = asString(dataset.dataset_version);
  const datasetVersion = datasetVersionRaw ?? "датасет не указан";
  const datasetRows = asNumber(dataset.rows_count);
  const datasetQueries = asNumber(dataset.queries_count);
  const selectedCandidate = asString(publish.selected_candidate) ?? asString(publish.candidate_name);
  const publishRecommendation = asString(publish.publish_recommendation);
  const rollbackAvailable = rollback.available === true;
  const tone = statusValue === "active" ? "ok" : statusValue === "error" ? "error" : "warning";
  const error = asString(status.error);

  return {
    status: statusValue,
    statusLabel: getModelStatusLabel(statusValue),
    tone,
    shortLabel: `Оценка качества страницы · ${schemaVersion}`,
    detail: error
      ? error
      : `Score считается по признакам целевой страницы, смысловой близости к запросу, техническим, коммерческим и доверительным сигналам.`,
    checkedAtLabel: formatCheckedAt(status.checked_at),
    artifactVersion: artifactVersionRaw,
    artifactSha1: artifactSha,
    datasetVersion: datasetVersionRaw,
    modelSchemaVersion: schemaVersionRaw,
    publishedAt: asString(model.published_at),
    modelTypeLabel: modelType,
    schemaLabel: schemaVersion,
    featureCountLabel: featureCount === null ? "—" : `${featureCount}`,
    datasetLabel: `${datasetVersion} · ${formatCount(datasetRows)} строк · ${formatCount(datasetQueries)} запросов`,
    artifactLabel: artifactVersion,
    publishedAtLabel: formatCheckedAt(asString(model.published_at)),
    publishLabel: selectedCandidate
      ? `${selectedCandidate}${publishRecommendation ? ` · ${publishRecommendation}` : ""}`
      : publishRecommendation || "решение публикации не указано",
    rollbackLabel: rollbackAvailable ? "Rollback доступен" : "Rollback не найден",
    artifactShaLabel: artifactSha ? artifactSha.slice(0, 12) : "—",
    metricRows: [],
  };
}

export function buildRuntimeHealthModel(input: RuntimeHealthInput): RuntimeHealthModel {
  const workerProfiles = buildProfileRows(input);
  const queues = buildQueueRows(input);
  const issues = buildIssues(input, workerProfiles, queues);
  const metrics = buildMetrics(input, issues);
  const modelStatus = buildModelStatusView(input.modelStatus ?? null);
  const modelRegistry = buildModelRegistryView(input.modelRegistry ?? null);
  const modelMonitoring = buildModelMonitoringView(input.modelMonitoring ?? null);
  const ready = input.readiness?.status === "ready";
  const hasErrorIssue = issues.some((issue) => issue.tone === "error");
  const hasWarningIssue = issues.some((issue) => issue.tone === "warning");
  const statusTone: RuntimeTone = ready && !hasErrorIssue && !hasWarningIssue ? "ok" : hasErrorIssue ? "error" : "warning";
  const checkedAt = input.metrics?.checked_at ?? input.readiness?.checked_at ?? input.live?.checked_at ?? null;
  const statusDetail = ready
    ? statusTone === "ok"
      ? "Очереди свободны, воркеры покрывают нужные профили, можно запускать новый аудит."
      : "Стек отвечает, но нагрузка очередей может временно ограничивать пропускную способность."
    : "Новые аудиты могут быть отклонены контролем допуска до восстановления обязательных компонентов.";

  return {
    checkedAtLabel: formatCheckedAt(checkedAt),
    appLabel: input.live?.app_name ?? input.metrics?.app_name ?? input.readiness?.app_name ?? "серверный API",
    environmentLabel: input.live?.environment ?? input.metrics?.environment ?? input.readiness?.environment ?? "unknown",
    ready,
    statusLabel: ready && statusTone === "ok" ? "Рабочий стек готов" : ready ? "Рабочий стек требует внимания" : "Рабочий стек не готов",
    statusDetail,
    statusTone,
    metrics,
    modelStatus,
    modelRegistry,
    modelMonitoring,
    components: buildComponentRows(input),
    workerProfiles,
    queues,
    issues,
    queueDepthTotal: input.metrics?.broker.total_depth ?? 0,
    workerCount: input.metrics?.workers.online_count ?? 0,
    backloggedQueueCount: input.metrics?.queue_pressure.backlogged_queues?.length ?? 0,
    stuckQueueCount: input.metrics?.queue_pressure.stuck_queues?.length ?? 0,
  };
}
