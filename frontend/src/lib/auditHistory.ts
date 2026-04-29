import type { AuditCreatePayload, AuditStatus, AuditSummary } from "../types";

export type AuditHistoryFocusFilter = "all" | "successful" | "problematic" | "stale" | "hidden";

export type AuditHistoryFilters = {
  status: "all" | AuditStatus;
  domain: string;
  search: string;
  focus: AuditHistoryFocusFilter;
};

export type AuditHistoryRow = {
  audit: AuditSummary;
  isHidden: boolean;
  isProblematic: boolean;
  isStale: boolean;
  isSuccessful: boolean;
};

export type AuditHistorySummary = {
  total: number;
  visible: number;
  successful: number;
  problematic: number;
  stale: number;
  hidden: number;
  filtered: number;
};

export type AuditHistoryModel = {
  rows: AuditHistoryRow[];
  latestSuccessfulAudit: AuditSummary | null;
  summary: AuditHistorySummary;
  hasActiveFilters: boolean;
};

const STALE_AUDIT_THRESHOLD_MS = 15 * 60 * 1000;

export const defaultAuditHistoryFilters: AuditHistoryFilters = {
  status: "all",
  domain: "",
  search: "",
  focus: "all",
};

export function isSuccessfulAudit(audit: AuditSummary): boolean {
  return audit.status === "completed" || audit.status === "completed_with_warnings";
}

export function isStaleAudit(audit: AuditSummary, now: number): boolean {
  if (audit.status !== "queued" && audit.status !== "processing") {
    return false;
  }

  if (audit.createdAtTimestamp === null || audit.createdAtTimestamp > now) {
    return false;
  }

  return now - audit.createdAtTimestamp >= STALE_AUDIT_THRESHOLD_MS;
}

export function isProblematicAudit(audit: AuditSummary, now: number): boolean {
  return audit.status === "failed" || audit.status === "completed_with_warnings" || isStaleAudit(audit, now);
}

export function createRepeatAuditPayload(audit: AuditSummary): AuditCreatePayload {
  return {
    query: audit.query,
    target_url: audit.targetUrl,
    top_n: audit.topN,
  };
}

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function matchesFocus(row: AuditHistoryRow, focus: AuditHistoryFocusFilter): boolean {
  switch (focus) {
    case "all":
      return !row.isHidden;
    case "successful":
      return !row.isHidden && row.isSuccessful;
    case "problematic":
      return !row.isHidden && row.isProblematic;
    case "stale":
      return !row.isHidden && row.isStale;
    case "hidden":
      return row.isHidden;
    default:
      return !row.isHidden;
  }
}

function matchesFilters(row: AuditHistoryRow, filters: AuditHistoryFilters): boolean {
  const domainFilter = normalizeText(filters.domain);
  const searchFilter = normalizeText(filters.search);
  const searchValue = normalizeText(`${row.audit.query} ${row.audit.domain} ${row.audit.targetUrl}`);

  return (
    matchesFocus(row, filters.focus) &&
    (filters.status === "all" || row.audit.status === filters.status) &&
    (!domainFilter || normalizeText(row.audit.domain).includes(domainFilter)) &&
    (!searchFilter || searchValue.includes(searchFilter))
  );
}

function isFilterActive(filters: AuditHistoryFilters): boolean {
  return (
    filters.status !== "all" ||
    filters.focus !== "all" ||
    filters.domain.trim().length > 0 ||
    filters.search.trim().length > 0
  );
}

export function buildAuditHistoryModel({
  audits,
  filters,
  hiddenAuditIds,
  now,
}: {
  audits: AuditSummary[];
  filters: AuditHistoryFilters;
  hiddenAuditIds: string[];
  now: number;
}): AuditHistoryModel {
  const hiddenIdSet = new Set(hiddenAuditIds);
  const allRows = audits.map((audit) => {
    const isHidden = hiddenIdSet.has(audit.id);
    const isStale = isStaleAudit(audit, now);
    const isSuccessful = isSuccessfulAudit(audit);

    return {
      audit,
      isHidden,
      isProblematic: audit.status === "failed" || audit.status === "completed_with_warnings" || isStale,
      isStale,
      isSuccessful,
    };
  });
  const visibleRows = allRows.filter((row) => !row.isHidden);
  const rows = allRows.filter((row) => matchesFilters(row, filters));

  return {
    rows,
    latestSuccessfulAudit: visibleRows.find((row) => row.isSuccessful)?.audit ?? null,
    summary: {
      total: allRows.length,
      visible: visibleRows.length,
      successful: visibleRows.filter((row) => row.isSuccessful).length,
      problematic: visibleRows.filter((row) => row.isProblematic).length,
      stale: visibleRows.filter((row) => row.isStale).length,
      hidden: allRows.length - visibleRows.length,
      filtered: rows.length,
    },
    hasActiveFilters: isFilterActive(filters),
  };
}
