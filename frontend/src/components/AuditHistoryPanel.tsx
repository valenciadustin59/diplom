import { useEffect, useState } from "react";
import {
  buildAuditHistoryModel,
  defaultAuditHistoryFilters,
  type AuditHistoryFilters,
  type AuditHistoryFocusFilter,
} from "../lib/auditHistory";
import type { AuditStatus, AuditSummary } from "../types";
import { Card } from "./Card";
import { RecentAuditList } from "./RecentAuditList";
import { ScoreRing } from "./ScoreRing";

const HIDDEN_AUDITS_STORAGE_KEY = "site-audit.hiddenAuditIds.v1";

const statusFilterOptions: Array<{ value: "all" | AuditStatus; label: string }> = [
  { value: "all", label: "Все статусы" },
  { value: "queued", label: "Запускается" },
  { value: "processing", label: "Обработка" },
  { value: "completed", label: "Завершён" },
  { value: "completed_with_warnings", label: "С предупреждениями" },
  { value: "failed", label: "Ошибка" },
];

const focusFilterOptions: Array<{ value: AuditHistoryFocusFilter; label: string }> = [
  { value: "all", label: "Все записи" },
  { value: "successful", label: "Успешные" },
  { value: "problematic", label: "Проблемные" },
  { value: "stale", label: "Зависшие/устаревшие" },
  { value: "hidden", label: "Скрытые локально" },
];

type AuditHistoryPanelProps = {
  recentAudits: AuditSummary[];
  activeAuditId?: string | null;
  loadingRecent: boolean;
  recentError: string | null;
  submitting: boolean;
  submissionError: string | null;
  success: string | null;
  onRefreshRecent: () => void;
  onOpenRuntime: () => void;
  onSelectAudit: (auditId: string) => void;
  onRepeatAudit: (audit: AuditSummary) => Promise<void>;
};

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function normalizeHiddenAuditIds(value: string[]): string[] {
  return [...new Set(value.map((item) => item.trim()).filter(Boolean))];
}

function readHiddenAuditIds(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const rawValue = window.localStorage.getItem(HIDDEN_AUDITS_STORAGE_KEY);
    if (!rawValue) {
      return [];
    }
    const parsedValue: unknown = JSON.parse(rawValue);
    return isStringArray(parsedValue) ? normalizeHiddenAuditIds(parsedValue) : [];
  } catch {
    return [];
  }
}

function writeHiddenAuditIds(hiddenAuditIds: string[]): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(HIDDEN_AUDITS_STORAGE_KEY, JSON.stringify(normalizeHiddenAuditIds(hiddenAuditIds)));
  } catch {
    // localStorage can be unavailable in restricted browser modes; hiding remains in-memory for the session.
  }
}

function createEmptyMessage(model: ReturnType<typeof buildAuditHistoryModel>, totalAudits: number): string {
  if (totalAudits === 0) {
    return "Пока нет аудитов. Запустите первый анализ через форму нового аудита.";
  }
  if (model.summary.hidden > 0 && model.rows.length === 0 && model.hasActiveFilters) {
    return "По текущим фильтрам ничего не найдено. Сбросьте фильтры или откройте скрытые локально записи.";
  }
  return "По текущим фильтрам ничего не найдено. Очистите фильтры, чтобы снова увидеть записи истории.";
}

function MetricBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-box">
      <span className="metric-box__label">{label}</span>
      <strong className="metric-box__value">{value}</strong>
    </div>
  );
}

export function AuditHistoryPanel({
  recentAudits,
  activeAuditId,
  loadingRecent,
  recentError,
  submitting,
  submissionError,
  success,
  onRefreshRecent,
  onOpenRuntime,
  onSelectAudit,
  onRepeatAudit,
}: AuditHistoryPanelProps) {
  const [filters, setFilters] = useState<AuditHistoryFilters>(defaultAuditHistoryFilters);
  const [hiddenAuditIds, setHiddenAuditIds] = useState<string[]>(readHiddenAuditIds);
  const model = buildAuditHistoryModel({
    audits: recentAudits,
    filters,
    hiddenAuditIds,
    now: Date.now(),
  });
  const heroScore = model.latestSuccessfulAudit?.score ?? model.rows[0]?.audit.score ?? 0;
  const hasRows = model.rows.length > 0;
  const latestSuccessfulLabel = model.latestSuccessfulAudit
    ? `Открыть ${model.latestSuccessfulAudit.domain}`
    : "Нет завершённых аудитов для быстрого открытия";

  useEffect(() => {
    writeHiddenAuditIds(hiddenAuditIds);
  }, [hiddenAuditIds]);

  function updateFilter<Key extends keyof AuditHistoryFilters>(key: Key, value: AuditHistoryFilters[Key]): void {
    setFilters((currentFilters) => ({ ...currentFilters, [key]: value }));
  }

  function resetFilters(): void {
    setFilters(defaultAuditHistoryFilters);
  }

  function hideAudit(auditId: string): void {
    setHiddenAuditIds((currentIds) => normalizeHiddenAuditIds([...currentIds, auditId]));
  }

  function restoreAudit(auditId: string): void {
    setHiddenAuditIds((currentIds) => currentIds.filter((currentId) => currentId !== auditId));
  }

  function repeatAudit(audit: AuditSummary): void {
    void onRepeatAudit(audit);
  }

  return (
    <div className="workspace-empty audit-history-panel">
      <Card className="hero-card workspace-empty__hero history-hero">
        <div className="hero-card__content">
          <div>
            <h2 className="hero-card__title">История аудитов</h2>
            <p className="hero-card__text">
              Здесь собраны запуски аудита. Можно открыть результат, повторить проверку или скрыть запись из локального списка.
            </p>
            <div className="history-hero__actions">
              <button
                className="primary-button"
                type="button"
                disabled={!model.latestSuccessfulAudit}
                title={latestSuccessfulLabel}
                onClick={() => (model.latestSuccessfulAudit ? onSelectAudit(model.latestSuccessfulAudit.id) : undefined)}
              >
                Открыть последний успешный
              </button>
              <button className="secondary-button" type="button" onClick={onRefreshRecent}>
                Обновить историю
              </button>
            </div>
          </div>
          <ScoreRing value={heroScore} label="История" />
        </div>
      </Card>

      <div className="metric-strip metric-strip--history">
        <MetricBox label="Всего" value={model.summary.total} />
        <MetricBox label="Актуальные" value={model.summary.visible} />
        <MetricBox label="Успешные" value={model.summary.successful} />
        <MetricBox label="Скрытые" value={model.summary.hidden} />
      </div>

      <Card title="Фильтры" subtitle="Найдите аудит по статусу, домену или запросу.">
        <div className="filters filters--history">
          <label className="filter-field filter-field--compact">
            <span>Статус</span>
            <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value as "all" | AuditStatus)}>
              {statusFilterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="filter-field filter-field--compact">
            <span>Домен</span>
            <input
              value={filters.domain}
              onChange={(event) => updateFilter("domain", event.target.value)}
              placeholder="seo-audit.ru"
            />
          </label>

          <label className="filter-field filter-field--compact">
            <span>Поиск</span>
            <input
              value={filters.search}
              onChange={(event) => updateFilter("search", event.target.value)}
              placeholder="запрос, домен или URL"
            />
          </label>

          <label className="filter-field filter-field--compact">
            <span>Фокус</span>
            <select value={filters.focus} onChange={(event) => updateFilter("focus", event.target.value as AuditHistoryFocusFilter)}>
              {focusFilterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <button className="secondary-button history-filter-reset" type="button" disabled={!model.hasActiveFilters} onClick={resetFilters}>
            Сбросить фильтры
          </button>
        </div>
      </Card>

      <Card title="Список аудитов" subtitle={`Показано записей: ${model.summary.filtered}`}>
        {recentError ? <div className="feedback-banner feedback-banner--error">{recentError}</div> : null}
        {submissionError ? <div className="feedback-banner feedback-banner--error">{submissionError}</div> : null}
        {success ? <div className="feedback-banner feedback-banner--success">{success}</div> : null}
        {loadingRecent && !hasRows ? (
          <div className="empty-state">Загружаем историю аудитов...</div>
        ) : !hasRows ? (
          <div className="empty-state">{createEmptyMessage(model, recentAudits.length)}</div>
        ) : (
          <RecentAuditList
            rows={model.rows}
            activeAuditId={activeAuditId}
            repeatDisabled={submitting}
            onSelect={onSelectAudit}
            onRepeat={repeatAudit}
            onHide={hideAudit}
            onRestore={restoreAudit}
          />
        )}
      </Card>

      <Card
        title="Состояние рабочего стека"
        subtitle="Если повторный аудит не запускается, проверьте API, Redis, SearXNG, Celery-воркеры и очереди."
        action={
          <button className="secondary-button" type="button" onClick={onOpenRuntime}>
            Открыть стек
          </button>
        }
      >
        <button className="secondary-button" type="button" onClick={onRefreshRecent}>
          Обновить историю
        </button>
      </Card>
    </div>
  );
}
