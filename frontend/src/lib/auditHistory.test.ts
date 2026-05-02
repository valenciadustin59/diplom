import { describe, expect, it } from "vitest";
import {
  buildAuditHistoryModel,
  createRepeatAuditPayload,
  defaultAuditHistoryFilters,
  isStaleAudit,
} from "./auditHistory";
import type { AuditSummary } from "../types";

const now = Date.UTC(2026, 0, 1, 10, 30, 0);

function createSummary(overrides: Partial<AuditSummary> = {}): AuditSummary {
  return {
    id: "audit-1",
    domain: "example.com",
    query: "seo audit",
    targetUrl: "https://example.com/landing",
    topN: 10,
    score: 72,
    status: "completed",
    createdAt: "1 янв. 2026 г., 10:00",
    createdAtTimestamp: Date.UTC(2026, 0, 1, 10, 0, 0),
    scoreBreakdown: {
      final_score: 72,
      rule_score: 70,
      ml_score: 74,
      model_info: {
        model_schema_version: "v3",
        dataset_version: "dataset-v3-d37",
        artifact_version: "dataset-v3-d37-20260501200434",
      },
    },
    ...overrides,
  };
}

describe("audit history model", () => {
  it("excludes locally hidden rows by default and shows them through the hidden focus", () => {
    const visible = createSummary({ id: "visible", domain: "visible.example" });
    const hidden = createSummary({ id: "hidden", domain: "hidden.example" });

    const defaultModel = buildAuditHistoryModel({
      audits: [hidden, visible],
      filters: defaultAuditHistoryFilters,
      hiddenAuditIds: ["hidden"],
      now,
    });
    const hiddenModel = buildAuditHistoryModel({
      audits: [hidden, visible],
      filters: { ...defaultAuditHistoryFilters, focus: "hidden" },
      hiddenAuditIds: ["hidden"],
      now,
    });

    expect(defaultModel.rows.map((row) => row.audit.id)).toEqual(["visible"]);
    expect(hiddenModel.rows.map((row) => row.audit.id)).toEqual(["hidden"]);
    expect(defaultModel.summary.hidden).toBe(1);
    expect(defaultModel.summary.visible).toBe(1);
  });

  it("marks stale in-flight rows as problematic without hiding them", () => {
    const staleAudit = createSummary({
      id: "stale-processing",
      status: "processing",
      createdAtTimestamp: now - 16 * 60 * 1000,
    });

    const model = buildAuditHistoryModel({
      audits: [staleAudit],
      filters: defaultAuditHistoryFilters,
      hiddenAuditIds: [],
      now,
    });

    expect(isStaleAudit(staleAudit, now)).toBe(true);
    expect(model.rows).toHaveLength(1);
    expect(model.rows[0].isStale).toBe(true);
    expect(model.rows[0].isProblematic).toBe(true);
  });

  it("builds a repeat-audit payload from the original row parameters", () => {
    const audit = createSummary({
      query: "купить диван",
      targetUrl: "https://shop.example/sofas",
      topN: 7,
    });

    expect(createRepeatAuditPayload(audit)).toEqual({
      query: "купить диван",
      target_url: "https://shop.example/sofas",
      top_n: 7,
    });
  });

  it("opens the latest successful non-hidden audit", () => {
    const hiddenLatest = createSummary({ id: "latest", status: "completed", createdAtTimestamp: now });
    const visibleSuccessful = createSummary({ id: "older-warning", status: "completed_with_warnings" });
    const failed = createSummary({ id: "failed", status: "failed" });

    const model = buildAuditHistoryModel({
      audits: [hiddenLatest, failed, visibleSuccessful],
      filters: defaultAuditHistoryFilters,
      hiddenAuditIds: ["latest"],
      now,
    });

    expect(model.latestSuccessfulAudit?.id).toBe("older-warning");
  });

  it("keeps old model rows visible because history is a database list, not a model archive", () => {
    const oldModel = createSummary({
      id: "old-model",
      domain: "old.example",
      scoreBreakdown: {
        final_score: 61,
        rule_score: 59,
        ml_score: 63,
        model_info: {
          model_schema_version: "v1",
          dataset_version: "ru_commercial_dataset-20260421-primary",
          artifact_version: "ru_commercial_dataset-20260421-primary-20260421174901",
        },
      },
    });
    const legacyWithoutArtifact = createSummary({
      id: "bootstrap-model",
      domain: "bootstrap.example",
      scoreBreakdown: {
        final_score: 36,
        rule_score: 20,
        ml_score: 66,
        model_info: {
          source: "bootstrap",
          model_type: "RandomForestRegressor",
          dataset_version: null,
        },
      },
    });
    const current = createSummary({ id: "current-model", domain: "current.example", createdAtTimestamp: now + 1000 });
    const oldProcessing = createSummary({
      id: "old-processing",
      domain: "old-processing.example",
      status: "processing",
      score: 0,
      scoreBreakdown: null,
      createdAtTimestamp: Date.UTC(2026, 0, 1, 9, 55, 0),
    });
    const newProcessing = createSummary({
      id: "new-processing",
      domain: "new-processing.example",
      status: "processing",
      score: 0,
      scoreBreakdown: null,
      createdAtTimestamp: Date.UTC(2026, 0, 1, 10, 20, 0),
    });

    const defaultModel = buildAuditHistoryModel({
      audits: [current, newProcessing, oldModel, legacyWithoutArtifact, oldProcessing],
      filters: defaultAuditHistoryFilters,
      hiddenAuditIds: [],
      now,
    });

    expect(defaultModel.rows.map((row) => row.audit.id)).toEqual([
      "current-model",
      "new-processing",
      "old-model",
      "bootstrap-model",
      "old-processing",
    ]);
    expect(defaultModel.summary.visible).toBe(5);
    expect(defaultModel.latestSuccessfulAudit?.id).toBe("current-model");
  });
});
