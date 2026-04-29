import { describe, expect, it } from "vitest";
import type { Recommendation, RecommendationGroup, RecommendationsBundle } from "../types";
import {
  buildRecommendationActionModel,
  getRecommendationActionKey,
  getRecommendationActionStatusLabel,
  sanitizeRecommendationActionStateMap,
} from "./recommendationActions";

function createRecommendation(code: string, title: string): Recommendation {
  return {
    code,
    priority: "high",
    impact: "high",
    title,
    message: `${title} message`,
    expected_outcome: `${title} outcome`,
    evidence: [],
    related_metrics: [],
  };
}

function createGroup(overrides: Partial<RecommendationGroup> = {}): RecommendationGroup {
  return {
    key: "technical_seo",
    label: "Technical SEO",
    description: "Technical recommendations",
    status: "critical",
    items: [],
    deviations: [],
    empty_state: "No issues",
    ...overrides,
  };
}

function createBundle(groups: RecommendationGroup[]): RecommendationsBundle {
  return {
    schema_version: "recommendations-v2",
    summary: {
      total_recommendations: groups.reduce((total, group) => total + group.items.length, 0),
      high_priority_count: groups.reduce((total, group) => total + group.items.filter((item) => item.priority === "high").length, 0),
      medium_priority_count: 0,
      low_priority_count: 0,
      groups_with_issues: groups.filter((group) => group.items.length > 0).length,
      competitor_context: true,
      score_gap_vs_competitors: -8,
    },
    groups,
  };
}

describe("recommendation action model", () => {
  it("defaults every recommendation action to not started", () => {
    const bundle = createBundle([
      createGroup({ items: [createRecommendation("TECHNICAL_TITLE", "Усилить title")] }),
    ]);

    const model = buildRecommendationActionModel(bundle, {});
    const actionKey = getRecommendationActionKey("technical_seo", "TECHNICAL_TITLE");

    expect(model.itemStatesByKey[actionKey].status).toBe("not_started");
    expect(model.itemStatesByKey[actionKey].statusLabel).toBe("Не начато");
    expect(model.summary).toMatchObject({ total: 1, notStarted: 1, closed: 0, progressPercent: 0 });
  });

  it("summarizes fixed and ignored actions as closed progress by group", () => {
    const bundle = createBundle([
      createGroup({
        items: [
          createRecommendation("TECHNICAL_TITLE", "Усилить title"),
          createRecommendation("TECHNICAL_CANONICAL", "Проверить canonical"),
        ],
      }),
      createGroup({
        key: "commercial_trust",
        label: "Commercial and Trust",
        status: "attention",
        items: [createRecommendation("COMMERCIAL_CONTACTS", "Добавить контакты")],
      }),
    ]);

    const model = buildRecommendationActionModel(bundle, {
      [getRecommendationActionKey("technical_seo", "TECHNICAL_TITLE")]: "fixed",
      [getRecommendationActionKey("technical_seo", "TECHNICAL_CANONICAL")]: "in_progress",
      [getRecommendationActionKey("commercial_trust", "COMMERCIAL_CONTACTS")]: "ignored",
    });

    expect(model.summary).toMatchObject({ total: 3, fixed: 1, ignored: 1, inProgress: 1, closed: 2, progressPercent: 67 });
    expect(model.groupSummariesByKey.technical_seo).toMatchObject({ total: 2, fixed: 1, inProgress: 1, closed: 1, progressPercent: 50 });
    expect(model.groupSummariesByKey.commercial_trust).toMatchObject({ total: 1, ignored: 1, closed: 1, progressPercent: 100 });
  });

  it("keeps only valid persisted status values", () => {
    expect(
      sanitizeRecommendationActionStateMap({
        "technical_seo:TECHNICAL_TITLE": "fixed",
        "technical_seo:UNKNOWN": "done",
        "": "ignored",
        invalid: 10,
      }),
    ).toEqual({
      "technical_seo:TECHNICAL_TITLE": "fixed",
    });
  });

  it("exposes Russian status labels", () => {
    expect(getRecommendationActionStatusLabel("in_progress")).toBe("В работе");
    expect(getRecommendationActionStatusLabel("fixed")).toBe("Исправлено");
    expect(getRecommendationActionStatusLabel("ignored")).toBe("Игнорируется");
  });
});
