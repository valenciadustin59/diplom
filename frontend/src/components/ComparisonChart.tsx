import type { CompetitorScore } from "../types";

type ComparisonChartProps = {
  items: CompetitorScore[];
};

export function ComparisonChart({ items }: ComparisonChartProps) {
  const maxScore = Math.max(...items.map((item) => item.score), 100);

  return (
    <div className="comparison-chart">
      {items.map((item) => (
        <div key={item.name} className="comparison-chart__row">
          <div className="comparison-chart__meta">
            <span
              className={
                item.isUser
                  ? "comparison-chart__name comparison-chart__name--user"
                  : "comparison-chart__name"
              }
            >
              {item.name}
            </span>
            <span className="comparison-chart__value">{item.score}</span>
          </div>
          <div className="comparison-chart__bar">
            <div
              className={item.isUser ? "comparison-chart__fill comparison-chart__fill--user" : "comparison-chart__fill"}
              style={{ width: `${(item.score / maxScore) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
