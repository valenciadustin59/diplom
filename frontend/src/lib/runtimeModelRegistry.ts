import type {
  RuntimeModelRegistryRecord,
  RuntimeModelRegistryResponse,
  RuntimeRollbackChecklistItem,
} from "../types";
import type { RuntimeMetric, RuntimeTone } from "./runtimeHealth";

export type RuntimeModelRegistryRecordRow = {
  key: string;
  role: string;
  roleLabel: string;
  statusLabel: string;
  tone: RuntimeTone;
  modelLabel: string;
  datasetLabel: string;
  artifactLabel: string;
  shaLabel: string;
  metadataLabel: string;
  publishLabel: string;
  evidenceLabels: string[];
  warningLabels: string[];
};

export type RuntimeRollbackChecklistRow = {
  key: string;
  label: string;
  detail: string;
  statusLabel: string;
  tone: RuntimeTone;
  pathLabel: string | null;
};

export type RuntimeRollbackCheckView = {
  status: string;
  statusLabel: string;
  tone: RuntimeTone;
  dryRunLabel: string;
  targetLabel: string;
  metadataLabel: string;
  checklistRows: RuntimeRollbackChecklistRow[];
};

export type RuntimeModelRegistryView = {
  status: string;
  statusLabel: string;
  tone: RuntimeTone;
  empty: boolean;
  checkedAtLabel: string;
  shortLabel: string;
  detail: string;
  summaryMetrics: RuntimeMetric[];
  records: RuntimeModelRegistryRecordRow[];
  rollbackCheck: RuntimeRollbackCheckView | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? new Intl.NumberFormat("ru-RU").format(value) : "—";
}

function formatCheckedAt(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(date);
}

function shortSha(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

function roleLabel(role: string): string {
  if (role === "current") {
    return "current";
  }
  if (role === "rollback") {
    return "rollback";
  }
  if (role === "archived") {
    return "archive";
  }
  return role;
}

function statusTone(status: string | null | undefined): RuntimeTone {
  if (status === "ok" || status === "pass" || status === "info") {
    return "ok";
  }
  if (status === "warning" || status === "warn") {
    return "warning";
  }
  if (status === "empty") {
    return "muted";
  }
  return status === "error" ? "error" : "warning";
}

function statusLabel(status: string | null | undefined): string {
  if (status === "ok" || status === "pass") {
    return "готово";
  }
  if (status === "warning" || status === "warn") {
    return "требует проверки";
  }
  if (status === "info") {
    return "информация";
  }
  if (status === "empty") {
    return "нет данных";
  }
  if (status === "error") {
    return "ошибка";
  }
  return status || "неизвестно";
}

function buildEvidenceLabels(record: RuntimeModelRegistryRecord): string[] {
  const evidence = isRecord(record.evidence) ? record.evidence : {};
  return [
    asString(evidence.publish_report_path) ? `publish report: ${asString(evidence.publish_report_path)}` : null,
    asString(evidence.publish_report_markdown_path) ? `report md: ${asString(evidence.publish_report_markdown_path)}` : null,
    asString(evidence.shadow_report_path) ? `shadow: ${asString(evidence.shadow_report_path)}` : null,
    asString(evidence.smoke_summary_path) ? `smoke: ${asString(evidence.smoke_summary_path)}` : null,
    asString(evidence.golden_replay_report_path) ? `golden replay: ${asString(evidence.golden_replay_report_path)}` : null,
  ].filter((label): label is string => Boolean(label));
}

function buildWarningLabels(record: RuntimeModelRegistryRecord): string[] {
  return (record.warnings ?? []).map((warning) =>
    warning.path ? `${warning.message} (${warning.path})` : warning.message,
  );
}

function buildRecordRow(record: RuntimeModelRegistryRecord): RuntimeModelRegistryRecordRow {
  const model = isRecord(record.model) ? record.model : {};
  const dataset = isRecord(record.dataset) ? record.dataset : {};
  const publish = isRecord(record.publish) ? record.publish : {};
  const role = asString(record.role) ?? "unknown";
  const status = asString(record.status) ?? "warning";
  const modelType = asString(model.model_type) ?? "model unknown";
  const schema = asString(model.model_schema_version) ?? "schema unknown";
  const featureCount = asNumber(model.feature_count);
  const artifactVersion = asString(model.artifact_version) ?? asString(record.artifact_path) ?? "artifact unknown";
  const datasetVersion = asString(dataset.dataset_version) ?? "dataset unknown";
  const rowsCount = asNumber(dataset.rows_count);
  const queriesCount = asNumber(dataset.queries_count);
  const selectedCandidate = asString(publish.selected_candidate) ?? asString(publish.candidate_name);
  const publishRecommendation = asString(publish.publish_recommendation) ?? asString(publish.publish_action);

  return {
    key: record.id,
    role,
    roleLabel: roleLabel(role),
    statusLabel: statusLabel(status),
    tone: statusTone(status),
    modelLabel: `${modelType} · ${schema}${featureCount === null ? "" : ` · ${featureCount} признаков`}`,
    datasetLabel: `${datasetVersion} · ${formatCount(rowsCount)} строк · ${formatCount(queriesCount)} запросов`,
    artifactLabel: artifactVersion,
    shaLabel: `artifact ${shortSha(record.artifact_sha1)} · metadata ${shortSha(record.metadata_sha1)}`,
    metadataLabel: record.metadata_path ?? "metadata sidecar не найден",
    publishLabel: selectedCandidate
      ? `${selectedCandidate}${publishRecommendation ? ` · ${publishRecommendation}` : ""}`
      : publishRecommendation || "решение публикации не указано",
    evidenceLabels: buildEvidenceLabels(record),
    warningLabels: buildWarningLabels(record),
  };
}

function buildChecklistRow(item: RuntimeRollbackChecklistItem): RuntimeRollbackChecklistRow {
  const status = asString(item.status) ?? "warn";
  return {
    key: item.code,
    label: item.label,
    detail: item.detail,
    statusLabel: statusLabel(status),
    tone: statusTone(status),
    pathLabel: item.path ?? null,
  };
}

function buildRollbackCheckView(registry: RuntimeModelRegistryResponse): RuntimeRollbackCheckView | null {
  const check = registry.rollback_check;
  if (!check) {
    return null;
  }
  const status = asString(check.status) ?? "warning";
  return {
    status,
    statusLabel: statusLabel(status),
    tone: statusTone(status),
    dryRunLabel: check.dry_run_only ? "dry-run only: UI не выполняет rollback" : "rollback execution не ограничен",
    targetLabel: `artifact ${shortSha(check.target_artifact_sha1)} · ${check.target_artifact_path ?? "path не указан"}`,
    metadataLabel: `metadata ${shortSha(check.target_metadata_sha1)} · ${check.target_metadata_path ?? "path не указан"}`,
    checklistRows: (check.checklist ?? []).map(buildChecklistRow),
  };
}

function buildSummaryMetrics(registry: RuntimeModelRegistryResponse): RuntimeMetric[] {
  const summary = registry.summary ?? {
    record_count: 0,
    current_count: 0,
    rollback_count: 0,
    archived_count: 0,
    warning_count: 0,
  };
  const rollbackStatus = asString(registry.rollback_check?.status) ?? "warning";
  return [
    {
      label: "Records",
      value: formatCount(summary.record_count),
      note: `${formatCount(summary.current_count)} current, ${formatCount(summary.rollback_count)} rollback, ${formatCount(summary.archived_count)} archive.`,
      tone: summary.record_count > 0 ? "ok" : "muted",
    },
    {
      label: "Warnings",
      value: formatCount(summary.warning_count),
      note: "Проблемы с artifact/metadata/SHA1 в registry.",
      tone: summary.warning_count > 0 ? "warning" : "ok",
    },
    {
      label: "Rollback check",
      value: statusLabel(rollbackStatus),
      note: "Dry-run checklist перед ручной инженерной операцией rollback.",
      tone: statusTone(rollbackStatus),
    },
  ];
}

export function buildModelRegistryView(
  registry: RuntimeModelRegistryResponse | null | undefined,
): RuntimeModelRegistryView | null {
  if (!registry) {
    return null;
  }
  const status = asString(registry.status) ?? "warning";
  const records = (registry.records ?? []).map(buildRecordRow);
  const current = records.find((record) => record.role === "current");
  const rollback = records.find((record) => record.role === "rollback");
  const warningCount = registry.summary?.warning_count ?? 0;
  const empty = status === "empty" || records.length === 0;

  return {
    status,
    statusLabel: statusLabel(status),
    tone: statusTone(status),
    empty,
    checkedAtLabel: formatCheckedAt(registry.checked_at),
    shortLabel: empty
      ? "Registry пуст"
      : rollback
        ? `${current?.artifactLabel ?? "current artifact"} → rollback ${rollback.artifactLabel}`
        : current?.artifactLabel ?? "Model registry",
    detail:
      warningCount > 0
        ? `Registry найден, но есть предупреждения по metadata/SHA1: ${warningCount}.`
        : "Current artifact, rollback target и evidence reports доступны в read-only registry.",
    summaryMetrics: buildSummaryMetrics(registry),
    records,
    rollbackCheck: buildRollbackCheckView(registry),
  };
}
