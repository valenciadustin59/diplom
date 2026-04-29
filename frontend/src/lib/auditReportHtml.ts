import { buildAuditReportModel, type AuditReportInput, type ReportMetric } from "./auditReport";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMetricHtml(metric: ReportMetric): string {
  return `<article class="metric"><span>${escapeHtml(metric.label)}</span><strong>${escapeHtml(metric.value)}</strong>${
    metric.note ? `<p>${escapeHtml(metric.note)}</p>` : ""
  }</article>`;
}

export function createAuditReportHtml(input: AuditReportInput, options: { autoPrint?: boolean } = {}): string {
  const report = buildAuditReportModel(input);
  const topRecommendations =
    report.topRecommendations.length > 0
      ? report.topRecommendations
          .map(
            (item) =>
              `<article class="action"><span>${escapeHtml(item.priorityLabel)} / ${escapeHtml(item.groupLabel)}</span><h3>${escapeHtml(
                item.title,
              )}</h3><p>${escapeHtml(item.message)}</p><small>${escapeHtml(item.expectedOutcome)}</small></article>`,
          )
          .join("")
      : "<p>Рекомендации пока не сформированы.</p>";
  const stages =
    report.stageRows.length > 0
      ? report.stageRows
          .map(
            (stage) =>
              `<tr><td>${escapeHtml(stage.stage)}</td><td>${stage.completed}</td><td>${stage.failed}</td><td>${escapeHtml(
                stage.duration,
              )}</td><td>${escapeHtml(stage.criticalPath)}</td></tr>`,
          )
          .join("")
      : '<tr><td colspan="5">Timeline diagnostics пока недоступны.</td></tr>';
  const competitors =
    report.competitors.length > 0
      ? report.competitors
          .map(
            (competitor) =>
              `<tr><td>${escapeHtml(competitor.domain)}</td><td>${escapeHtml(competitor.score)}</td><td>${escapeHtml(
                competitor.status,
              )}</td><td>${escapeHtml(competitor.url)}</td></tr>`,
          )
          .join("")
      : '<tr><td colspan="4">Конкурентные страницы пока не обработаны.</td></tr>';

  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(report.title)}</title>
  <style>
    :root { font-family: Inter, Segoe UI, Arial, sans-serif; color: #111827; background: #f5f7fc; }
    body { margin: 0; padding: 32px; }
    main { max-width: 1040px; margin: 0 auto; display: grid; gap: 24px; }
    section, header { background: #fff; border: 1px solid #e6ebf5; border-radius: 24px; padding: 24px; box-shadow: 0 16px 40px rgba(31,45,78,.06); }
    h1, h2, h3, p { margin-top: 0; }
    h1 { font-size: 34px; letter-spacing: -0.04em; }
    h2 { font-size: 20px; }
    .muted, .metric span, small { color: #667085; }
    .score { font-size: 52px; font-weight: 800; color: #335fce; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .metric { padding: 14px; border-radius: 16px; background: #f8faff; border: 1px solid #edf1fa; }
    .metric strong { display: block; margin-top: 6px; font-size: 18px; }
    .metric p { margin: 8px 0 0; color: #667085; font-size: 13px; }
    .actions { display: grid; gap: 12px; }
    .action { padding: 16px; border-left: 4px solid #4f7cff; border-radius: 16px; background: #f8faff; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px 10px; border-bottom: 1px solid #edf1fa; text-align: left; vertical-align: top; }
    th { color: #667085; font-size: 13px; }
    @media print { body { padding: 0; background: #fff; } section, header { box-shadow: none; page-break-inside: avoid; } }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">Audit report / generated ${escapeHtml(report.generatedAt)}</p>
      <h1>${escapeHtml(report.domain)}</h1>
      <p>${escapeHtml(report.query)} · ${escapeHtml(report.targetUrl)}</p>
      <div class="score">${escapeHtml(report.scoreLabel)}</div>
      <p>${escapeHtml(report.scoreVerdict)}</p>
    </header>
    <section>
      <h2>Executive Summary</h2>
      <ul>${report.summary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>
    <section>
      <h2>Score And ML Explanation</h2>
      <div class="grid">
        ${renderMetricHtml({ label: "Final score", value: report.scoreBreakdown.finalScore })}
        ${renderMetricHtml({ label: "Rule-based score", value: report.scoreBreakdown.ruleScore })}
        ${renderMetricHtml({ label: "ML score", value: report.scoreBreakdown.mlScore })}
        ${renderMetricHtml({ label: "Status", value: report.statusLabel })}
      </div>
      <p class="muted">${escapeHtml(report.scoreBreakdown.methodology)}</p>
    </section>
    <section>
      <h2>SEO Evidence</h2>
      <div class="grid">${report.seoMetrics.map(renderMetricHtml).join("")}</div>
    </section>
    <section>
      <h2>Competitor Evidence</h2>
      <div class="grid">${report.competitorMetrics.map(renderMetricHtml).join("")}</div>
      <table><thead><tr><th>Domain</th><th>Score</th><th>Status</th><th>URL</th></tr></thead><tbody>${competitors}</tbody></table>
    </section>
    <section>
      <h2>Recommendation Plan</h2>
      <div class="grid">${report.recommendationMetrics.map(renderMetricHtml).join("")}</div>
      <div class="actions">${topRecommendations}</div>
    </section>
    <section>
      <h2>Distributed Runtime Evidence</h2>
      <div class="grid">${report.runtimeMetrics.map(renderMetricHtml).join("")}</div>
      <table><thead><tr><th>Stage</th><th>Completed</th><th>Failed</th><th>Duration</th><th>Critical path</th></tr></thead><tbody>${stages}</tbody></table>
    </section>
  </main>
  ${options.autoPrint ? "<script>window.addEventListener('load', () => setTimeout(() => window.print(), 250));</script>" : ""}
</body>
</html>`;
}
