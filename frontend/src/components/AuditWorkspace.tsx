import { AuditPage } from "../pages/AuditPage";
import { AuditReportPage } from "../pages/AuditReportPage";
import { AuditTimelinePage } from "../pages/AuditTimelinePage";
import { RecommendationsPage } from "../pages/RecommendationsPage";
import { RuntimeStatusCompactCard } from "../pages/RuntimeStatusPage";
import { getTopRecommendationItems } from "../lib/recommendations";
import type { RuntimeHealthModel } from "../lib/runtimeHealth";
import { getAuditStatusLabel, getFailureDetailEntries, getFailureStageLabel, resolveAuditFailureContext } from "../lib/ui";
import { getFetchMethodLabel, getHumanReadableLabel } from "../lib/terminology";
import { AuditTabs } from "./AuditTabs";
import { AuditLaunchForm } from "./AuditLaunchForm";
import { Card } from "./Card";
import { AuditHistoryPanel } from "./AuditHistoryPanel";
import { ComparisonChart } from "./ComparisonChart";
import { RecommendationPreviewList } from "./RecommendationList";
import { ScoreRing } from "./ScoreRing";
import type {
  AuditCreatePayload,
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditSummary,
  AuditTab,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  ComparisonSummary,
  CompetitorScore,
  FailureContext,
  PageRow,
  RecommendationsBundle,
  ScoreBreakdown,
  ScoreFactor,
} from "../types";

type AuditWorkspaceProps = {
  currentAudit: AuditStatusResponse | null;
  currentResults: AuditResultsResponse | null;
  recommendations: RecommendationsBundle | null;
  timelineDiagnostics: AuditTimelineDiagnosticsResponse | null;
  timelineEvents: AuditTimelineEventsResponse | null;
  pageRows: PageRow[];
  competitorScores: CompetitorScore[];
  comparisonSummary: ComparisonSummary | null;
  auditStatus: AuditStatus;
  loading: boolean;
  error: string | null;
  activeTab: AuditTab;
  onTabChange: (tab: AuditTab) => void;
};

type EmptyWorkspaceProps = {
  mode: "new" | "history";
  recentAudits: AuditSummary[];
  activeAuditId?: string | null;
  loadingRecent: boolean;
  recentError: string | null;
  submitting: boolean;
  submissionError: string | null;
  success: string | null;
  runtimeHealth: RuntimeHealthModel | null;
  loadingRuntime: boolean;
  runtimeError: string | null;
  onRefreshRuntime: () => void;
  onOpenRuntime: () => void;
  onRefreshRecent: () => void;
  onCreateAudit: (payload: AuditCreatePayload) => Promise<boolean>;
  onSelectAudit: (auditId: string) => void;
  onRepeatAudit: (audit: AuditSummary) => Promise<void>;
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatImpact(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function getScoreFactorId(item: ScoreFactor, index: number): string {
  return item.code ?? item.key ?? `${item.label}:${index}`;
}

function formatScoreFactorDetail(item: ScoreFactor): string {
  if (item.detail) {
    return item.detail;
  }

  if (item.value !== undefined && item.value !== null) {
    return `Значение фактора: ${item.value}`;
  }

  return "Фактор участвует в объяснении итоговой оценки.";
}

function formatScoreWeight(value: number | undefined): string | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return `${Math.round(value * 100)}%`;
}

function getScoreMethodologyText(breakdown: ScoreBreakdown): string {
  const ruleWeight = formatScoreWeight(breakdown.weights?.rule_weight);
  const mlWeight = formatScoreWeight(breakdown.weights?.ml_weight);

  if (ruleWeight && mlWeight) {
    return `Итоговая оценка рассчитывается как гибрид объяснимых SEO- и смысловых сигналов с ML-калибровкой: ${ruleWeight} веса дают правила, ${mlWeight} — модель. Ниже показаны метрики, которые сильнее всего подняли или снизили результат.`;
  }

  return "Итоговая оценка рассчитывается по набору объяснимых SEO, смысловых, технических, коммерческих и доверительных сигналов с ML-калибровкой. Ниже показаны факторы, которые сильнее всего повлияли на результат.";
}

const interactionSignalLabels: Record<string, string> = {
  query_semantic_alignment: "Смысловое соответствие + покрытие запроса",
  title_semantic_alignment: "Title + смысловое соответствие",
  heading_semantic_alignment: "Заголовки + смысловое соответствие",
  query_prominence_score: "Выраженность запроса",
  keyword_balance_score: "Баланс ключевых слов",
  semantic_content_richness: "Глубина и смысловая полнота контента",
  cta_semantic_score: "Призыв к действию + коммерческое намерение",
};

function ScoreFactorList({
  title,
  items = [],
  tone,
}: {
  title: string;
  items?: ScoreFactor[];
  tone: "positive" | "negative";
}) {
  return (
    <div className="score-factor-group">
      <h4 className="score-factor-group__title">{title}</h4>
      {items.length > 0 ? (
        <div className="score-factor-list">
          {items.map((item, index) => (
            <article key={getScoreFactorId(item, index)} className={`score-factor score-factor--${tone}`}>
              <div className="score-factor__top">
                <strong>{getHumanReadableLabel(item.label)}</strong>
                <span className={`score-factor__impact score-factor__impact--${tone}`}>{formatImpact(item.impact)}</span>
              </div>
              <p className="score-factor__detail">{formatScoreFactorDetail(item)}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">После завершения аудита здесь появятся объяснимые факторы оценки.</div>
      )}
    </div>
  );
}

function ScoreBreakdownCard({ breakdown }: { breakdown: ScoreBreakdown | null | undefined }) {
  if (!breakdown) {
    return (
      <Card
        title="Как формируется оценка"
        subtitle="После завершения аудита здесь появится объяснение итоговой оценки, её сильных сторон и просадок."
      >
        <div className="empty-state">Дождитесь завершения анализа, чтобы увидеть расшифровку итоговой оценки.</div>
      </Card>
    );
  }

  const positiveFactors = breakdown.positives ?? breakdown.top_positive_factors ?? [];
  const negativeFactors = breakdown.negatives ?? breakdown.top_negative_factors ?? [];
  const methodology = getScoreMethodologyText(breakdown);

  return (
    <Card
      title="Как формируется оценка"
      subtitle="Итог складывается из объяснимых SEO- и смысловых сигналов и отдельной ML-калибровки."
    >
      <div className="score-breakdown">
        <p className="score-breakdown__methodology">{methodology}</p>

        <div className="metric-strip metric-strip--comparison">
          <div className="metric-box">
            <span className="metric-box__label">Итоговая оценка</span>
            <strong className="metric-box__value">{breakdown.final_score}</strong>
          </div>
          <div className="metric-box">
            <span className="metric-box__label">Оценка по правилам</span>
            <strong className="metric-box__value">{breakdown.rule_score}</strong>
          </div>
          <div className="metric-box">
            <span className="metric-box__label">ML-калибровка</span>
            <strong className="metric-box__value">{breakdown.ml_score}</strong>
          </div>
        </div>

        {breakdown.interaction_signals ? (
          <div className="metric-strip metric-strip--comparison">
            {Object.entries(breakdown.interaction_signals).map(([key, value]) => (
              <div key={key} className="metric-box">
                <span className="metric-box__label">{interactionSignalLabels[key] ?? key}</span>
                <strong className="metric-box__value">{value.toFixed(2)}</strong>
              </div>
            ))}
          </div>
        ) : null}

        <div className="score-breakdown__grid">
          <ScoreFactorList title="Что помогает странице" items={positiveFactors} tone="positive" />
          <ScoreFactorList title="Что тянет оценку вниз" items={negativeFactors} tone="negative" />
        </div>
      </div>
    </Card>
  );
}

function FailureContextBanner({
  context,
  title,
}: {
  context: FailureContext;
  title?: string;
}) {
  const detailEntries = getFailureDetailEntries(context);

  return (
    <div className="feedback-banner feedback-banner--error">
      <div>
        <strong>{title ?? `Ошибка на этапе ${getFailureStageLabel(context.stage)}`}</strong>
      </div>
      <div>{context.message}</div>
      {context.code ? <div>Код: {context.code}</div> : null}
      {detailEntries.map((entry) => (
        <div key={`${entry.label}:${entry.value}`}>
          {entry.label}: {entry.value}
        </div>
      ))}
    </div>
  );
}

function AuditWarnings({
  currentAudit,
  currentResults,
  failureContext,
}: Pick<AuditWorkspaceProps, "currentAudit" | "currentResults"> & {
  failureContext: FailureContext | null;
}) {
  const warnings = currentResults?.warnings ?? currentAudit?.warnings ?? [];

  return (
    <>
      {currentAudit?.status === "completed_with_warnings" && warnings.length > 0 ? (
        <div className="feedback-banner feedback-banner--warning">
          {warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}

      {currentAudit?.status === "failed" && failureContext ? (
        <FailureContextBanner
          context={failureContext}
          title={`Аудит остановился на этапе ${getFailureStageLabel(failureContext.stage)}`}
        />
      ) : null}
    </>
  );
}

function AuditProgressBanner({ status }: { status: AuditStatus }) {
  if (status !== "queued" && status !== "processing") {
    return null;
  }

  const title = status === "queued" ? "Аудит запускается" : "Аудит обрабатывается";
  const message =
    status === "queued"
      ? "Подготавливаем этапы анализа. Обычно первый статус меняется через несколько секунд."
      : "Система загружает страницу, собирает конкурентов и пересчитывает итоговую оценку. Данные обновляются автоматически.";

  return (
    <div className="feedback-banner feedback-banner--info">
      <strong>{title}</strong>
      <div>{message}</div>
    </div>
  );
}

function OverviewPanel({
  currentAudit,
  currentResults,
  recommendations,
  competitorScores,
  comparisonSummary,
}: Pick<
  AuditWorkspaceProps,
  "currentAudit" | "currentResults" | "recommendations" | "competitorScores" | "comparisonSummary"
>) {
  const topRecommendationItems = getTopRecommendationItems(recommendations, 3);
  const foundCount = comparisonSummary?.competitors_found ?? comparisonSummary?.competitors_count ?? 0;
  const analyzedCount = comparisonSummary?.competitors_analyzed ?? comparisonSummary?.competitors_count ?? 0;
  const failedCount = comparisonSummary?.competitors_failed ?? Math.max(0, foundCount - analyzedCount);

  return (
    <div className="workspace-grid">
      <Card className="workspace-hero">
        <div className="workspace-hero__content">
          <div>
            <span className="eyebrow-pill">Обзор аудита</span>
            <h2 className="workspace-hero__title">{currentAudit ? getDomain(currentAudit.target_url) : "Аудит"}</h2>
            <p className="workspace-hero__text">
              {currentAudit?.query ?? "Запустите аудит, чтобы увидеть метрики, сравнение и рекомендации."}
            </p>

            {currentAudit ? (
              <div className="workspace-meta">
                <span className="workspace-meta__item">Статус: {getAuditStatusLabel(currentAudit.status as AuditStatus)}</span>
                <span className="workspace-meta__item">Запущен: {formatDate(currentAudit.created_at)}</span>
                <span className="workspace-meta__item">Загрузка: {getFetchMethodLabel(currentResults?.target_fetch_method ?? currentAudit.target_fetch_method)}</span>
              </div>
            ) : null}
          </div>

          <ScoreRing value={Math.round(comparisonSummary?.user_score ?? currentAudit?.score ?? 0)} />
        </div>
      </Card>

      <div className="metric-strip workspace-metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Оценка страницы</span>
          <strong className="metric-box__value">{comparisonSummary?.user_score ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Средняя оценка конкурентов</span>
          <strong className="metric-box__value">{comparisonSummary?.competitors_average_score ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Разница</span>
          <strong className="metric-box__value">{comparisonSummary?.score_difference ?? 0}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Конкуренты</span>
          <strong className="metric-box__value">{`${analyzedCount}/${foundCount}`}</strong>
        </div>
      </div>

      <Card
        title="Сравнение с конкурентами"
        subtitle="График строится только по реально обработанным страницам из поисковой выдачи."
      >
        {competitorScores.length > 0 ? (
          <>
            <ComparisonChart items={competitorScores} />
            {failedCount > 0 ? (
              <div className="feedback-banner feedback-banner--warning">
                Обработано {analyzedCount} из {foundCount} конкурентных страниц, {failedCount} страниц ограничили автоматический доступ.
              </div>
            ) : null}
          </>
        ) : (
          <div className="empty-state">Конкурентные страницы ещё не собраны или не удалось обработать ни одну страницу.</div>
        )}
      </Card>

      <ScoreBreakdownCard breakdown={currentResults?.score_breakdown} />

      <Card
        title="Ключевые рекомендации"
        subtitle="Первые действия, которые сильнее всего влияют на качество страницы."
      >
        {topRecommendationItems.length > 0 ? (
          <RecommendationPreviewList items={topRecommendationItems} />
        ) : (
          <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
        )}
      </Card>
    </div>
  );
}

function CompetitorsPanel({
  currentResults,
  competitorScores,
  comparisonSummary,
  loading,
  error,
  failureContext,
}: Pick<
  AuditWorkspaceProps,
  "currentResults" | "competitorScores" | "comparisonSummary" | "loading" | "error"
> & {
  failureContext: FailureContext | null;
}) {
  const competitors = currentResults?.competitor_results ?? [];
  const foundCount = comparisonSummary?.competitors_found ?? comparisonSummary?.competitors_count ?? 0;
  const analyzedCount = comparisonSummary?.competitors_analyzed ?? comparisonSummary?.competitors_count ?? 0;
  const failedCount = comparisonSummary?.competitors_failed ?? Math.max(0, foundCount - analyzedCount);

  return (
    <Card
      title="Конкурентные страницы"
      subtitle="Реальные результаты из поисковой выдачи по введённому запросу."
    >
      {loading ? <div className="empty-state">Подбираем конкурентные страницы...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {!loading && !error && failureContext?.stage === "search" ? (
        <FailureContextBanner context={failureContext} title="Сравнение с конкурентами не построено" />
      ) : null}

      {!loading && !error && competitors.length === 0 && failureContext?.stage !== "search" ? (
        <div className="empty-state">
          По этому запросу пока не удалось собрать релевантные страницы конкурентов. Повторите аудит позже или уточните поисковый запрос.
        </div>
      ) : null}

      {!loading && !error && competitors.length > 0 ? (
        <>
          <div className="metric-strip metric-strip--comparison">
            <div className="metric-box">
              <span className="metric-box__label">Найдено в SERP</span>
              <strong className="metric-box__value">{foundCount}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Успешно обработано</span>
              <strong className="metric-box__value">{analyzedCount}</strong>
            </div>
            <div className="metric-box">
              <span className="metric-box__label">Ограничили доступ</span>
              <strong className="metric-box__value">{failedCount}</strong>
            </div>
          </div>

          {competitorScores.length > 0 ? <ComparisonChart items={competitorScores} /> : null}

          <div className="competitor-list">
            {competitors.map((competitor) => (
              <article key={competitor.url} className="competitor-list__item">
                <div>
                  <div className="competitor-list__domain">{competitor.domain}</div>
                  <div className="competitor-list__title">{competitor.title || "Без заголовка"}</div>
                  <div className="competitor-list__url">{competitor.url}</div>
                  {competitor.fetch_status === "failed" ? (
                    <div className="competitor-list__note">
                      {competitor.fetch_error_message ?? competitor.fetch_error_code ?? "Страница не обработана"}
                    </div>
                  ) : (
                    <div className="competitor-list__note">
                      Способ загрузки: {getFetchMethodLabel(competitor.fetch_method)}
                    </div>
                  )}
                </div>
                <div className="competitor-list__side">
                  <span className={`status-pill status-pill--fetch-${competitor.fetch_status}`}>
                    {competitor.fetch_status === "success" ? "Обработан" : "Недоступен"}
                  </span>
                  <div className="competitor-list__score">{competitor.score !== null ? Math.round(competitor.score) : "—"}</div>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </Card>
  );
}

function NewAuditWorkspace({
  submitting,
  submissionError,
  success,
  runtimeHealth,
  loadingRuntime,
  runtimeError,
  onRefreshRuntime,
  onOpenRuntime,
  onCreateAudit,
}: Pick<
  EmptyWorkspaceProps,
  | "submitting"
  | "submissionError"
  | "success"
  | "runtimeHealth"
  | "loadingRuntime"
  | "runtimeError"
  | "onRefreshRuntime"
  | "onOpenRuntime"
  | "onCreateAudit"
>) {
  return (
    <div className="workspace-empty">
      <Card className="hero-card workspace-empty__hero">
        <div className="hero-card__content">
          <div>
            <span className="eyebrow-pill">Новый аудит</span>
            <h2 className="hero-card__title">Запустите новую проверку сайта</h2>
            <p className="hero-card__text">
              Введите поисковый запрос и URL сайта. После запуска откроется рабочее пространство аудита с итоговой оценкой,
              сравнением и рекомендациями.
            </p>
          </div>
          <ScoreRing value={0} label="Старт" />
        </div>

        <div className="hero-card__actions">
          <AuditLaunchForm
            isSubmitting={submitting}
            submitLabel="Запустить аудит"
            onSubmit={onCreateAudit}
          />
          {submissionError ? (
            <div className="feedback-banner feedback-banner--error">{submissionError}</div>
          ) : null}
          {success ? <div className="feedback-banner feedback-banner--success">{success}</div> : null}
        </div>
      </Card>

      <RuntimeStatusCompactCard
        model={runtimeHealth}
        loading={loadingRuntime}
        error={runtimeError}
        onRefresh={onRefreshRuntime}
        onOpenFull={onOpenRuntime}
      />
    </div>
  );
}


export function AuditWorkspace({
  currentAudit,
  currentResults,
  recommendations,
  timelineDiagnostics,
  timelineEvents,
  pageRows,
  competitorScores,
  comparisonSummary,
  auditStatus,
  loading,
  error,
  activeTab,
  onTabChange,
}: AuditWorkspaceProps) {
  if (!currentAudit && loading) {
    return <div className="empty-state">Загружаем выбранный аудит...</div>;
  }

  if (!currentAudit && error) {
    return <div className="feedback-banner feedback-banner--error">{error}</div>;
  }

  if (!currentAudit) {
    return <div className="empty-state">Выберите аудит, чтобы открыть рабочее пространство.</div>;
  }

  const failureContext = resolveAuditFailureContext(currentAudit, currentResults);

  return (
    <div className="workspace">
      <div className="workspace__header">
        <div>
          <p className="content__eyebrow">Рабочее пространство аудита</p>
          <h1 className="content__title">{getDomain(currentAudit.target_url)}</h1>
          <p className="workspace__subtitle">{currentAudit.query}</p>
        </div>
        <div className="workspace__status">
          <span className={`status-pill status-pill--${currentAudit.status}`}>
            {getAuditStatusLabel(currentAudit.status as AuditStatus)}
          </span>
        </div>
      </div>

      <AuditWarnings currentAudit={currentAudit} currentResults={currentResults} failureContext={failureContext} />
      <AuditProgressBanner status={currentAudit.status as AuditStatus} />

      <AuditTabs activeTab={activeTab} onChange={onTabChange} />

      <div className="workspace__panel">
        {activeTab === "overview" ? (
          <OverviewPanel
            currentAudit={currentAudit}
            currentResults={currentResults}
            recommendations={recommendations}
            competitorScores={competitorScores}
            comparisonSummary={comparisonSummary}
          />
        ) : null}

        {activeTab === "report" ? (
          <AuditReportPage
            currentAudit={currentAudit}
            currentResults={currentResults}
            recommendations={recommendations}
            timelineDiagnostics={timelineDiagnostics}
            auditStatus={auditStatus}
            loading={loading}
            error={error}
            failureContext={failureContext}
          />
        ) : null}

        {activeTab === "timeline" ? (
          <AuditTimelinePage
            currentAudit={currentAudit}
            currentResults={currentResults}
            timelineDiagnostics={timelineDiagnostics}
            timelineEvents={timelineEvents}
            auditStatus={auditStatus}
            loading={loading}
            error={error}
            failureContext={failureContext}
          />
        ) : null}

        {activeTab === "pages" ? (
          <AuditPage rows={pageRows} auditStatus={auditStatus} loading={loading} error={error} />
        ) : null}

        {activeTab === "competitors" ? (
          <CompetitorsPanel
            currentResults={currentResults}
            competitorScores={competitorScores}
            comparisonSummary={comparisonSummary}
            loading={loading}
            error={error}
            failureContext={failureContext}
          />
        ) : null}

        {activeTab === "recommendations" ? (
          <RecommendationsPage
            auditId={currentAudit.id}
            recommendations={recommendations}
            auditStatus={auditStatus}
            loading={loading}
            error={error}
            failureContext={failureContext}
          />
        ) : null}
      </div>
    </div>
  );
}

export function EmptyWorkspace({
  mode,
  recentAudits,
  activeAuditId,
  loadingRecent,
  recentError,
  submitting,
  submissionError,
  success,
  runtimeHealth,
  loadingRuntime,
  runtimeError,
  onRefreshRuntime,
  onOpenRuntime,
  onRefreshRecent,
  onCreateAudit,
  onSelectAudit,
  onRepeatAudit,
}: EmptyWorkspaceProps) {
  if (mode === "history") {
    return (
      <AuditHistoryPanel
        recentAudits={recentAudits}
        activeAuditId={activeAuditId}
        loadingRecent={loadingRecent}
        recentError={recentError}
        submitting={submitting}
        submissionError={submissionError}
        success={success}
        onRefreshRecent={onRefreshRecent}
        onOpenRuntime={onOpenRuntime}
        onSelectAudit={onSelectAudit}
        onRepeatAudit={onRepeatAudit}
      />
    );
  }

  return (
    <NewAuditWorkspace
      submitting={submitting}
      submissionError={submissionError}
      success={success}
      runtimeHealth={runtimeHealth}
      loadingRuntime={loadingRuntime}
      runtimeError={runtimeError}
      onRefreshRuntime={onRefreshRuntime}
      onOpenRuntime={onOpenRuntime}
      onCreateAudit={onCreateAudit}
    />
  );
}
