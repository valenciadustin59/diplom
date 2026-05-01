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
  const recommendationRows =
    report.recommendationActions.length > 0
      ? report.recommendationActions
          .map(
            (item) =>
              `<tr><td>${escapeHtml(item.priorityLabel)}</td><td>${escapeHtml(item.groupLabel)}</td><td><strong>${escapeHtml(
                item.title,
              )}</strong><br><small>Код: ${escapeHtml(item.code)}</small></td><td>${escapeHtml(
                item.message,
              )}<br><small>Ожидаемый эффект: ${escapeHtml(item.expectedOutcome)}</small></td></tr>`,
          )
          .join("")
      : '<tr><td colspan="4">Рекомендации пока не сформированы.</td></tr>';
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
      : '<tr><td colspan="5">Диагностика таймлайна пока недоступна.</td></tr>';
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
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px 10px; border-bottom: 1px solid #edf1fa; text-align: left; vertical-align: top; }
    th { color: #667085; font-size: 13px; }
    .recommendations td { font-size: 13px; }
    .recommendations small { display: block; margin-top: 4px; }
    @media print { body { padding: 0; background: #fff; } section, header { box-shadow: none; page-break-inside: avoid; } }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">SEO-отчёт / сформирован ${escapeHtml(report.generatedAt)}</p>
      <h1>${escapeHtml(report.domain)}</h1>
      <p>${escapeHtml(report.query)} · ${escapeHtml(report.targetUrl)}</p>
      <div class="score">${escapeHtml(report.scoreLabel)}</div>
      <p>${escapeHtml(report.scoreVerdict)}</p>
    </header>
    <section>
      <h2>Краткий вывод</h2>
      <ul>${report.summary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>
    <section>
      <h2>Объяснение оценки и ML-калибровки</h2>
      <div class="grid">
        ${renderMetricHtml({ label: "Итоговая оценка", value: report.scoreBreakdown.finalScore })}
        ${renderMetricHtml({ label: "Оценка по правилам", value: report.scoreBreakdown.ruleScore })}
        ${renderMetricHtml({ label: "ML-калибровка", value: report.scoreBreakdown.mlScore })}
        ${renderMetricHtml({ label: "Статус", value: report.statusLabel })}
      </div>
      <p class="muted">${escapeHtml(report.scoreBreakdown.methodology)}</p>
      ${
        report.modelMetrics.length > 0
          ? `<h3>Статус модели</h3><div class="grid">${report.modelMetrics.map(renderMetricHtml).join("")}</div>`
          : ""
      }
    </section>
    <section>
      <h2>SEO-сигналы</h2>
      <div class="grid">${report.seoMetrics.map(renderMetricHtml).join("")}</div>
    </section>
    <section>
      <h2>Конкурентный контекст</h2>
      <div class="grid">${report.competitorMetrics.map(renderMetricHtml).join("")}</div>
      <table><thead><tr><th>Домен</th><th>Оценка</th><th>Статус</th><th>URL</th></tr></thead><tbody>${competitors}</tbody></table>
    </section>
    <section>
      <h2>План рекомендаций</h2>
      <div class="grid">${report.recommendationMetrics.map(renderMetricHtml).join("")}</div>
      <table class="recommendations"><thead><tr><th>Приоритет</th><th>Группа</th><th>Рекомендация</th><th>Что изменить</th></tr></thead><tbody>${recommendationRows}</tbody></table>
    </section>
    <section>
      <h2>Доказательство распределённого выполнения</h2>
      <div class="grid">${report.runtimeMetrics.map(renderMetricHtml).join("")}</div>
      <table><thead><tr><th>Этап</th><th>Завершено</th><th>Ошибок</th><th>Длительность</th><th>Критический путь</th></tr></thead><tbody>${stages}</tbody></table>
    </section>
  </main>
  ${options.autoPrint ? "<script>window.addEventListener('load', () => setTimeout(() => window.print(), 250));</script>" : ""}
</body>
</html>`;
}
