import { useEffect, useMemo, useState } from "react";
import { Card } from "../components/Card";
import { RecommendationList } from "../components/RecommendationList";
import {
  buildRecommendationActionModel,
  sanitizeRecommendationActionStateMap,
  type RecommendationActionModel,
  type RecommendationActionStateMap,
  type RecommendationActionStatus,
} from "../lib/recommendationActions";
import { getAuditStatusLabel, getFailureDetailEntries, getFailureStageLabel } from "../lib/ui";
import type { AuditStatus, FailureContext, RecommendationsBundle } from "../types";

const RECOMMENDATION_ACTION_STORAGE_PREFIX = "site-audit.recommendationActions.v1";

type RecommendationsPageProps = {
  auditId?: string | null;
  recommendations: RecommendationsBundle | null;
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  failureContext: FailureContext | null;
};

type RecommendationActionStore = {
  storageKey: string | null;
  actionStates: RecommendationActionStateMap;
};

function getRecommendationActionStorageKey(auditId?: string | null): string | null {
  return auditId ? `${RECOMMENDATION_ACTION_STORAGE_PREFIX}.${auditId}` : null;
}

function readRecommendationActionStateMap(storageKey: string | null): RecommendationActionStateMap {
  if (!storageKey || typeof window === "undefined") {
    return {};
  }

  try {
    const rawValue = window.localStorage.getItem(storageKey);
    return rawValue ? sanitizeRecommendationActionStateMap(JSON.parse(rawValue)) : {};
  } catch {
    return {};
  }
}

function writeRecommendationActionStateMap(storageKey: string | null, actionStates: RecommendationActionStateMap): void {
  if (!storageKey || typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(actionStates));
  } catch {
    // localStorage can be unavailable in restricted browser modes; tracking remains in-memory for the session.
  }
}

function removeActionState(
  actionStates: RecommendationActionStateMap,
  actionKey: string,
): RecommendationActionStateMap {
  return Object.fromEntries(Object.entries(actionStates).filter(([currentActionKey]) => currentActionKey !== actionKey));
}

function RecommendationActionProgress({ actionModel }: { actionModel: RecommendationActionModel }) {
  const { summary } = actionModel;

  return (
    <section className="recommendation-action-panel" aria-label="План действий по рекомендациям">
      <div className="recommendation-action-panel__heading">
        <h3>План действий</h3>
        <p>Отмечайте статус рекомендаций локально: прогресс сохраняется в браузере для этого аудита.</p>
      </div>

      <div className="metric-strip metric-strip--actions">
        <div className="metric-box">
          <span className="metric-box__label">Закрыто</span>
          <strong className="metric-box__value">{`${summary.closed}/${summary.total}`}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">В работе</span>
          <strong className="metric-box__value">{summary.inProgress}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Исправлено</span>
          <strong className="metric-box__value">{summary.fixed}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Игнорируется</span>
          <strong className="metric-box__value">{summary.ignored}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Прогресс</span>
          <strong className="metric-box__value">{summary.progressPercent}%</strong>
        </div>
      </div>
    </section>
  );
}

function formatScoreGap(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

export function RecommendationsPage({
  auditId,
  recommendations,
  auditStatus,
  loading,
  error,
  failureContext,
}: RecommendationsPageProps) {
  const detailEntries = failureContext ? getFailureDetailEntries(failureContext) : [];
  const summary = recommendations?.summary ?? null;
  const storageKey = getRecommendationActionStorageKey(auditId);
  const [actionStore, setActionStore] = useState<RecommendationActionStore>(() => ({
    storageKey,
    actionStates: readRecommendationActionStateMap(storageKey),
  }));
  const actionModel = useMemo(
    () => buildRecommendationActionModel(recommendations, actionStore.actionStates),
    [actionStore.actionStates, recommendations],
  );

  useEffect(() => {
    setActionStore({ storageKey, actionStates: readRecommendationActionStateMap(storageKey) });
  }, [storageKey]);

  useEffect(() => {
    if (actionStore.storageKey !== storageKey) {
      return;
    }

    writeRecommendationActionStateMap(storageKey, actionStore.actionStates);
  }, [actionStore, storageKey]);

  function handleActionStatusChange(actionKey: string, status: RecommendationActionStatus): void {
    setActionStore((currentStore) => {
      const currentStates = currentStore.storageKey === storageKey ? currentStore.actionStates : readRecommendationActionStateMap(storageKey);
      return {
        storageKey,
        actionStates: status === "not_started" ? removeActionState(currentStates, actionKey) : { ...currentStates, [actionKey]: status },
      };
    });
  }

  return (
    <Card
      title="Рекомендации"
      subtitle="Секции по техническим, смысловым, коммерческим и конкурентным факторам с объяснением причин просадки."
    >
      <div className="metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Статус</span>
          <strong className="metric-box__value">{getAuditStatusLabel(auditStatus)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Рекомендаций</span>
          <strong className="metric-box__value">{summary?.total_recommendations ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Проблемных групп</span>
          <strong className="metric-box__value">{summary?.groups_with_issues ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Разница с конкурентами</span>
          <strong className="metric-box__value">{formatScoreGap(summary?.score_gap_vs_competitors ?? null)}</strong>
        </div>
      </div>

      {loading ? <div className="empty-state">Загружаем рекомендации...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {!loading && !error && auditStatus === "failed" && failureContext ? (
        <div className="feedback-banner feedback-banner--error">
          <div>
            <strong>Рекомендации не сформированы из-за ошибки на этапе {getFailureStageLabel(failureContext.stage)}</strong>
          </div>
          <div>{failureContext.message}</div>
          {failureContext.code ? <div>Код: {failureContext.code}</div> : null}
          {detailEntries.map((entry) => (
            <div key={`${entry.label}:${entry.value}`}>
              {entry.label}: {entry.value}
            </div>
          ))}
        </div>
      ) : null}
      {!loading && !error && !recommendations && !(auditStatus === "failed" && failureContext) ? (
        <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
      ) : null}
      {!loading && !error && recommendations ? (
        <>
          <RecommendationActionProgress actionModel={actionModel} />
          <RecommendationList
            recommendations={recommendations}
            actionModel={actionModel}
            onActionStatusChange={handleActionStatusChange}
          />
        </>
      ) : null}
    </Card>
  );
}
