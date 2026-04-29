import { useMemo } from "react";
import { Card } from "../components/Card";
import {
  buildAuditTimelineModel,
  type TimelineEventRow,
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
        {stage.isCriticalPath ? <span className="timeline-badge">Critical path</span> : null}
      </div>
      <p>{stage.description}</p>
      <dl className="timeline-stage-card__metrics">
        <div>
          <dt>Queue</dt>
          <dd>{stage.queueLabel}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{stage.durationLabel}</dd>
        </div>
        <div>
          <dt>Events</dt>
          <dd>{stage.eventCount}</dd>
        </div>
        <div>
          <dt>Latest</dt>
          <dd>{stage.latestEventLabel}</dd>
        </div>
      </dl>
    </article>
  );
}

function FanOutCard({ fanOut }: { fanOut: ReturnType<typeof buildAuditTimelineModel>["fanOut"] }) {
  return (
    <Card
      title="Fan-out"
      subtitle="Показывает, где pipeline разветвлялся на параллельные задачи и как это влияет на critical path."
    >
      {fanOut ? (
        <div className="timeline-fanout">
          <div className="timeline-fanout__summary">
            <span className="eyebrow-pill">{fanOut.stageLabel}</span>
            <strong>{fanOut.branchCount} branches</strong>
            <p>{fanOut.note}</p>
          </div>
          <div className="metric-strip timeline-fanout__metrics">
            <div className="metric-box">
              <span className="metric-box__label">Dispatched</span>
              <strong className="metric-box__value">{fanOut.dispatchCount}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Terminal</span>
              <strong className="metric-box__value">{fanOut.terminalCount}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">In flight</span>
              <strong className="metric-box__value">{fanOut.inFlightCount}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Max branch</span>
              <strong className="metric-box__value">{fanOut.maxDurationLabel}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Average branch</span>
              <strong className="metric-box__value">{fanOut.averageDurationLabel}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Critical contribution</span>
              <strong className="metric-box__value">{fanOut.criticalPathDurationLabel}</strong>
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          Fan-out в этом запуске не найден или диагностика ещё не успела получить competitor branch events.
        </div>
      )}
    </Card>
  );
}

function StageDiagnosticsTable({ stages }: { stages: TimelineStageRow[] }) {
  return (
    <Card
      title="Stage diagnostics"
      subtitle="Агрегированные счётчики по каждому логическому этапу audit pipeline."
    >
      <div className="report-table-shell">
        <table className="report-table timeline-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Status</th>
              <th>Queue</th>
              <th>Started / terminal</th>
              <th>Completed / failed</th>
              <th>Duration</th>
              <th>Critical path</th>
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
                  <span className="timeline-table__muted">max {stage.maxDurationLabel}</span>
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
      title="Event stream"
      subtitle="Raw events из backend event log: очередь, worker stage, terminal durations и полезные details."
    >
      {events.length > 0 ? (
        <div className="report-table-shell timeline-event-stream">
          <table className="report-table timeline-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Stage</th>
                <th>Event</th>
                <th>Duration</th>
                <th>Queue</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.timestampLabel}</td>
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
          Raw event stream пока недоступен. Stage diagnostics выше остаются источником aggregate runtime evidence.
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
            <span className="eyebrow-pill">Таймлайн выполнения аудита</span>
            <h2 className="timeline-hero__title">{model.title}</h2>
            <p className="timeline-hero__text">
              Visual trace of the distributed Celery pipeline: queues, worker stages, fan-out branches, warnings,
              failures and the critical path that determined runtime.
            </p>
            <div className="workspace-meta">
              <span className="workspace-meta__item">Status: {model.statusLabel}</span>
              <span className="workspace-meta__item">Processing: {model.processingVersionLabel}</span>
              <span className="workspace-meta__item">Events: {model.rangeLabel}</span>
              <span className="workspace-meta__item">{model.targetUrl}</span>
            </div>
          </div>
        </div>
      </Card>

      {loading && isInFlight ? (
        <div className="feedback-banner feedback-banner--info">
          Timeline обновляется автоматически, пока аудит находится в очереди или обработке.
        </div>
      ) : null}
      {error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {model.failure ? (
        <div className="feedback-banner feedback-banner--error">
          <strong>Pipeline failed at {model.failure.stageLabel}</strong>
          <div>{model.failure.message}</div>
          {model.failure.code ? <div>Code: {model.failure.code}</div> : null}
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
          title="Timeline diagnostics пока недоступны"
          subtitle="Для старых аудитов event log может отсутствовать, а для новых queued runs события появятся после первого worker stage."
        >
          <div className="empty-state">
            Откройте аудит после завершения или дождитесь первого события pipeline, чтобы увидеть stage lifecycle,
            очереди, fan-out и critical path.
          </div>
        </Card>
      ) : (
        <>
          <Card
            title="Stage lifecycle"
            subtitle="Ordered view of the distributed audit execution stages. Critical path badge marks stages that contributed to total runtime."
          >
            <div className="timeline-stage-grid">
              {model.stageRows.map((stage, index) => (
                <TimelineStageCard key={stage.stage} stage={stage} index={index} />
              ))}
            </div>
          </Card>

          <FanOutCard fanOut={model.fanOut} />
          <StageDiagnosticsTable stages={model.stageRows} />
          <EventStreamTable events={model.eventRows} />
        </>
      )}
    </div>
  );
}
