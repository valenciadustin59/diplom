import { PriorityBadge } from "./PriorityBadge";
import type {
  RecommendationDeviation,
  RecommendationGroup,
  RecommendationGroupStatus,
  RecommendationsBundle,
} from "../types";
import type { RecommendationPreviewItem } from "../lib/recommendations";

type RecommendationListProps = {
  recommendations: RecommendationsBundle;
};

type RecommendationPreviewListProps = {
  items: RecommendationPreviewItem[];
};

function getImpactLabel(priority: "high" | "medium" | "low"): string {
  if (priority === "high") {
    return "сильный";
  }
  if (priority === "medium") {
    return "заметный";
  }
  return "точечный";
}

function formatDeviationValue(value: number, unit: string): string {
  if (unit === "binary") {
    return value >= 0.5 ? "Да" : "Нет";
  }
  if (unit === "chars") {
    return `${Math.round(value)} симв.`;
  }
  if (unit === "count") {
    return String(Math.round(value));
  }
  if (unit === "percentile") {
    return `${Math.round(value * 100)} перцентиль`;
  }
  return value.toFixed(2);
}

function getGroupStatusLabel(status: RecommendationGroupStatus): string {
  switch (status) {
    case "critical":
      return "Критично";
    case "attention":
      return "Требует внимания";
    case "monitor":
      return "Есть точки роста";
    case "competitive":
      return "Конкурентно";
    case "not_enough_data":
      return "Недостаточно данных";
    default:
      return status;
  }
}

function renderDeviation(deviation: RecommendationDeviation) {
  return (
    <article
      key={deviation.code}
      className={`recommendation-deviation recommendation-deviation--${deviation.trend}`}
    >
      <div className="recommendation-deviation__top">
        <strong>{deviation.label}</strong>
        <PriorityBadge priority={deviation.priority} />
      </div>
      <div className="recommendation-deviation__values">
        <span>Страница: {formatDeviationValue(deviation.current_value, deviation.unit)}</span>
        <span>
          {deviation.benchmark_label}: {formatDeviationValue(deviation.benchmark_value, deviation.unit)}
        </span>
      </div>
      <p className="recommendation-deviation__summary">{deviation.summary}</p>
    </article>
  );
}

function renderRecommendationCard(item: RecommendationPreviewItem | RecommendationGroup["items"][number], compact = false) {
  const className = [
    "recommendation-item",
    `recommendation-item--${item.priority}`,
    compact ? "recommendation-item--compact" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article key={item.code} className={className}>
      <div className="recommendation-item__top">
        <div className="recommendation-item__heading">
          {"groupLabel" in item ? <span className="recommendation-item__group">{item.groupLabel}</span> : null}
          <strong className="recommendation-item__title">{item.title}</strong>
          <span className="recommendation-item__code">{item.code}</span>
        </div>
        <div className="recommendation-item__badges">
          <PriorityBadge priority={item.priority} />
          <span className={`recommendation-impact recommendation-impact--${item.impact}`}>
            Эффект: {getImpactLabel(item.impact)}
          </span>
        </div>
      </div>
      <p className="recommendation-item__message">{item.message}</p>
      {!compact ? <p className="recommendation-item__outcome">{item.expected_outcome}</p> : null}
      {!compact && item.evidence.length > 0 ? (
        <div className="recommendation-evidence-list">
          {item.evidence.map((evidence) => (
            <div key={`${item.code}:${evidence.label}`} className="recommendation-evidence">
              <span className="recommendation-evidence__label">{evidence.label}</span>
              <span className="recommendation-evidence__value">{evidence.value}</span>
              {evidence.benchmark ? (
                <span className="recommendation-evidence__benchmark">
                  {evidence.benchmark_label}: {evidence.benchmark}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function RecommendationGroupSection({ group, defaultOpen }: { group: RecommendationGroup; defaultOpen: boolean }) {
  return (
    <details className={`recommendation-group recommendation-group--${group.status}`} open={defaultOpen}>
      <summary className="recommendation-group__header">
        <div className="recommendation-group__heading">
          <h3 className="recommendation-group__title">{group.label}</h3>
          <p className="recommendation-group__description">{group.description}</p>
        </div>
        <span className={`recommendation-group__status recommendation-group__status--${group.status}`}>
          {getGroupStatusLabel(group.status)}
        </span>
      </summary>

      <div className="recommendation-group__body">
        {group.deviations.length > 0 ? (
          <section className="recommendation-subsection recommendation-subsection--metrics" aria-label="Сравнение с конкурентами">
            <div className="recommendation-subsection__header">
              <span className="recommendation-subsection__kicker">Сравнение</span>
              <span className="recommendation-subsection__count">{group.deviations.length}</span>
            </div>
            <div className="recommendation-deviation-list">{group.deviations.map(renderDeviation)}</div>
          </section>
        ) : null}

        {group.items.length > 0 ? (
          <section className="recommendation-subsection recommendation-subsection--actions" aria-label="Рекомендации к улучшению">
            <div className="recommendation-subsection__header">
              <span className="recommendation-subsection__kicker">Что улучшить</span>
              <span className="recommendation-subsection__count">{group.items.length}</span>
            </div>
            <div className="recommendation-group__items">{group.items.map((item) => renderRecommendationCard(item))}</div>
          </section>
        ) : (
          <div className="empty-state recommendation-group__empty">{group.empty_state}</div>
        )}
      </div>
    </details>
  );
}

export function RecommendationList({ recommendations }: RecommendationListProps) {
  const firstIssueIndex = recommendations.groups.findIndex(
    (group) => group.items.length > 0 || group.deviations.length > 0,
  );

  return (
    <div className="recommendation-list">
      {recommendations.groups.map((group, index) => (
        <RecommendationGroupSection key={group.key} group={group} defaultOpen={index === firstIssueIndex} />
      ))}
    </div>
  );
}

export function RecommendationPreviewList({ items }: RecommendationPreviewListProps) {
  return (
    <div className="recommendation-preview-list">
      {items.map((item) => renderRecommendationCard(item, true))}
    </div>
  );
}
