import type { RecommendationGroupKey, RecommendationsBundle } from "../types";

export type RecommendationActionStatus = "not_started" | "in_progress" | "fixed" | "ignored";

export type RecommendationActionStateMap = Record<string, RecommendationActionStatus>;

export type RecommendationActionStatusOption = {
  value: RecommendationActionStatus;
  label: string;
};

export type RecommendationActionSummary = {
  total: number;
  notStarted: number;
  inProgress: number;
  fixed: number;
  ignored: number;
  closed: number;
  progressPercent: number;
};

export type RecommendationActionGroupSummary = RecommendationActionSummary & {
  groupKey: RecommendationGroupKey;
  groupLabel: string;
};

export type RecommendationActionItemState = {
  actionKey: string;
  groupKey: RecommendationGroupKey;
  groupLabel: string;
  code: string;
  status: RecommendationActionStatus;
  statusLabel: string;
};

export type RecommendationActionModel = {
  summary: RecommendationActionSummary;
  groupSummaries: RecommendationActionGroupSummary[];
  groupSummariesByKey: Partial<Record<RecommendationGroupKey, RecommendationActionGroupSummary>>;
  itemStatesByKey: Record<string, RecommendationActionItemState>;
};

export const recommendationActionStatusOptions: RecommendationActionStatusOption[] = [
  { value: "not_started", label: "Не начато" },
  { value: "in_progress", label: "В работе" },
  { value: "fixed", label: "Исправлено" },
  { value: "ignored", label: "Игнорируется" },
];

const recommendationActionStatusLabels: Record<RecommendationActionStatus, string> = Object.fromEntries(
  recommendationActionStatusOptions.map((option) => [option.value, option.label]),
) as Record<RecommendationActionStatus, string>;

const recommendationActionStatuses = new Set<RecommendationActionStatus>(
  recommendationActionStatusOptions.map((option) => option.value),
);

export function isRecommendationActionStatus(value: unknown): value is RecommendationActionStatus {
  return typeof value === "string" && recommendationActionStatuses.has(value as RecommendationActionStatus);
}

export function getRecommendationActionStatusLabel(status: RecommendationActionStatus): string {
  return recommendationActionStatusLabels[status];
}

export function getRecommendationActionKey(groupKey: RecommendationGroupKey, code: string): string {
  return `${groupKey}:${code}`;
}

export function getRecommendationActionStatus(
  actionStates: RecommendationActionStateMap,
  actionKey: string,
): RecommendationActionStatus {
  return actionStates[actionKey] ?? "not_started";
}

export function sanitizeRecommendationActionStateMap(value: unknown): RecommendationActionStateMap {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, RecommendationActionStatus] => entry[0].trim().length > 0 && isRecommendationActionStatus(entry[1]),
    ),
  );
}

function createEmptySummary(): RecommendationActionSummary {
  return {
    total: 0,
    notStarted: 0,
    inProgress: 0,
    fixed: 0,
    ignored: 0,
    closed: 0,
    progressPercent: 0,
  };
}

function incrementStatus(summary: RecommendationActionSummary, status: RecommendationActionStatus): RecommendationActionSummary {
  return {
    ...summary,
    total: summary.total + 1,
    notStarted: status === "not_started" ? summary.notStarted + 1 : summary.notStarted,
    inProgress: status === "in_progress" ? summary.inProgress + 1 : summary.inProgress,
    fixed: status === "fixed" ? summary.fixed + 1 : summary.fixed,
    ignored: status === "ignored" ? summary.ignored + 1 : summary.ignored,
    closed: status === "fixed" || status === "ignored" ? summary.closed + 1 : summary.closed,
  };
}

function finalizeSummary(summary: RecommendationActionSummary): RecommendationActionSummary {
  return {
    ...summary,
    progressPercent: summary.total > 0 ? Math.round((summary.closed / summary.total) * 100) : 0,
  };
}

export function buildRecommendationActionModel(
  recommendations: RecommendationsBundle | null | undefined,
  actionStates: RecommendationActionStateMap,
): RecommendationActionModel {
  const itemStatesByKey: Record<string, RecommendationActionItemState> = {};
  const groupSummaries = (recommendations?.groups ?? []).map((group) => {
    const groupSummary = group.items.reduce<RecommendationActionSummary>((summary, item) => {
      const actionKey = getRecommendationActionKey(group.key, item.code);
      const status = getRecommendationActionStatus(actionStates, actionKey);

      itemStatesByKey[actionKey] = {
        actionKey,
        groupKey: group.key,
        groupLabel: group.label,
        code: item.code,
        status,
        statusLabel: getRecommendationActionStatusLabel(status),
      };

      return incrementStatus(summary, status);
    }, createEmptySummary());

    return {
      ...finalizeSummary(groupSummary),
      groupKey: group.key,
      groupLabel: group.label,
    };
  });
  const summary = finalizeSummary(
    Object.values(itemStatesByKey).reduce(
      (currentSummary, item) => incrementStatus(currentSummary, item.status),
      createEmptySummary(),
    ),
  );

  return {
    summary,
    groupSummaries,
    groupSummariesByKey: Object.fromEntries(groupSummaries.map((groupSummary) => [groupSummary.groupKey, groupSummary])),
    itemStatesByKey,
  };
}
