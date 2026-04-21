import { Card } from "../components/Card";
import { RecommendationList } from "../components/RecommendationList";
import { getAuditStatusLabel, getFailureDetailEntries, getFailureStageLabel } from "../lib/ui";
import type { AuditStatus, FailureContext, Recommendation } from "../types";

type RecommendationsPageProps = {
  items: Recommendation[];
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  failureContext: FailureContext | null;
};

export function RecommendationsPage({
  items,
  auditStatus,
  loading,
  error,
  failureContext,
}: RecommendationsPageProps) {
  const detailEntries = failureContext ? getFailureDetailEntries(failureContext) : [];

  return (
    <Card title="Рекомендации" subtitle="Приоритетные действия на основе score, отклонений и анализа страницы.">
      <div className="metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Статус</span>
          <strong className="metric-box__value">{getAuditStatusLabel(auditStatus)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Рекомендаций</span>
          <strong className="metric-box__value">{items.length}</strong>
        </div>
      </div>

      {loading ? <div className="empty-state">Загружаем рекомендации...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {!loading && !error && auditStatus === "failed" && failureContext ? (
        <div className="feedback-banner feedback-banner--error">
          <div>
            <strong>Рекомендации не сформированы из-за ошибки на этапе {getFailureStageLabel(failureContext.stage)}</strong>
          </div>
          <div>{failureContext.message}</div>
          {failureContext.code ? <div>Код: {failureContext.code}</div> : null}
          {detailEntries.map((entry) => (
            <div key={`${entry.label}:${entry.value}`}>
              {entry.label}: {entry.value}
            </div>
          ))}
        </div>
      ) : null}
      {!loading && !error && items.length === 0 && !(auditStatus === "failed" && failureContext) ? (
        <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
      ) : null}
      {!loading && !error && items.length > 0 ? <RecommendationList items={items} /> : null}
    </Card>
  );
}
