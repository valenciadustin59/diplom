import type { AuditStatus, ScoreBreakdown } from "../types";
import type { RuntimeModelStatusView } from "./runtimeHealth";

export type ActiveModelIdentity = Pick<
  RuntimeModelStatusView,
  "artifactVersion" | "datasetVersion" | "modelSchemaVersion" | "artifactSha1" | "publishedAt"
> | null | undefined;

export type AuditModelArchiveState = "current" | "archived" | "unknown" | "not_scored";

export type AuditModelArchiveInfo = {
  state: AuditModelArchiveState;
  isArchived: boolean;
  label: string;
  reason: string;
};

export const CURRENT_PRODUCTION_MODEL_FALLBACK: NonNullable<ActiveModelIdentity> = {
  artifactVersion: "dataset-v3-d37-20260501200434",
  artifactSha1: "29c4b29455f795a535da94b2c6f36ef603d003eb",
  datasetVersion: "dataset-v3-d37",
  modelSchemaVersion: "v3",
  publishedAt: "2026-05-01T20:04:34.923991+00:00",
};

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function getModelInfoValue(modelInfo: Record<string, unknown> | null, key: string): string | null {
  return asString(modelInfo?.[key]);
}

function getScoreBreakdownModelInfo(scoreBreakdown: ScoreBreakdown | null | undefined): Record<string, unknown> | null {
  const modelInfo = scoreBreakdown?.model_info;
  return typeof modelInfo === "object" && modelInfo !== null ? modelInfo : null;
}

function hasScoredResult(status: AuditStatus, score: number | null | undefined): boolean {
  return (status === "completed" || status === "completed_with_warnings") && typeof score === "number";
}

function getTimestamp(value: string | number | null | undefined): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const timestamp = new Date(value).getTime();
    return Number.isNaN(timestamp) ? null : timestamp;
  }
  return null;
}

function hasActiveModelIdentity(activeModel: ActiveModelIdentity): boolean {
  return Boolean(
    activeModel?.artifactVersion ||
      activeModel?.datasetVersion ||
      activeModel?.modelSchemaVersion ||
      activeModel?.artifactSha1,
  );
}

function resolveActiveModelIdentity(activeModel: ActiveModelIdentity): NonNullable<ActiveModelIdentity> {
  if (hasActiveModelIdentity(activeModel) && activeModel) {
    return activeModel;
  }
  return CURRENT_PRODUCTION_MODEL_FALLBACK;
}

export function resolveAuditModelArchive({
  status,
  score,
  scoreBreakdown,
  activeModel,
  createdAt,
}: {
  status: AuditStatus;
  score: number | null | undefined;
  scoreBreakdown: ScoreBreakdown | null | undefined;
  activeModel: ActiveModelIdentity;
  createdAt?: string | number | null;
}): AuditModelArchiveInfo {
  const resolvedActiveModel = resolveActiveModelIdentity(activeModel);
  const auditCreatedAt = getTimestamp(createdAt);
  const modelPublishedAt = getTimestamp(resolvedActiveModel.publishedAt);

  if (!hasScoredResult(status, score)) {
    if (auditCreatedAt !== null && modelPublishedAt !== null && auditCreatedAt < modelPublishedAt) {
      return {
        state: "archived",
        isArchived: true,
        label: "Архив старой оценки",
        reason: "Запуск создан до публикации текущей модели.",
      };
    }

    return {
      state: "not_scored",
      isArchived: false,
      label: "Без итоговой оценки",
      reason: "Аудит ещё не завершён или завершился без расчёта score.",
    };
  }

  const modelInfo = getScoreBreakdownModelInfo(scoreBreakdown);
  if (!modelInfo) {
    return {
      state: "archived",
      isArchived: true,
      label: "Архив старой оценки",
      reason: "В аудите нет сохранённых сведений о модели, поэтому он считается legacy-расчётом.",
    };
  }

  const auditArtifactSha1 = getModelInfoValue(modelInfo, "artifact_sha1");
  const auditArtifactVersion = getModelInfoValue(modelInfo, "artifact_version");
  const auditDatasetVersion = getModelInfoValue(modelInfo, "dataset_version");
  const auditSchemaVersion = getModelInfoValue(modelInfo, "model_schema_version");

  if (resolvedActiveModel.artifactVersion) {
    if (!auditArtifactVersion) {
      return {
        state: "archived",
        isArchived: true,
        label: "Архив старой оценки",
        reason: "В аудите нет версии artifact, поэтому он относится к старым расчётам.",
      };
    }

    const isCurrent = auditArtifactVersion === resolvedActiveModel.artifactVersion;
    return {
      state: isCurrent ? "current" : "archived",
      isArchived: !isCurrent,
      label: isCurrent ? "Актуальная оценка" : "Архив старой оценки",
      reason: isCurrent
        ? "Аудит рассчитан текущей опубликованной версией модели."
        : "Аудит рассчитан старой опубликованной версией модели.",
    };
  }

  if (resolvedActiveModel.artifactSha1 && auditArtifactSha1) {
    const isCurrent = auditArtifactSha1 === resolvedActiveModel.artifactSha1;
    return {
      state: isCurrent ? "current" : "archived",
      isArchived: !isCurrent,
      label: isCurrent ? "Актуальная оценка" : "Архив старой оценки",
      reason: isCurrent
        ? "Аудит рассчитан текущим production artifact."
        : "Аудит рассчитан другим artifact модели.",
    };
  }

  if (resolvedActiveModel.datasetVersion && auditDatasetVersion && auditDatasetVersion !== resolvedActiveModel.datasetVersion) {
    return {
      state: "archived",
      isArchived: true,
      label: "Архив старой оценки",
      reason: "Аудит рассчитан на предыдущем наборе данных модели.",
    };
  }

  if (
    resolvedActiveModel.modelSchemaVersion &&
    auditSchemaVersion &&
    auditSchemaVersion !== resolvedActiveModel.modelSchemaVersion
  ) {
    return {
      state: "archived",
      isArchived: true,
      label: "Архив старой оценки",
      reason: "Аудит рассчитан предыдущей схемой признаков модели.",
    };
  }

  if (
    (resolvedActiveModel.datasetVersion && auditDatasetVersion === resolvedActiveModel.datasetVersion) ||
    (resolvedActiveModel.modelSchemaVersion && auditSchemaVersion === resolvedActiveModel.modelSchemaVersion)
  ) {
    return {
      state: "current",
      isArchived: false,
      label: "Актуальная оценка",
      reason: "Аудит совпадает с текущей версией модели по доступным сведениям.",
    };
  }

  return {
    state: "unknown",
    isArchived: false,
    label: "Версия оценки неизвестна",
    reason: "В аудите не хватает сведений для уверенного сравнения с текущей моделью.",
  };
}
