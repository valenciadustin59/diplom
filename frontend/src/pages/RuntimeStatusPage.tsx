import { Card } from "../components/Card";
import type {
  RuntimeHealthModel,
  RuntimeIssue,
  RuntimeModelStatusView,
  RuntimeTone,
} from "../lib/runtimeHealth";

type RuntimeStatusProps = {
  model: RuntimeHealthModel | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onOpenFull?: () => void;
};

function getToneClass(tone: RuntimeTone): string {
  return `runtime-tone runtime-tone--${tone}`;
}

function RefreshButton({ loading, onRefresh }: Pick<RuntimeStatusProps, "loading" | "onRefresh">) {
  return (
    <button className="secondary-button" type="button" disabled={loading} onClick={onRefresh}>
      {loading ? "Обновляем..." : "Обновить"}
    </button>
  );
}

function RuntimeLoadingState({ error }: { error: string | null }) {
  return (
    <>
      {error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      <div className="empty-state">Загружаем диагностику рабочего стека...</div>
    </>
  );
}

function RuntimeIssueList({ issues }: { issues: RuntimeIssue[] }) {
  return (
    <div className="runtime-issue-list">
      {issues.map((issue) => (
        <article key={issue.key} className={`runtime-issue runtime-issue--${issue.tone}`}>
          <strong>{issue.title}</strong>
          <p>{issue.detail}</p>
        </article>
      ))}
    </div>
  );
}

function RuntimeMetricGrid({ model }: { model: RuntimeHealthModel }) {
  return (
    <div className="report-metric-grid runtime-metric-grid">
      {model.metrics.map((metric) => (
        <div key={metric.label} className={`report-metric runtime-metric runtime-metric--${metric.tone}`}>
          <span className="report-metric__label">{metric.label}</span>
          <strong className="report-metric__value">{metric.value}</strong>
          <p className="report-metric__note">{metric.note}</p>
        </div>
      ))}
    </div>
  );
}

function RuntimeModelStatusCard({ modelStatus }: { modelStatus: RuntimeModelStatusView | null }) {
  if (!modelStatus) {
    return null;
  }

  return (
    <Card
      title="Что оценивает сервис"
      subtitle="Коротко о том, как читать итоговую оценку без внутренних технических деталей."
      className="runtime-model-card"
    >
      <div className={`runtime-model-status runtime-model-status--${modelStatus.tone}`}>
        <div className="runtime-model-status__summary">
          <span className={getToneClass(modelStatus.tone)}>
            {modelStatus.tone === "ok" ? "Расчёт оценки доступен" : modelStatus.statusLabel}
          </span>
          <h3>Оценка соответствия запросу</h3>
          <p>
            Сервис показывает, насколько выбранная страница отвечает введённому запросу и насколько убедительно выглядит
            рядом с найденными конкурентами. Высокая оценка невозможна, если страница не про то, что ищет пользователь.
          </p>
        </div>
      </div>

      {modelStatus.tone !== "ok" ? (
        <div className="feedback-banner feedback-banner--warning">
          Расчёт оценки требует внимания: {modelStatus.detail}
        </div>
      ) : null}

      <div className="runtime-model-principles">
        <article>
          <strong>1. Проверяет попадание в запрос</strong>
          <p>Страница должна раскрывать именно ту тему и намерение, которые пользователь ввёл в поиск.</p>
        </article>
        <article>
          <strong>2. Оценивает полноту ответа</strong>
          <p>Смотрит, достаточно ли информации, чтобы посетитель понял предложение и мог принять решение.</p>
        </article>
        <article>
          <strong>3. Сравнивает с конкурентами</strong>
          <p>Показывает, где страница сильнее или слабее сайтов, найденных по тому же запросу.</p>
        </article>
        <article>
          <strong>4. Подсказывает, что улучшить</strong>
          <p>Рекомендации выделяют действия, которые помогут странице стать понятнее, полезнее и конкурентнее.</p>
        </article>
      </div>
    </Card>
  );
}

function RuntimeCardActions({ loading, onRefresh, onOpenFull }: Pick<RuntimeStatusProps, "loading" | "onRefresh" | "onOpenFull">) {
  return (
    <div className="runtime-card-actions">
      {onOpenFull ? (
        <button className="secondary-button" type="button" onClick={onOpenFull}>
          Открыть стек
        </button>
      ) : null}
      <RefreshButton loading={loading} onRefresh={onRefresh} />
    </div>
  );
}

export function RuntimeStatusCompactCard({ model, loading, error, onRefresh, onOpenFull }: RuntimeStatusProps) {
  return (
    <Card
      title="Готовность рабочего стека"
      subtitle="Проверяет API, Redis, SearXNG, Celery-воркеры и очереди до запуска нового аудита."
      action={<RuntimeCardActions loading={loading} onRefresh={onRefresh} onOpenFull={onOpenFull} />}
      className="runtime-compact-card"
    >
      {!model ? (
        <RuntimeLoadingState error={error} />
      ) : (
        <div className="runtime-compact">
          {error ? <div className="feedback-banner feedback-banner--warning">{error}</div> : null}
          <div className={`runtime-status-hero runtime-status-hero--${model.statusTone}`}>
            <div>
              <span className={getToneClass(model.statusTone)}>{model.statusLabel}</span>
              <p>{model.statusDetail}</p>
            </div>
            <div className="runtime-status-hero__meta">
              <span>{model.workerCount} воркеров</span>
              <span>{model.queueDepthTotal} задач в очередях</span>
              <span>Проверено: {model.checkedAtLabel}</span>
            </div>
          </div>
          <RuntimeIssueList issues={model.issues.slice(0, 3)} />
        </div>
      )}
    </Card>
  );
}

function RuntimeComponentsCard({ model }: { model: RuntimeHealthModel }) {
  return (
    <Card title="Компоненты рабочего стека" subtitle="Готовность и диагностика обязательных компонентов распределённого стека.">
      <div className="runtime-component-grid">
        {model.components.map((component) => (
          <article key={component.id} className={`runtime-component runtime-component--${component.tone}`}>
            <div className="runtime-component__top">
              <strong>{component.label}</strong>
              <span className={getToneClass(component.tone)}>{component.statusLabel}</span>
            </div>
            <p>{component.detail}</p>
          </article>
        ))}
      </div>
    </Card>
  );
}

function RuntimeProfilesCard({ model }: { model: RuntimeHealthModel }) {
  return (
    <Card title="Профили воркеров" subtitle="Каноническая топология привязки очередей: каждый профиль обслуживает свой набор задач.">
      <div className="runtime-profile-grid">
        {model.workerProfiles.map((profile) => (
          <article key={profile.name} className={`runtime-profile runtime-profile--${profile.tone}`}>
            <div className="runtime-profile__top">
              <div>
                <span className="eyebrow-pill">{profile.name}</span>
                <h3>{profile.label}</h3>
              </div>
              <span className={getToneClass(profile.tone)}>{profile.statusLabel}</span>
            </div>
            <p>{profile.description}</p>
            <dl className="runtime-profile__metrics">
              <div>
                <dt>Воркеры</dt>
                <dd>{profile.workerCount}</dd>
              </div>
              <div>
                <dt>Рекомендованная параллельность</dt>
                <dd>{profile.recommendedConcurrencyLabel}</dd>
              </div>
              <div>
                <dt>Очереди</dt>
                <dd>{profile.queuesLabel}</dd>
              </div>
              <div>
                <dt>Активные процессы</dt>
                <dd>{profile.workersLabel}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </Card>
  );
}

function RuntimeQueuesCard({ model }: { model: RuntimeHealthModel }) {
  return (
    <Card title="Очереди Celery" subtitle="Нагрузка очередей, накопление задач, активные задачи и покрытие воркерами.">
      <div className="report-table-shell">
        <table className="report-table runtime-queue-table">
          <thead>
            <tr>
              <th>Очередь</th>
              <th>Профиль</th>
              <th>Статус</th>
              <th>Глубина</th>
              <th>Воркеры</th>
              <th>Задачи</th>
              <th>Причина</th>
            </tr>
          </thead>
          <tbody>
            {model.queues.map((queue) => (
              <tr key={queue.name}>
                <td>
                  <strong>{queue.name}</strong>
                </td>
                <td>{queue.profileLabel}</td>
                <td>
                  <span className={getToneClass(queue.tone)}>{queue.pressureLabel}</span>
                </td>
                <td>{queue.depth}</td>
                <td>
                  <strong>{queue.workerCount}</strong>
                  <span className="timeline-table__muted">{queue.workersLabel}</span>
                </td>
                <td>
                  <span>активные {queue.activeTasks}</span>
                  <span className="timeline-table__muted">
                    зарезервировано {queue.reservedTasks}, запланировано {queue.scheduledTasks}, свободно {queue.availableCapacity}
                  </span>
                </td>
                <td>{queue.reasonLabels.length > 0 ? queue.reasonLabels.join("; ") : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function RuntimeStatusPage({ model, loading, error, onRefresh }: RuntimeStatusProps) {
  return (
    <div className="runtime-dashboard">
      <Card className="runtime-hero">
        <div className="runtime-hero__content">
          <div>
            <span className="eyebrow-pill">Состояние стека</span>
            <h2 className="runtime-hero__title">Состояние распределённого стека</h2>
            <p className="runtime-hero__text">
              Панель показывает, готов ли сервер к новым аудитам: API, брокер Redis, SearXNG, профили воркеров,
              покрытие очередей, накопление задач и нагрузку очередей.
            </p>
            {model ? (
              <div className="workspace-meta">
                <span className="workspace-meta__item">Приложение: {model.appLabel}</span>
                <span className="workspace-meta__item">Окружение: {model.environmentLabel}</span>
                <span className="workspace-meta__item">Проверено: {model.checkedAtLabel}</span>
              </div>
            ) : null}
          </div>
          <RefreshButton loading={loading} onRefresh={onRefresh} />
        </div>
      </Card>

      {!model ? (
        <RuntimeLoadingState error={error} />
      ) : (
        <>
          {error ? <div className="feedback-banner feedback-banner--warning">{error}</div> : null}
          <RuntimeMetricGrid model={model} />
          <RuntimeModelStatusCard modelStatus={model.modelStatus} />
          <Card title="Что восстановить" subtitle="Понятный вывод по готовности, нагрузке очередей и рискам контроля допуска.">
            <RuntimeIssueList issues={model.issues} />
          </Card>
          <RuntimeComponentsCard model={model} />
          <RuntimeProfilesCard model={model} />
          <RuntimeQueuesCard model={model} />
        </>
      )}
    </div>
  );
}
