import type { AuditHistoryRow } from "../lib/auditHistory";
import type { AuditSummary } from "../types";
import { getEarlyStopMismatchView } from "../lib/earlyStop";
import { getAuditStatusLabel } from "../lib/ui";

type RecentAuditListProps = {
  rows: AuditHistoryRow[];
  activeAuditId?: string | null;
  repeatDisabled?: boolean;
  onSelect?: (auditId: string) => void;
  onRepeat?: (audit: AuditSummary) => void;
  onHide?: (auditId: string) => void;
  onRestore?: (auditId: string) => void;
};

function getRowClassName(row: AuditHistoryRow, activeAuditId?: string | null): string {
  return [
    "recent-list__item",
    row.audit.id === activeAuditId ? "recent-list__item--active" : null,
    row.isHidden ? "recent-list__item--hidden" : null,
  ].filter(Boolean).join(" ");
}

function getRowFlags(row: AuditHistoryRow): string[] {
  const flags: string[] = [];
  if (getEarlyStopMismatchView(row.audit.scoreBreakdown)) {
    flags.push("Страница не соответствует запросу");
  }
  if (row.isStale) {
    flags.push("Зависший/устаревший");
  } else if (row.isProblematic) {
    flags.push("Проблемный");
  }
  if (row.isHidden) {
    flags.push("Скрыт локально");
  }
  return flags;
}

export function RecentAuditList({
  rows,
  activeAuditId,
  repeatDisabled = false,
  onSelect,
  onRepeat,
  onHide,
  onRestore,
}: RecentAuditListProps) {
  if (rows.length === 0) {
    return <div className="empty-state">Пока нет аудитов. Запустите первый анализ через форму нового аудита.</div>;
  }

  return (
    <div className="recent-list">
      {rows.map((row) => {
        const audit = row.audit;
        const flags = getRowFlags(row);
        const earlyStopView = getEarlyStopMismatchView(audit.scoreBreakdown);

        return (
          <article key={audit.id} className={getRowClassName(row, activeAuditId)}>
            <div className="recent-list__content">
              <div className="recent-list__title">{audit.domain}</div>
              <div className="recent-list__sub">{audit.query}</div>
              {earlyStopView ? <div className="recent-list__notice">{earlyStopView.message}</div> : null}
              <div className="recent-list__time">{audit.createdAt}</div>
              {flags.length > 0 ? (
                <div className="recent-list__flags">
                  {flags.map((flag) => (
                    <span key={flag} className="history-row-flag">{flag}</span>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="recent-list__side">
              <div className="recent-list__meta">
                <span className={`status-pill status-pill--${audit.status}`}>
                  {getAuditStatusLabel(audit.status)}
                </span>
                <span className="recent-list__score">{audit.score}</span>
              </div>
              <div className="recent-list__actions">
                {onSelect ? (
                  <button className="secondary-button secondary-button--compact" type="button" onClick={() => onSelect(audit.id)}>
                    Открыть
                  </button>
                ) : null}
                {onRepeat ? (
                  <button
                    className="secondary-button secondary-button--compact"
                    type="button"
                    disabled={repeatDisabled}
                    onClick={() => onRepeat(audit)}
                  >
                    Повторить аудит
                  </button>
                ) : null}
                {row.isHidden && onRestore ? (
                  <button className="secondary-button secondary-button--compact" type="button" onClick={() => onRestore(audit.id)}>
                    Восстановить
                  </button>
                ) : null}
                {!row.isHidden && onHide ? (
                  <button className="secondary-button secondary-button--compact" type="button" onClick={() => onHide(audit.id)}>
                    Скрыть локально
                  </button>
                ) : null}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
