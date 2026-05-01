import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App, { buildAuditWorkspacePath, getActiveTab } from "./App";

function renderAppAt(path: string): string {
  const originalConsoleError = console.error;
  const consoleError = vi.spyOn(console, "error").mockImplementation((message?: unknown, ...args: unknown[]) => {
    if (typeof message === "string" && message.includes("useLayoutEffect does nothing on the server")) {
      return;
    }
    originalConsoleError(message, ...args);
  });

  try {
    return renderToStaticMarkup(
      createElement(
        MemoryRouter,
        { initialEntries: [path] },
        createElement(App),
      ),
    );
  } finally {
    consoleError.mockRestore();
  }
}

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
    expect(getActiveTab("runtime")).toBe("overview");
  });

  it("routes root history and stack views through the app shell", () => {
    const historyMarkup = renderAppAt("/?view=history");
    expect(historyMarkup).toContain("История аудитов");
    expect(historyMarkup).toContain("Список аудитов");
    expect(historyMarkup).toContain("Состояние рабочего стека");
    expect(historyMarkup).toContain("Открыть последний успешный");
    expect(historyMarkup).toContain("Скрытые локально");
    expect(historyMarkup).toContain("Открыть стек");

    const runtimeMarkup = renderAppAt("/?view=runtime");
    expect(runtimeMarkup).toContain("Стек");
    expect(runtimeMarkup).toContain("Состояние распределённого стека");
    expect(runtimeMarkup).toContain("Загружаем диагностику рабочего стека");
  });
});
