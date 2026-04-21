type ControlRailProps = {
  activeView: "new" | "history";
  onOpenNew: () => void;
  onOpenHistory: () => void;
};

export function ControlRail({ activeView, onOpenNew, onOpenHistory }: ControlRailProps) {
  return (
    <aside className="control-rail">
      <div className="control-rail__section control-rail__section--brand">
        <div className="control-rail__brand">
          <div className="control-rail__logo">SA</div>
          <div>
            <p className="control-rail__eyebrow">Анализ сайтов</p>
            <h1 className="control-rail__title">Audit Cloud</h1>
          </div>
        </div>
        <p className="control-rail__text">
          Слева только навигация. Создание нового аудита и просмотр истории открываются в центральной рабочей области.
        </p>

        <div className="control-rail__switcher" role="tablist" aria-label="Навигация по приложению">
          <button
            type="button"
            className={`control-rail__switcher-button ${activeView === "new" ? "control-rail__switcher-button--active" : ""}`}
            onClick={onOpenNew}
          >
            Новый аудит
          </button>
          <button
            type="button"
            className={`control-rail__switcher-button ${activeView === "history" ? "control-rail__switcher-button--active" : ""}`}
            onClick={onOpenHistory}
          >
            История
          </button>
        </div>
      </div>
    </aside>
  );
}
