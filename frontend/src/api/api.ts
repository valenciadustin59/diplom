import type {
  AuditCreatePayload,
  AuditRecommendationsResponse,
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
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

  if (status === 503 && workerCount === 0 && queueName) {
    const baseMessage = message ?? "Новый аудит сейчас не может стартовать.";
    return `${baseMessage} Очередь ${queueName} сейчас без активных воркеров. Запустите полный стек или дождитесь восстановления worker-процессов.`;
  }

  if (message) {
    return message;
  }

  if (code) {
    return `Ошибка запроса: ${code}`;
  }

  return `Ошибка запроса: ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (error) {
    throw new ApiError("Не удалось подключиться к backend API", 0, error);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
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
