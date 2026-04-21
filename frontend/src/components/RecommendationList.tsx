import { PriorityBadge } from "./PriorityBadge";
import type { Recommendation } from "../types";

type RecommendationListProps = {
  items: Recommendation[];
};

export function RecommendationList({ items }: RecommendationListProps) {
  const groupedItems = {
    high: items.filter((item) => item.priority === "high"),
    medium: items.filter((item) => item.priority === "medium"),
    low: items.filter((item) => item.priority === "low"),
  };

  const sections: Array<{ key: "high" | "medium" | "low"; title: string }> = [
    { key: "high", title: "Высокий приоритет" },
    { key: "medium", title: "Средний приоритет" },
    { key: "low", title: "Низкий приоритет" },
  ];

  return (
    <div className="recommendation-list">
      {sections.map((section) =>
        groupedItems[section.key].length > 0 ? (
          <div key={section.key} className="recommendation-group">
            <h3 className="recommendation-group__title">{section.title}</h3>
            <div className="recommendation-group__items">
              {groupedItems[section.key].map((item) => (
                <article key={item.code} className="recommendation-item">
                  <div className="recommendation-item__top">
                    <span className="recommendation-item__code">{item.code}</span>
                    <PriorityBadge priority={item.priority} />
                  </div>
                  <p className="recommendation-item__message">{item.message}</p>
                </article>
              ))}
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}
