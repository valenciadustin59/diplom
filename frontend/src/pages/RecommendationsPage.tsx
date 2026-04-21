import { Card } from "../components/Card";
import { RecommendationList } from "../components/RecommendationList";
import { getAuditStatusLabel } from "../lib/ui";
import type { AuditStatus, Recommendation } from "../types";

type RecommendationsPageProps = {
  items: Recommendation[];
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
};

export function RecommendationsPage({
  items,
  auditStatus,
  loading,
  error,
}: RecommendationsPageProps) {
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
      {!loading && !error && items.length === 0 ? (
        <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
      ) : null}
      {!loading && !error && items.length > 0 ? <RecommendationList items={items} /> : null}
    </Card>
  );
}
