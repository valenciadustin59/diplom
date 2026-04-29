import { useMemo, useState } from "react";
import { Card } from "../components/Card";
import {
  buildAuditReportFilename,
  buildAuditReportModel,
  createAuditReportMarkdown,
  type AuditReportInput,
  type ReportMetric,
} from "../lib/auditReport";
import { createAuditReportHtml } from "../lib/auditReportHtml";
import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  FailureContext,
  RecommendationsBundle,
} from "../types";

type AuditReportPageProps = {
  currentAudit: AuditStatusResponse;
  currentResults: AuditResultsResponse | null;
  recommendations: RecommendationsBundle | null;
  timelineDiagnostics: AuditTimelineDiagnosticsResponse | null;
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  failureContext: FailureContext | null;
};

function downloadTextFile(fileName: string, contents: string, type: string): void {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function openHtmlDocument(html: string): boolean {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const openedWindow = window.open(url, "_blank");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return openedWindow !== null;
}

function MetricGrid({ items }: { items: ReportMetric[] }) {
  return (
    <div className="report-metric-grid">
      {items.map((item) => (
        <article key={item.label} className="report-metric">
          <span className="report-metric__label">{item.label}</span>
          <strong className="report-metric__value">{item.value}</strong>
          {item.note ? <p className="report-metric__note">{item.note}</p> : null}
        </article>
      ))}
    </div>
  );
}

export function AuditReportPage({
  currentAudit,
  currentResults,
  recommendations,
  timelineDiagnostics,
  auditStatus,
  loading,
  error,
  failureContext,
}: AuditReportPageProps) {
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const reportInput = useMemo<AuditReportInput>(
    () => ({
      audit: currentAudit,
      results: currentResults,
      recommendations,
      diagnostics: timelineDiagnostics,
    }),
    [currentAudit, currentResults, recommendations, timelineDiagnostics],
  );
  const report = useMemo(() => buildAuditReportModel(reportInput), [reportInput]);

  function handleDownloadMarkdown() {
    downloadTextFile(
      buildAuditReportFilename(currentAudit, "md"),
      createAuditReportMarkdown(reportInput),
      "text/markdown;charset=utf-8",
    );
    setExportMessage("Markdown-отчёт скачан.");
  }

  function handleDownloadHtml() {
    downloadTextFile(
      buildAuditReportFilename(currentAudit, "html"),
      createAuditReportHtml(reportInput),
      "text/html;charset=utf-8",
    );
    setExportMessage("HTML-отчёт скачан.");
  }

  function handleOpenPrintable() {
    const opened = openHtmlDocument(createAuditReportHtml(reportInput, { autoPrint: true }));
    setExportMessage(
      opened
        ? "Печатная версия открыта в новой вкладке. В диалоге печати можно выбрать Save as PDF."
        : "Браузер заблокировал новую вкладку. Используйте скачивание HTML или разрешите pop-up для localhost.",
    );
  }

  return (
    <div className="report-dashboard">
      <Card className="report-hero">
        <div className="report-hero__content">
          <div>
            <span className="eyebrow-pill">Отчёт аудита</span>
            <h2 className="report-hero__title">{report.domain}</h2>
            <p className="report-hero__text">
              Единый export dashboard для демонстрации SEO/ML-результата, competitor evidence, рекомендаций и распределённого
              runtime.
            </p>
            <div className="workspace-meta">
              <span className="workspace-meta__item">Запрос: {report.query}</span>
              <span className="workspace-meta__item">Статус: {report.statusLabel}</span>
              <span className="workspace-meta__item">Создан: {report.createdAt}</span>
            </div>
          </div>
          <div className="report-score">
            <span className="report-score__label">Score</span>
            <strong className="report-score__value">{report.scoreLabel}</strong>
          </div>
        </div>

        <div className="report-actions" aria-label="Экспорт отчёта">
          <button type="button" className="primary-button" onClick={handleOpenPrintable}>
            Открыть печатную версию
          </button>
          <button type="button" className="secondary-button" onClick={handleDownloadHtml}>
            Скачать HTML
          </button>
          <button type="button" className="secondary-button" onClick={handleDownloadMarkdown}>
            Скачать Markdown
          </button>
        </div>

        {exportMessage ? <div className="feedback-banner feedback-banner--success">{exportMessage}</div> : null}
      </Card>

      {loading ? <div className="feedback-banner feedback-banner--info">Обновляем данные отчёта...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {auditStatus === "failed" && failureContext ? (
        <div className="feedback-banner feedback-banner--warning">
          Отчёт частичный: аудит остановился на этапе {failureContext.stage}. Причина: {failureContext.message}
        </div>
      ) : null}

      <Card title="Executive summary" subtitle="Короткий вывод, который можно показать без расшифровки внутренних полей.">
        <div className="report-summary-list">
          {report.summary.map((item) => (
            <div key={item} className="report-summary-list__item">
              {item}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Score and ML explanation" subtitle="Отчёт разделяет rule-based SEO-сигналы и ML-калибровку итоговой оценки.">
        <MetricGrid
          items={[
            { label: "Final score", value: report.scoreBreakdown.finalScore },
            { label: "Rule-based score", value: report.scoreBreakdown.ruleScore },
            { label: "ML score", value: report.scoreBreakdown.mlScore },
            { label: "Status", value: report.statusLabel },
          ]}
        />
        <p className="report-section-note">{report.scoreBreakdown.methodology}</p>
      </Card>

      <Card title="SEO evidence" subtitle="Сигналы из feature schema v2, target snapshot и isolated heavy-analysis stage.">
        <MetricGrid items={report.seoMetrics} />
      </Card>

      <Card title="Competitor evidence" subtitle="SERP-relative контекст: сколько конкурентов найдено, обработано и каков score gap.">
        <MetricGrid items={report.competitorMetrics} />
        <div className="report-table-shell">
          <table className="report-table">
            <thead>
              <tr>
                <th>Домен</th>
                <th>Score</th>
                <th>Статус</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {report.competitors.length > 0 ? (
                report.competitors.map((competitor) => (
                  <tr key={competitor.url}>
                    <td>{competitor.domain}</td>
                    <td>{competitor.score}</td>
                    <td>{competitor.status}</td>
                    <td>{competitor.url}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4}>Конкурентные страницы пока не обработаны.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Recommendation plan" subtitle="Полный action backlog: все рекомендации, отсортированные по приоритету.">
        <MetricGrid items={report.recommendationMetrics} />
        <div className="report-group-list">
          {report.groupSummaries.map((group) => (
            <article key={group.label} className="report-group-card">
              <strong>{group.label}</strong>
              <span>{group.value}</span>
              {group.note ? <p>{group.note}</p> : null}
            </article>
          ))}
        </div>
        <div className="report-table-shell report-table-shell--recommendations">
          <table className="report-table report-table--recommendations">
            <thead>
              <tr>
                <th>Приоритет</th>
                <th>Группа</th>
                <th>Рекомендация</th>
                <th>Что изменить</th>
              </tr>
            </thead>
            <tbody>
              {report.recommendationActions.length > 0 ? (
                report.recommendationActions.map((item) => (
                  <tr key={item.code}>
                    <td>{item.priorityLabel}</td>
                    <td>{item.groupLabel}</td>
                    <td>
                      <strong className="report-action-title">{item.title}</strong>
                      <small className="report-action-code">{item.code}</small>
                    </td>
                    <td>
                      <p className="report-action-detail">{item.message}</p>
                      <small className="report-action-outcome">{item.expectedOutcome}</small>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4}>Рекомендации появятся после завершения обработки аудита.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="Distributed runtime evidence"
        subtitle="Timeline diagnostics показывает, что аудит выполнялся как stage-based Celery pipeline, а не как один монолитный запрос."
      >
        <MetricGrid items={report.runtimeMetrics} />
        <div className="report-table-shell">
          <table className="report-table">
            <thead>
              <tr>
                <th>Stage</th>
                <th>Completed</th>
                <th>Failed</th>
                <th>Duration</th>
                <th>Critical path</th>
              </tr>
            </thead>
            <tbody>
              {report.stageRows.length > 0 ? (
                report.stageRows.map((stage) => (
                  <tr key={stage.stage}>
                    <td>{stage.stage}</td>
                    <td>{stage.completed}</td>
                    <td>{stage.failed}</td>
                    <td>{stage.duration}</td>
                    <td>{stage.criticalPath}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>Timeline diagnostics пока недоступны.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
