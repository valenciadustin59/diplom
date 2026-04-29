import { describe, expect, it } from "vitest";
import { buildAuditWorkspacePath, getActiveTab } from "./App";

describe("audit workspace routing", () => {
  it("opens audits on overview by default and keeps report as an explicit tab", () => {
    expect(buildAuditWorkspacePath("audit-1")).toBe("/audits/audit-1");
    expect(buildAuditWorkspacePath("audit-1", "overview")).toBe("/audits/audit-1");
    expect(buildAuditWorkspacePath("audit-1", "report")).toBe("/audits/audit-1?tab=report");
    expect(buildAuditWorkspacePath("audit-1", "timeline")).toBe("/audits/audit-1?tab=timeline");
  });

  it("falls back to overview for missing or unknown tab params", () => {
    expect(getActiveTab(null)).toBe("overview");
    expect(getActiveTab("unknown")).toBe("overview");
    expect(getActiveTab("report")).toBe("report");
    expect(getActiveTab("timeline")).toBe("timeline");
  });
});
