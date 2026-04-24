import { Card } from "../components/Card";
import { RecommendationList } from "../components/RecommendationList";
import { getAuditStatusLabel, getFailureDetailEntries, getFailureStageLabel } from "../lib/ui";
import type { AuditStatus, FailureContext, RecommendationsBundle } from "../types";

type RecommendationsPageProps = {
  recommendations: RecommendationsBundle | null;
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  failureContext: FailureContext | null;
};

function formatScoreGap(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

export function RecommendationsPage({
  recommendations,
  auditStatus,
  loading,
  error,
  failureContext,
}: RecommendationsPageProps) {
  const detailEntries = failureContext ? getFailureDetailEntries(failureContext) : [];
  const summary = recommendations?.summary ?? null;

  return (
    <Card
      title="Рекомендации"
      subtitle="Секции по техническим, semantic, commercial и competitor-gap факторам с объяснением причин просадки."
    >
      <div className="metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Статус</span>
          <strong className="metric-box__value">{getAuditStatusLabel(auditStatus)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Рекомендаций</span>
          <strong className="metric-box__value">{summary?.total_recommendations ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Проблемных групп</span>
          <strong className="metric-box__value">{summary?.groups_with_issues ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Gap vs конкуренты</span>
          <strong className="metric-box__value">{formatScoreGap(summary?.score_gap_vs_competitors ?? null)}</strong>
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
      {!loading && !error && !recommendations && !(auditStatus === "failed" && failureContext) ? (
        <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
      ) : null}
      {!loading && !error && recommendations ? <RecommendationList recommendations={recommendations} /> : null}
    </Card>
  );
}
