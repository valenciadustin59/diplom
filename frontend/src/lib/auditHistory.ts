import type { AuditCreatePayload, AuditStatus, AuditSummary } from "../types";
import { resolveAuditModelArchive, type ActiveModelIdentity, type AuditModelArchiveInfo } from "./auditArchive";

export type AuditHistoryFocusFilter = "all" | "successful" | "problematic" | "stale" | "archived" | "hidden";

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
  isArchived: boolean;
  archiveInfo: AuditModelArchiveInfo;
};

export type AuditHistorySummary = {
  total: number;
  visible: number;
  successful: number;
  problematic: number;
  stale: number;
  archived: number;
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
      return !row.isHidden && !row.isArchived;
    case "successful":
      return !row.isHidden && !row.isArchived && row.isSuccessful;
    case "problematic":
      return !row.isHidden && !row.isArchived && row.isProblematic;
    case "stale":
      return !row.isHidden && !row.isArchived && row.isStale;
    case "archived":
      return !row.isHidden && row.isArchived;
    case "hidden":
      return row.isHidden;
    default:
      return !row.isHidden && !row.isArchived;
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
  activeModel,
  now,
}: {
  audits: AuditSummary[];
  filters: AuditHistoryFilters;
  hiddenAuditIds: string[];
  activeModel?: ActiveModelIdentity;
  now: number;
}): AuditHistoryModel {
  const hiddenIdSet = new Set(hiddenAuditIds);
  const allRows = audits.map((audit) => {
    const isHidden = hiddenIdSet.has(audit.id);
    const isStale = isStaleAudit(audit, now);
    const isSuccessful = isSuccessfulAudit(audit);
    const archiveInfo = resolveAuditModelArchive({
      status: audit.status,
      score: audit.score,
      scoreBreakdown: audit.scoreBreakdown,
      activeModel,
      createdAt: audit.createdAtTimestamp,
    });

    return {
      audit,
      isHidden,
      isProblematic: audit.status === "failed" || audit.status === "completed_with_warnings" || isStale,
      isStale,
      isSuccessful,
      isArchived: archiveInfo.isArchived,
      archiveInfo,
    };
  });
  const visibleRows = allRows.filter((row) => !row.isHidden);
  const activeVisibleRows = visibleRows.filter((row) => !row.isArchived);
  const rows = allRows.filter((row) => matchesFilters(row, filters));

  return {
    rows,
    latestSuccessfulAudit: activeVisibleRows.find((row) => row.isSuccessful)?.audit ?? null,
    summary: {
      total: allRows.length,
      visible: activeVisibleRows.length,
      successful: activeVisibleRows.filter((row) => row.isSuccessful).length,
      problematic: activeVisibleRows.filter((row) => row.isProblematic).length,
      stale: activeVisibleRows.filter((row) => row.isStale).length,
      archived: visibleRows.filter((row) => row.isArchived).length,
      hidden: allRows.length - visibleRows.length,
      filtered: rows.length,
    },
    hasActiveFilters: isFilterActive(filters),
  };
}
