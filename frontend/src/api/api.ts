import type {
  AuditCreatePayload,
  AuditRecommendationsResponse,
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  RuntimeLivenessResponse,
  RuntimeMetricsResponse,
  RuntimeReadinessResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getStringField(source: Record<string, unknown> | null, key: string): string | null {
  const value = source?.[key];
  return typeof value === "string" ? value : null;
}

function getNumberField(source: Record<string, unknown> | null, key: string): number | null {
  const value = source?.[key];
  return typeof value === "number" ? value : null;
}

const queueProfileLabels: Record<string, string> = {
  "audits.pipeline": "профиль оркестратора",
  "audits.fetch": "сетевой профиль",
  "audits.competitors": "сетевой профиль",
  "audits.competitor_pages": "сетевой профиль",
  "audits.heavy_analysis": "профиль тяжёлого анализа",
  "audits.features": "CPU/ML профиль",
  "audits.scoring": "CPU/ML профиль",
  "audits.recommendations": "CPU/ML профиль",
  "audits.finalize": "CPU/ML профиль",
};

function getAdmissionControlMessage(code: string | null, queueName: string | null, workerCount: number | null): string | null {
  if (!code || !queueName) {
    return null;
  }

  const profileLabel = queueProfileLabels[queueName] ?? "нужный профиль воркеров";
  const queueSuffix = ` Очередь: ${queueName}.`;

  if (workerCount === 0) {
    return `Новый аудит временно не запускается: очередь не обслуживается активными воркерами. Проверьте состояние стека и запустите ${profileLabel}.${queueSuffix}`;
  }

  if (code === "pipeline_queue_capacity_exhausted" || code === "pipeline_queue_backlog_detected") {
    return `Новый аудит временно не запускается: входная очередь аудитов перегружена. Проверьте состояние стека, дождитесь снижения накопления задач или запустите ${profileLabel}.${queueSuffix}`;
  }

  if (code === "heavy_analysis_queue_capacity_exhausted") {
    return `Новый аудит временно не запускается: очередь тяжёлого анализа перегружена или не обслуживается воркерами. Проверьте состояние стека и профиль тяжёлого анализа.${queueSuffix}`;
  }

  if (code === "broker_runtime_telemetry_unavailable") {
    return `Новый аудит временно не запускается: сервер не смог прочитать диагностику очередей Redis/Celery. Проверьте состояние стека, Redis и воркеры.${queueSuffix}`;
  }

  return null;
}

export function getApiErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (!isRecord(payload) || !("detail" in payload)) {
    return `Ошибка запроса: ${status}`;
  }

  const detail = payload.detail;
  if (typeof detail === "string") {
    return detail;
  }

  if (!isRecord(detail)) {
    return `Ошибка запроса: ${status}`;
  }

  const message = getStringField(detail, "message");
  const code = getStringField(detail, "code");
  const queueName = getStringField(detail, "queue_name");
  const detailFields = isRecord(detail.details) ? detail.details : null;
  const workerCount = getNumberField(detailFields, "worker_count");

  if (status === 503) {
    const admissionMessage = getAdmissionControlMessage(code, queueName, workerCount);
    if (admissionMessage) {
      return admissionMessage;
    }
  }

  if (message) {
    return message;
  }

  if (code) {
    return `Ошибка запроса: ${code}`;
  }

  return `Ошибка запроса: ${status}`;
}

async function request<T>(
  path: string,
  init?: RequestInit & { acceptedStatuses?: number[] },
): Promise<T> {
  let response: Response;
  const { acceptedStatuses = [], ...requestInit } = init ?? {};

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(requestInit.headers ?? {}),
      },
      ...requestInit,
    });
  } catch (error) {
    throw new ApiError("Не удалось подключиться к серверному API", 0, error);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok && !acceptedStatuses.includes(response.status)) {
    const message = getApiErrorMessage(payload, response.status);

    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export const auditsApi = {
  list(): Promise<AuditStatusResponse[]> {
    return request<AuditStatusResponse[]>("/audits");
  },

  create(payload: AuditCreatePayload): Promise<AuditStatusResponse> {
    return request<AuditStatusResponse>("/audits", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getStatus(auditId: string): Promise<AuditStatusResponse> {
    return request<AuditStatusResponse>(`/audits/${auditId}`);
  },

  getResults(auditId: string): Promise<AuditResultsResponse> {
    return request<AuditResultsResponse>(`/audits/${auditId}/results`);
  },

  getRecommendations(auditId: string): Promise<AuditRecommendationsResponse> {
    return request<AuditRecommendationsResponse>(`/audits/${auditId}/recommendations`);
  },

  getTimelineDiagnostics(auditId: string): Promise<AuditTimelineDiagnosticsResponse> {
    return request<AuditTimelineDiagnosticsResponse>(`/audits/${auditId}/events/diagnostics`);
  },

  getTimelineEvents(auditId: string): Promise<AuditTimelineEventsResponse> {
    return request<AuditTimelineEventsResponse>(`/audits/${auditId}/events`);
  },
};

export const runtimeApi = {
  getLiveness(): Promise<RuntimeLivenessResponse> {
    return request<RuntimeLivenessResponse>("/health/live");
  },

  getReadiness(): Promise<RuntimeReadinessResponse> {
    return request<RuntimeReadinessResponse>("/health/ready", { acceptedStatuses: [503] });
  },

  getMetrics(): Promise<RuntimeMetricsResponse> {
    return request<RuntimeMetricsResponse>("/health/metrics");
  },
};
