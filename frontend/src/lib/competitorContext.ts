import type { ComparisonSummary, CompetitorResult } from "../types";

export type CompetitorContextStats = {
  accepted: number;
  collected: number;
  discarded: number;
  replacements: number;
  failed: number;
  requestedTopN: number | null;
  hasQualityV2: boolean;
};

function asCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.round(value)) : null;
}

function pluralRu(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) {
    return one;
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return few;
  }
  return many;
}

function formatCountPhrase(count: number, one: string, few: string, many: string): string {
  return `${count} ${pluralRu(count, one, few, many)}`;
}

function isQualityV2(summary: ComparisonSummary | null | undefined): boolean {
  const quality = summary?.competitor_context_quality;
  return Boolean(
    quality &&
      (asCount(quality.collected_candidates) !== null ||
        asCount(quality.accepted_competitors) !== null ||
        asCount(quality.discarded_competitors) !== null ||
        asCount(quality.replacement_attempts) !== null ||
        quality.schema_version === "competitor-context-quality-v2"),
  );
}

export function isExcludedCompetitor(competitor: CompetitorResult): boolean {
  return competitor.competitor_context_status === "discarded" || competitor.competitor_context_status === "unused";
}

export function getAcceptedCompetitors(competitors: CompetitorResult[] | null | undefined): CompetitorResult[] {
  return (competitors ?? []).filter((competitor) => !isExcludedCompetitor(competitor));
}

export function getExcludedCompetitors(competitors: CompetitorResult[] | null | undefined): CompetitorResult[] {
  return (competitors ?? []).filter(isExcludedCompetitor);
}

export function getCompetitorContextStatusLabel(status: CompetitorResult["competitor_context_status"]): string {
  if (status === "accepted") {
    return "В расчёте";
  }
  if (status === "discarded") {
    return "Исключён";
  }
  if (status === "unused") {
    return "Не использовался";
  }
  return "Обработан";
}

export function buildCompetitorContextStats(
  summary: ComparisonSummary | null | undefined,
  competitors?: CompetitorResult[] | null,
): CompetitorContextStats {
  const quality = summary?.competitor_context_quality;
  const acceptedFromResults = getAcceptedCompetitors(competitors).filter(
    (competitor) => competitor.fetch_status === "success" && typeof competitor.score === "number",
  ).length;
  const excludedFromResults = getExcludedCompetitors(competitors).length;
  const found = asCount(summary?.competitors_found) ?? asCount(summary?.competitors_count) ?? competitors?.length ?? 0;
  const analyzed =
    asCount(summary?.competitors_analyzed) ?? asCount(summary?.competitors_count) ?? acceptedFromResults;
  const failed = asCount(summary?.competitors_failed) ?? Math.max(0, found - analyzed);
  const hasQualityV2 = isQualityV2(summary);
  const accepted = asCount(quality?.accepted_competitors) ?? analyzed;
  const collected = Math.max(
    accepted,
    asCount(quality?.collected_candidates) ?? Math.max(found, accepted + excludedFromResults),
  );

  return {
    accepted,
    collected,
    discarded: asCount(quality?.discarded_competitors) ?? excludedFromResults,
    replacements: asCount(quality?.replacement_attempts) ?? 0,
    failed,
    requestedTopN: asCount(quality?.requested_top_n),
    hasQualityV2,
  };
}

export function formatCompetitorContextSummary(stats: CompetitorContextStats): string | null {
  if (stats.hasQualityV2) {
    if (stats.collected === 0 && stats.accepted === 0) {
      return null;
    }

    const main = `${stats.accepted === 1 ? "В расчёт вошёл" : "В расчёт вошло"} ${formatCountPhrase(
      stats.accepted,
      "валидный конкурент",
      "валидных конкурента",
      "валидных конкурентов",
    )} из ${stats.collected}`;
    const details: string[] = [];

    if (stats.replacements > 0) {
      details.push(formatCountPhrase(stats.replacements, "заменён", "заменены", "заменены"));
    }
    if (stats.discarded > 0) {
      details.push(formatCountPhrase(stats.discarded, "исключён", "исключены", "исключены"));
    }

    return details.length > 0 ? `${main}; ${details.join(", ")}.` : `${main}.`;
  }

  if (stats.collected === 0 && stats.accepted === 0) {
    return null;
  }

  const main = `Обработано ${stats.accepted} из ${stats.collected} конкурентных страниц`;
  return stats.failed > 0
    ? `${main}; ${formatCountPhrase(stats.failed, "страница недоступна", "страницы недоступны", "страниц недоступны")}.`
    : `${main}.`;
}
