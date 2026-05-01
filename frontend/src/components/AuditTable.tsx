import type { PageRow } from "../types";

type AuditTableProps = {
  rows: PageRow[];
};

export function AuditTable({ rows }: AuditTableProps) {
  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            <th>Страница</th>
            <th>Тип</th>
            <th>Загрузка</th>
            <th>Оценка</th>
            <th>Текст</th>
            <th>SEO-заголовок</th>
            <th>Совпадение запроса</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="data-table__url">
                <div className="data-table__url-value" title={row.url}>
                  {row.url}
                </div>
                <div className="data-table__note">{row.fetchNote}</div>
              </td>
              <td>{row.pageType}</td>
              <td>
                <span className={`status-pill status-pill--fetch-${row.fetchStatus}`}>
                  {row.fetchStatus === "success" ? "OK" : "Не удалось"}
                </span>
              </td>
              <td>{row.score}</td>
              <td>{row.textLength}</td>
              <td>{row.seoTitle}</td>
              <td>{Math.round(row.queryMatch * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
