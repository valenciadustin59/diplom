import type {
  Recommendation,
  RecommendationGroupKey,
  RecommendationsBundle,
} from "../types";

export type RecommendationPreviewItem = Recommendation & {
  groupKey: RecommendationGroupKey;
  groupLabel: string;
};

const priorityOrder = {
  high: 0,
  medium: 1,
  low: 2,
} as const;

const groupOrder: Record<RecommendationGroupKey, number> = {
  technical_seo: 0,
  commercial_trust: 1,
  semantic_intent: 2,
  competitor_gap: 3,
};

export function flattenRecommendationItems(
  bundle: RecommendationsBundle | null | undefined,
): RecommendationPreviewItem[] {
  if (!bundle) {
    return [];
  }

  return bundle.groups
    .flatMap((group) =>
      group.items.map((item) => ({
        ...item,
        groupKey: group.key,
        groupLabel: group.label,
      })),
    )
    .sort(
      (left, right) =>
        priorityOrder[left.priority] - priorityOrder[right.priority] ||
        groupOrder[left.groupKey] - groupOrder[right.groupKey] ||
        left.title.localeCompare(right.title, "ru"),
    );
}

export function getTopRecommendationItems(
  bundle: RecommendationsBundle | null | undefined,
  limit = 3,
): RecommendationPreviewItem[] {
  return flattenRecommendationItems(bundle).slice(0, limit);
}
