import { Card } from "../components/Card";
import type { RuntimeHealthModel, RuntimeIssue, RuntimeTone } from "../lib/runtimeHealth";

type RuntimeStatusProps = {
  model: RuntimeHealthModel | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
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
      <div className="empty-state">Загружаем runtime diagnostics...</div>
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

export function RuntimeStatusCompactCard({ model, loading, error, onRefresh }: RuntimeStatusProps) {
  return (
    <Card
      title="Готовность runtime"
      subtitle="Проверяет API, Redis, SearXNG, Celery workers и очереди до запуска нового аудита."
      action={<RefreshButton loading={loading} onRefresh={onRefresh} />}
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
    <Card title="Компоненты runtime" subtitle="Readiness и telemetry обязательных компонентов distributed stack.">
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
    <Card title="Профили воркеров" subtitle="Каноническая queue-affinity topology: каждый профиль обслуживает свой набор очередей.">
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
                <dt>Рекоменд. concurrency</dt>
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
    <Card title="Очереди Celery" subtitle="Queue pressure, backlog, активные задачи и покрытие воркерами.">
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
                  <span>active {queue.activeTasks}</span>
                  <span className="timeline-table__muted">
                    reserved {queue.reservedTasks}, scheduled {queue.scheduledTasks}, capacity {queue.availableCapacity}
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
            <span className="eyebrow-pill">Runtime status</span>
            <h2 className="runtime-hero__title">Состояние distributed stack</h2>
            <p className="runtime-hero__text">
              Панель показывает, готов ли backend к новым аудитам: API, Redis broker, SearXNG, профили воркеров,
              покрытие очередей, backlog и queue pressure.
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
          <Card title="Что восстановить" subtitle="Human-readable вывод по readiness, queue pressure и admission-control рискам.">
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
