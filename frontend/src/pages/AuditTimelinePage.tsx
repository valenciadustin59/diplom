import { useMemo } from "react";
import { Card } from "../components/Card";
import {
  buildAuditTimelineModel,
  type TimelineEventRow,
  type TimelineFanOutModel,
  type TimelineMetric,
  type TimelineStageRow,
} from "../lib/auditTimeline";
import type {
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  FailureContext,
} from "../types";

type AuditTimelinePageProps = {
  currentAudit: AuditStatusResponse;
  currentResults: AuditResultsResponse | null;
  timelineDiagnostics: AuditTimelineDiagnosticsResponse | null;
  timelineEvents: AuditTimelineEventsResponse | null;
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  failureContext: FailureContext | null;
};

const statusPillTone: Record<TimelineStageRow["status"], AuditStatus> = {
  pending: "queued",
  dispatched: "queued",
  running: "processing",
  completed: "completed",
  failed: "failed",
  aborted: "failed",
};

function SummaryMetrics({ metrics }: { metrics: TimelineMetric[] }) {
  return (
    <div className="report-metric-grid timeline-metric-grid">
      {metrics.map((metric) => (
        <div key={metric.label} className="report-metric">
          <span className="report-metric__label">{metric.label}</span>
          <strong className="report-metric__value">{metric.value}</strong>
          {metric.note ? <p className="report-metric__note">{metric.note}</p> : null}
        </div>
      ))}
    </div>
  );
}

function TimelineStageCard({ stage, index }: { stage: TimelineStageRow; index: number }) {
  return (
    <article className={`timeline-stage-card timeline-stage-card--${stage.status}`}>
      <div className="timeline-stage-card__top">
        <span className="timeline-stage-card__index">{index + 1}</span>
        <span className={`status-pill status-pill--${statusPillTone[stage.status]}`}>{stage.statusLabel}</span>
      </div>
      <div className="timeline-stage-card__heading">
        <h3>{stage.label}</h3>
        {stage.isCriticalPath ? <span className="timeline-badge" title="Этап влияет на общее время выполнения аудита">Критический путь</span> : null}
      </div>
      <p>{stage.description}</p>
      <dl className="timeline-stage-card__metrics">
        <div>
          <dt>Очередь</dt>
          <dd>{stage.queueLabel}</dd>
        </div>
        <div>
          <dt>Длительность</dt>
          <dd>{stage.durationLabel}</dd>
        </div>
        <div>
          <dt>События</dt>
          <dd>{stage.eventCount}</dd>
        </div>
        <div>
          <dt>Последнее</dt>
          <dd>{stage.latestEventLabel}</dd>
        </div>
      </dl>
    </article>
  );
}

function FanOutCard({ fanOutStages }: { fanOutStages: TimelineFanOutModel[] }) {
  return (
    <Card
      title="Ветки обработки"
      subtitle="Показывает, какие задачи запускались параллельно и сколько времени заняли самые долгие ветки."
    >
      {fanOutStages.length > 0 ? (
        <div className="timeline-fanout">
          {fanOutStages.map((fanOut) => (
            <article key={fanOut.stage} className="timeline-fanout__stage">
              <div className="timeline-fanout__summary">
                <span className="eyebrow-pill">{fanOut.stageLabel}</span>
                <strong>{fanOut.branchCount} веток</strong>
                <p>{fanOut.note}</p>
              </div>
              <div className="metric-strip timeline-fanout__metrics">
                <div className="metric-box">
                  <span className="metric-box__label">Отправлено</span>
                  <strong className="metric-box__value">{fanOut.dispatchCount}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Завершено веток</span>
                  <strong className="metric-box__value">{fanOut.terminalCount}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">В работе</span>
                  <strong className="metric-box__value">{fanOut.inFlightCount}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Самая долгая ветка</span>
                  <strong className="metric-box__value">{fanOut.maxDurationLabel}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Средняя ветка</span>
                  <strong className="metric-box__value">{fanOut.averageDurationLabel}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Критический путь</span>
                  <strong className="metric-box__value">{fanOut.criticalPathDurationLabel}</strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          Параллельные ветки в этом запуске не найдены или диагностика ещё не успела получить события веток конкурентов.
        </div>
      )}
    </Card>
  );
}

function StageDiagnosticsTable({ stages }: { stages: TimelineStageRow[] }) {
  return (
    <Card
      title="Диагностика этапов"
      subtitle="Агрегированные счётчики по каждому логическому этапу конвейера аудита."
    >
      <div className="report-table-shell">
        <table className="report-table timeline-table timeline-diagnostics-table">
          <thead>
            <tr>
              <th>Этап</th>
              <th>Статус</th>
              <th>Очередь</th>
              <th>Запущено / завершено</th>
              <th>Успешно / ошибок</th>
              <th>Длительность</th>
              <th>Вклад во время выполнения</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((stage) => (
              <tr key={stage.stage}>
                <td>
                  <strong>{stage.label}</strong>
                  <span className="timeline-table__muted">{stage.stage}</span>
                </td>
                <td>
                  <span className={`status-pill status-pill--${statusPillTone[stage.status]}`}>{stage.statusLabel}</span>
                </td>
                <td>{stage.queueLabel}</td>
                <td>{stage.startedCount} / {stage.terminalCount}</td>
                <td>{stage.completedCount} / {stage.failedCount + stage.abortedCount}</td>
                <td>
                  <strong>{stage.durationLabel}</strong>
                  <span className="timeline-table__muted">макс. {stage.maxDurationLabel}</span>
                </td>
                <td>
                  <strong>{stage.criticalPathDurationLabel}</strong>
                  <span className="timeline-table__muted">{stage.criticalPathModeLabel}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function EventStreamTable({ events }: { events: TimelineEventRow[] }) {
  return (
    <Card
      title="Поток событий"
      subtitle="Сырые события из серверного журнала. Эта таблица показывает факты запуска и завершения, а параллельность удобнее смотреть выше в блоке веток обработки."
    >
      {events.length > 0 ? (
        <div className="report-table-shell timeline-event-stream">
          <table className="report-table timeline-table timeline-event-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Этап</th>
                <th>Событие</th>
                <th>Длительность</th>
                <th>Очередь</th>
                <th>Детали</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td className="timeline-event-table__time">{event.timestampLabel}</td>
                  <td>
                    <strong>{event.stageLabel}</strong>
                    <span className="timeline-table__muted">{event.stage}</span>
                  </td>
                  <td>
                    <span className={`timeline-event-tone timeline-event-tone--${event.tone}`}>{event.eventLabel}</span>
                  </td>
                  <td>{event.durationLabel}</td>
                  <td>{event.queueLabel}</td>
                  <td>{event.detailSummary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          Поток сырых событий пока недоступен. Диагностика этапов выше остаётся источником агрегированных данных о выполнении.
        </div>
      )}
    </Card>
  );
}

export function AuditTimelinePage({
  currentAudit,
  currentResults,
  timelineDiagnostics,
  timelineEvents,
  auditStatus,
  loading,
  error,
  failureContext,
}: AuditTimelinePageProps) {
  const model = useMemo(
    () =>
      buildAuditTimelineModel({
        audit: currentAudit,
        results: currentResults,
        diagnostics: timelineDiagnostics,
        events: timelineEvents,
        failureContext,
      }),
    [currentAudit, currentResults, failureContext, timelineDiagnostics, timelineEvents],
  );
  const isInFlight = auditStatus === "queued" || auditStatus === "processing";

  return (
    <div className="timeline-dashboard">
      <Card className="timeline-hero">
        <div className="timeline-hero__content">
          <div>
            <h2 className="timeline-hero__title">{model.title}</h2>
            <p className="timeline-hero__text">
              Здесь видно, какие этапы уже прошли, какие задачи выполнялись параллельно и где аудит потратил больше всего времени.
            </p>
            <div className="workspace-meta">
              <span className="workspace-meta__item">Статус: {model.statusLabel}</span>
              <span className="workspace-meta__item">Версия обработки: {model.processingVersionLabel}</span>
              <span className="workspace-meta__item">События: {model.rangeLabel}</span>
              <span className="workspace-meta__item">Целевая страница: {model.targetUrl}</span>
            </div>
          </div>
        </div>
      </Card>

      {loading && isInFlight ? (
        <div className="feedback-banner feedback-banner--info">
          Таймлайн обновляется автоматически, пока аудит находится в очереди или обработке.
        </div>
      ) : null}
      {error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {model.earlyStop ? (
        <div className="early-stop-state early-stop-state--compact">
          <div>
            <strong>{model.earlyStop.title}</strong>
            <p>{model.earlyStop.message}</p>
          </div>
          {model.earlyStop.score !== null ? <span>{Math.round(model.earlyStop.score)}</span> : null}
        </div>
      ) : null}
      {model.failure ? (
        <div className="feedback-banner feedback-banner--error">
          <strong>Конвейер остановился на этапе: {model.failure.stageLabel}</strong>
          <div>{model.failure.message}</div>
          {model.failure.code ? <div>Код: {model.failure.code}</div> : null}
          {model.failure.details.map((detail) => (
            <div key={`${detail.label}:${detail.value}`}>
              {detail.label}: {detail.value}
            </div>
          ))}
        </div>
      ) : null}
      {model.warnings.length > 0 ? (
        <div className="feedback-banner feedback-banner--warning">
          {model.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}

      <SummaryMetrics metrics={model.summaryMetrics} />

      {!model.hasData ? (
        <Card
          title="Диагностика таймлайна пока недоступна"
          subtitle="Для старых аудитов журнал событий может отсутствовать, а для новых запусков в очереди события появятся после первого этапа воркера."
        >
          <div className="empty-state">
            Откройте аудит после завершения или дождитесь первого события конвейера, чтобы увидеть жизненный цикл этапов,
            очереди, параллельные ветки и подсказки по вкладу в критический путь.
          </div>
        </Card>
      ) : (
        <>
          <Card
            title="Этапы обработки"
            subtitle="Показывает, как аудит проходил загрузку, анализ страницы, обработку конкурентов и финальный расчёт."
          >
            <div className="timeline-stage-grid">
              {model.stageRows.map((stage, index) => (
                <TimelineStageCard key={stage.stage} stage={stage} index={index} />
              ))}
            </div>
          </Card>

          <FanOutCard fanOutStages={model.fanOutStages} />
          <StageDiagnosticsTable stages={model.stageRows} />
          <EventStreamTable events={model.eventRows} />
        </>
      )}
    </div>
  );
}
