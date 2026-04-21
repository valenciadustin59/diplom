import type { AuditSummary } from "../types";
import { getAuditStatusLabel } from "../lib/ui";

type RecentAuditListProps = {
  items: AuditSummary[];
  activeAuditId?: string | null;
  onSelect?: (auditId: string) => void;
};

export function RecentAuditList({ items, activeAuditId, onSelect }: RecentAuditListProps) {
  if (items.length === 0) {
    return <div className="empty-state">Пока нет аудитов. Запустите первый анализ через форму нового аудита.</div>;
  }

  return (
    <div className="recent-list">
      {items.map((audit) => (
        <button
          key={audit.id}
          type="button"
          className={
            audit.id === activeAuditId
              ? "recent-list__item recent-list__item--active"
              : "recent-list__item"
          }
          onClick={() => onSelect?.(audit.id)}
        >
          <div>
            <div className="recent-list__title">{audit.domain}</div>
            <div className="recent-list__sub">{audit.query}</div>
            <div className="recent-list__time">{audit.createdAt}</div>
          </div>
          <div className="recent-list__meta">
            <span className={`status-pill status-pill--${audit.status}`}>
              {getAuditStatusLabel(audit.status)}
            </span>
            <span className="recent-list__score">{audit.score}</span>
          </div>
        </button>
      ))}
    </div>
  );
}
