import type {
  AuditCreatePayload,
  AuditRecommendationsResponse,
  AuditResultsResponse,
  AuditStatusResponse,
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
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `Ошибка запроса: ${response.status}`;

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
};
