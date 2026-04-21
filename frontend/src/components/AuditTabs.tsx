import type { AuditTab } from "../types";

type AuditTabsProps = {
  activeTab: AuditTab;
  onChange: (tab: AuditTab) => void;
};

const tabs: Array<{ id: AuditTab; label: string }> = [
  { id: "overview", label: "Обзор" },
  { id: "pages", label: "Страницы" },
  { id: "competitors", label: "Конкуренты" },
  { id: "recommendations", label: "Рекомендации" },
];

export function AuditTabs({ activeTab, onChange }: AuditTabsProps) {
  return (
    <div className="audit-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={tab.id === activeTab ? "audit-tabs__item audit-tabs__item--active" : "audit-tabs__item"}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
