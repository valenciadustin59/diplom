import { PriorityBadge } from "./PriorityBadge";
import {
  getRecommendationActionKey,
  recommendationActionStatusOptions,
  type RecommendationActionModel,
  type RecommendationActionStatus,
} from "../lib/recommendationActions";
import {
  getHumanReadableLabel,
  getRecommendationGroupDescription,
  getRecommendationGroupEmptyState,
  getRecommendationGroupLabel,
} from "../lib/terminology";
import type {
  RecommendationDeviation,
  RecommendationGroup,
  RecommendationGroupStatus,
  RecommendationsBundle,
} from "../types";
import type { RecommendationPreviewItem } from "../lib/recommendations";

type RecommendationListProps = {
  recommendations: RecommendationsBundle;
  actionModel: RecommendationActionModel;
  onActionStatusChange: (actionKey: string, status: RecommendationActionStatus) => void;
};

type RecommendationPreviewListProps = {
  items: RecommendationPreviewItem[];
};

type RecommendationActionControlProps = {
  actionKey: string;
  status: RecommendationActionStatus;
  statusLabel: string;
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

function getPlainRecommendationAction(item: RecommendationPreviewItem | RecommendationGroup["items"][number]): string {
  const code = item.code.toUpperCase();
  const text = `${item.title} ${item.message}`.toLowerCase();

  if (code.includes("TITLE")) {
    return "Перепишите title так, чтобы в нём ясно были тема страницы и важные слова из запроса. Не набивайте фразами, сделайте заголовок понятным для человека.";
  }
  if (code.includes("DESCRIPTION") || code.includes("SNIPPET")) {
    return "Добавьте короткое meta description: что предлагает страница, кому она подходит и почему по ней стоит перейти из выдачи.";
  }
  if (code.includes("CANONICAL")) {
    return "Поставьте canonical на основную версию страницы, чтобы поисковик не делил сигналы между дублями URL.";
  }
  if (code.includes("INDEX") || code.includes("ROBOTS")) {
    return "Проверьте robots, noindex и HTTP-статус: страница должна быть доступна поисковику и разрешена к индексации.";
  }
  if (code.includes("HEADING") || code.includes("H1")) {
    return "Сделайте главный заголовок и подзаголовки ближе к реальной теме запроса: пользователь должен сразу понять, что попал на нужную страницу.";
  }
  if (code.includes("QUERY") || code.includes("INTENT") || code.includes("SEMANTIC") || text.includes("запрос")) {
    return "Усилите ответ именно на введённый запрос: добавьте недостающие уточнения, примеры, условия, характеристики или разделы, которые ожидает пользователь.";
  }
  if (code.includes("COMMERCIAL") || code.includes("CONTACT") || code.includes("CTA") || code.includes("TRUST")) {
    return "Сделайте путь к действию очевидным: контакты, форма заявки, условия работы, доверительные данные и следующий шаг должны быть видны без поиска по сайту.";
  }
  if (code.includes("TEXT") || code.includes("CONTENT")) {
    return "Раскройте тему глубже: добавьте конкретику по услуге или товару, ответы на частые вопросы и детали, которых не хватает по сравнению с конкурентами.";
  }
  if (code.includes("URL") || code.includes("REDIRECT")) {
    return "Упростите технический путь страницы: чистый URL, минимум лишних параметров и редиректов, корректный финальный адрес.";
  }
  if (code.includes("COMPETITOR") || text.includes("конкурент")) {
    return "Посмотрите, в чём лидеры выдачи раскрывают запрос сильнее, и добавьте на страницу именно эти недостающие элементы.";
  }

  return "Исправьте указанный пункт на самой проверяемой странице и после правки повторите аудит, чтобы увидеть изменение score.";
}

function renderDeviation(deviation: RecommendationDeviation) {
  return (
    <article
      key={deviation.code}
      className={`recommendation-deviation recommendation-deviation--${deviation.trend}`}
    >
      <div className="recommendation-deviation__top">
        <strong>{getHumanReadableLabel(deviation.label)}</strong>
        <PriorityBadge priority={deviation.priority} />
      </div>
      <div className="recommendation-deviation__values">
        <span>Страница: {formatDeviationValue(deviation.current_value, deviation.unit)}</span>
        <span>
          {getHumanReadableLabel(deviation.benchmark_label)}: {formatDeviationValue(deviation.benchmark_value, deviation.unit)}
        </span>
      </div>
      <p className="recommendation-deviation__summary">{deviation.summary}</p>
    </article>
  );
}

function renderRecommendationActionControl(
  actionControl: RecommendationActionControlProps,
  onActionStatusChange: RecommendationListProps["onActionStatusChange"],
) {
  return (
    <div className="recommendation-item__tracking">
      <span className={`recommendation-action-status recommendation-action-status--${actionControl.status}`}>
        {actionControl.statusLabel}
      </span>
      <label className="recommendation-action-control">
        <span>Статус действия</span>
        <select
          value={actionControl.status}
          onChange={(event) => onActionStatusChange(actionControl.actionKey, event.target.value as RecommendationActionStatus)}
        >
          {recommendationActionStatusOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function renderRecommendationCard(
  item: RecommendationPreviewItem | RecommendationGroup["items"][number],
  compact = false,
  actionControl: RecommendationActionControlProps | null = null,
  onActionStatusChange?: RecommendationListProps["onActionStatusChange"],
) {
  const className = [
    "recommendation-item",
    `recommendation-item--${item.priority}`,
    compact ? "recommendation-item--compact" : "",
    actionControl ? `recommendation-item--status-${actionControl.status}` : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article key={item.code} className={className}>
      <div className="recommendation-item__top">
        <div className="recommendation-item__heading">
          {"groupLabel" in item ? <span className="recommendation-item__group">{item.groupLabel}</span> : null}
          <strong className="recommendation-item__title">{item.title}</strong>
          <span className="recommendation-item__code">Код: {item.code}</span>
        </div>
        <div className="recommendation-item__badges">
          <PriorityBadge priority={item.priority} />
          <span className={`recommendation-impact recommendation-impact--${item.impact}`}>
            Эффект: {getImpactLabel(item.impact)}
          </span>
        </div>
      </div>
      <p className="recommendation-item__message">{item.message}</p>
      {!compact ? (
        <div className="recommendation-item__plain-action">
          <span>Что сделать</span>
          <p>{getPlainRecommendationAction(item)}</p>
        </div>
      ) : null}
      {!compact ? <p className="recommendation-item__outcome">{item.expected_outcome}</p> : null}
      {!compact && actionControl && onActionStatusChange ? renderRecommendationActionControl(actionControl, onActionStatusChange) : null}
      {!compact && item.evidence.length > 0 ? (
        <div className="recommendation-evidence-list">
          {item.evidence.map((evidence) => (
            <div key={`${item.code}:${evidence.label}`} className="recommendation-evidence">
              <span className="recommendation-evidence__label">{getHumanReadableLabel(evidence.label)}</span>
              <span className="recommendation-evidence__value">{evidence.value}</span>
              {evidence.benchmark ? (
                <span className="recommendation-evidence__benchmark">
                  {getHumanReadableLabel(evidence.benchmark_label)}: {evidence.benchmark}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function RecommendationGroupSection({
  group,
  defaultOpen,
  actionModel,
  onActionStatusChange,
}: {
  group: RecommendationGroup;
  defaultOpen: boolean;
  actionModel: RecommendationActionModel;
  onActionStatusChange: RecommendationListProps["onActionStatusChange"];
}) {
  const groupActionSummary = actionModel.groupSummariesByKey[group.key];
  const groupLabel = getRecommendationGroupLabel(group.key);
  const showMetricComparison = false;

  return (
    <details className={`recommendation-group recommendation-group--${group.status}`} open={defaultOpen}>
      <summary className="recommendation-group__header">
        <div className="recommendation-group__heading">
          <h3 className="recommendation-group__title">{groupLabel}</h3>
          <p className="recommendation-group__description">{getRecommendationGroupDescription(group)}</p>
        </div>
        <div className="recommendation-group__status-stack">
          <span className={`recommendation-group__status recommendation-group__status--${group.status}`}>
            {getGroupStatusLabel(group.status)}
          </span>
          {groupActionSummary && groupActionSummary.total > 0 ? (
            <span className="recommendation-action-summary">
              Закрыто {groupActionSummary.closed}/{groupActionSummary.total}
            </span>
          ) : null}
        </div>
      </summary>

      <div className="recommendation-group__body">
        {showMetricComparison && group.deviations.length > 0 ? (
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
              {groupActionSummary && groupActionSummary.total > 0 ? (
                <span className="recommendation-subsection__progress">Прогресс: {groupActionSummary.progressPercent}%</span>
              ) : null}
            </div>
            <div className="recommendation-group__items">
              {group.items.map((item) => {
                const actionKey = getRecommendationActionKey(group.key, item.code);
                const itemState = actionModel.itemStatesByKey[actionKey];

                return renderRecommendationCard(item, false, itemState ?? null, onActionStatusChange);
              })}
            </div>
          </section>
        ) : (
          <div className="empty-state recommendation-group__empty">{getRecommendationGroupEmptyState(group)}</div>
        )}
      </div>
    </details>
  );
}

export function RecommendationList({ recommendations, actionModel, onActionStatusChange }: RecommendationListProps) {
  const visibleGroups = recommendations.groups.filter((group) => group.items.length > 0);
  const firstIssueIndex = visibleGroups.findIndex((group) => group.items.length > 0);

  if (visibleGroups.length === 0) {
    return (
      <div className="recommendation-list">
        <div className="empty-state">
          Явных задач для улучшения не найдено. Если хотите усилить страницу, ориентируйтесь на обзор score и сравнение с конкурентами.
        </div>
      </div>
    );
  }

  return (
    <div className="recommendation-list">
      {visibleGroups.map((group, index) => (
        <RecommendationGroupSection
          key={group.key}
          group={group}
          defaultOpen={index === firstIssueIndex}
          actionModel={actionModel}
          onActionStatusChange={onActionStatusChange}
        />
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
