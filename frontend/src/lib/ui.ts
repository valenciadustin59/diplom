import type { AuditResultsResponse, AuditStatus, AuditStatusResponse, FailureContext, FailureStage } from "../types";

export function getAuditStatusLabel(status: AuditStatus): string {
  switch (status) {
    case "queued":
      return "Запускается";
    case "processing":
      return "Обработка";
    case "completed":
      return "Завершён";
    case "completed_with_warnings":
      return "Завершён с предупреждениями";
    case "failed":
      return "Ошибка";
    default:
      return status;
  }
}

export function getFailureStageLabel(stage: FailureStage): string {
  switch (stage) {
    case "fetch":
      return "загрузка целевой страницы";
    case "heavy_analysis":
      return "тяжёлый анализ страницы";
    case "features":
      return "извлечение признаков страницы";
    case "scoring":
      return "расчёт score";
    case "search":
      return "поиск и анализ конкурентов";
    case "recommendations":
      return "формирование рекомендаций";
    case "pipeline":
      return "обработка аудита";
    default:
      return stage;
  }
}

function formatFailureDetailValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

export function getFailureDetailEntries(context: FailureContext): Array<{ label: string; value: string }> {
  const details = context.details ?? {};
  const labels: Record<string, string> = {
    fetch_method: "Способ fetch",
    http_status: "HTTP статус",
  };

  return Object.entries(details).flatMap(([key, rawValue]) => {
    const value = formatFailureDetailValue(rawValue);
    if (!value) {
      return [];
    }

    return [
      {
        label: labels[key] ?? key,
        value,
      },
    ];
  });
}

export function resolveAuditFailureContext(
  audit: AuditStatusResponse | null,
  results: AuditResultsResponse | null,
): FailureContext | null {
  const explicitContext = results?.failure_context ?? audit?.failure_context ?? null;
  if (explicitContext) {
    return explicitContext;
  }

  const auditStatus = results?.status ?? audit?.status;
  if (auditStatus !== "failed") {
    return null;
  }

  const targetFetchStatus = results?.target_fetch_status ?? audit?.target_fetch_status;
  const targetFetchMethod = results?.target_fetch_method ?? audit?.target_fetch_method;
  const targetFetchErrorCode = results?.target_fetch_error_code ?? audit?.target_fetch_error_code ?? null;
  const targetFetchErrorMessage = results?.target_fetch_error_message ?? audit?.target_fetch_error_message;

  if (targetFetchStatus === "failed" && targetFetchErrorMessage) {
    return {
      stage: "fetch",
      code: targetFetchErrorCode,
      message: targetFetchErrorMessage,
      details: targetFetchMethod ? { fetch_method: targetFetchMethod } : null,
    };
  }

  const genericMessage = results?.error_message ?? audit?.error_message;
  if (!genericMessage) {
    return null;
  }

  return {
    stage: "pipeline",
    code: null,
    message: genericMessage,
    details: null,
  };
}
