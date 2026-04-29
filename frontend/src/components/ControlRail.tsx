type ControlRailProps = {
  activeView: "new" | "history" | "runtime";
  onOpenNew: () => void;
  onOpenHistory: () => void;
  onOpenRuntime: () => void;
};

export function ControlRail({ activeView, onOpenNew, onOpenHistory, onOpenRuntime }: ControlRailProps) {
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
          <button
            type="button"
            className={`control-rail__switcher-button ${activeView === "runtime" ? "control-rail__switcher-button--active" : ""}`}
            onClick={onOpenRuntime}
          >
            Runtime
          </button>
        </div>
      </div>
    </aside>
  );
}
