import { describe, expect, it } from "vitest";
import {
  getFetchMethodLabel,
  getHumanReadableLabel,
  getIntentLabel,
  getRecommendationGroupDescription,
  getRecommendationGroupEmptyState,
  getRecommendationGroupLabel,
} from "./terminology";

describe("interface terminology", () => {
  it("uses Russian primary labels for recommendation groups", () => {
    expect(getRecommendationGroupLabel("technical_seo")).toBe("Техническое SEO");
    expect(getRecommendationGroupLabel("commercial_trust")).toBe("Коммерция и доверие");
    expect(
      getRecommendationGroupDescription({
        key: "semantic_intent",
        description: "Semantic issues",
      }),
    ).toContain("поисковым намерением");
    expect(
      getRecommendationGroupEmptyState({
        key: "competitor_gap",
        empty_state: "No issues",
      }),
    ).toContain("Существенных отставаний");
  });

  it("keeps technical values readable without exposing raw English labels first", () => {
    expect(getIntentLabel("local_commercial")).toBe("локально-коммерческий");
    expect(getFetchMethodLabel("http_retry")).toBe("HTTP с повтором");
    expect(getHumanReadableLabel("Semantic relevance")).toBe("Смысловое соответствие");
    expect(getHumanReadableLabel("unknown_metric")).toBe("unknown_metric");
    expect(getHumanReadableLabel(null)).toBe("—");
  });
});
