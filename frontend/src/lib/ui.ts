import type { AuditStatus } from "../types";

export function getAuditStatusLabel(status: AuditStatus): string {
  switch (status) {
    case "queued":
      return "В очереди";
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
