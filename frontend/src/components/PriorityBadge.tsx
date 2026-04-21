type Priority = "high" | "medium" | "low";

type PriorityBadgeProps = {
  priority: Priority;
};

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const labels: Record<Priority, string> = {
    high: "Высокий",
    medium: "Средний",
    low: "Низкий",
  };

  return <span className={`priority-badge priority-badge--${priority}`}>{labels[priority]}</span>;
}
