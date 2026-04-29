import { useMemo, useState } from "react";
import { AuditTable } from "../components/AuditTable";
import { Card } from "../components/Card";
import { getAuditStatusLabel } from "../lib/ui";
import type { AuditStatus, PageRow } from "../types";

type AuditPageProps = {
  rows: PageRow[];
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
};

export function AuditPage({ rows, auditStatus, loading, error }: AuditPageProps) {
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("0");

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const matchesSearch =
        row.url.toLowerCase().includes(search.toLowerCase()) ||
        row.seoTitle.toLowerCase().includes(search.toLowerCase()) ||
        row.pageType.toLowerCase().includes(search.toLowerCase()) ||
        row.fetchNote.toLowerCase().includes(search.toLowerCase());

      const matchesScore = row.score >= Number(minScore);
      return matchesSearch && matchesScore;
    });
  }, [minScore, rows, search]);

  return (
    <Card title="Страницы аудита" subtitle="Просматривайте оценку страниц, текстовые сигналы, SEO-метрики и статус обработки.">
      <div className="metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Статус</span>
          <strong className="metric-box__value">{getAuditStatusLabel(auditStatus)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Страниц</span>
          <strong className="metric-box__value">{rows.length}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Отображено</span>
          <strong className="metric-box__value">{filteredRows.length}</strong>
        </div>
      </div>

      <div className="filters">
        <label className="filter-field">
          <span>Поиск</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по URL, заголовку, типу страницы или статусу загрузки"
          />
        </label>

        <label className="filter-field filter-field--compact">
          <span>Мин. оценка</span>
          <select value={minScore} onChange={(event) => setMinScore(event.target.value)}>
            <option value="0">Все</option>
            <option value="60">60+</option>
            <option value="70">70+</option>
            <option value="80">80+</option>
          </select>
        </label>
      </div>

      {loading ? <div className="empty-state">Загружаем результаты аудита...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {!loading && !error && filteredRows.length === 0 ? (
        <div className="empty-state">Пока нет данных по страницам. Запустите аудит или дождитесь завершения обработки.</div>
      ) : null}
      {!loading && !error && filteredRows.length > 0 ? <AuditTable rows={filteredRows} /> : null}
    </Card>
  );
}
