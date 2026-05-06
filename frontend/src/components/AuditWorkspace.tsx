import { AuditPage } from "../pages/AuditPage";
import { AuditReportPage } from "../pages/AuditReportPage";
import { AuditTimelinePage } from "../pages/AuditTimelinePage";
import { RecommendationsPage } from "../pages/RecommendationsPage";
import { RuntimeStatusCompactCard } from "../pages/RuntimeStatusPage";
import { buildScoreConfidenceView } from "../lib/auditConfidence";
import { buildAuditLowScoreReason, type AuditLowScoreReason } from "../lib/auditLowScoreReason";
import {
  buildCompetitorContextStats,
  formatCompetitorContextSummary,
  getAcceptedCompetitors,
  getCompetitorContextStatusLabel,
  getExcludedCompetitors,
} from "../lib/competitorContext";
import { getEarlyStopMismatchView } from "../lib/earlyStop";
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
  CompetitorResult,
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

function getDisplayUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname && parsed.pathname !== "/" ? parsed.pathname : "";
    const query = parsed.search ?? "";
    return decodeURI(`${parsed.hostname}${path}${query}`);
  } catch {
    return url;
  }
}

function formatScoreValue(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(Math.round(value * 10) / 10) : "—";
}

function formatSignedScoreValue(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function getFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getCompetitorContextNotice(summary?: ComparisonSummary | null): string | null {
  const status = summary?.competitor_context_status ?? summary?.competitor_context_quality?.status;
  if (status === "insufficient_processed_competitors") {
    return "Сравнение с рынком пока не используется в итоговой оценке: обработано слишком мало страниц из выдачи.";
  }
  if (status === "no_serp_results") {
    return "По этому запросу не удалось получить страницы конкурентов, поэтому показана оценка самой страницы.";
  }
  if (status === "partial_but_usable") {
    return "Часть страниц из выдачи ограничила автоматический доступ, но обработанных конкурентов достаточно для сравнения.";
  }
  return null;
}

function getCompetitivenessMetric(breakdown: ScoreBreakdown | null | undefined, key: string): number | null {
  return getFiniteNumber(breakdown?.competitiveness?.[key]);
}

function getDisplayedFinalScore({
  currentAudit,
  currentResults,
  comparisonSummary,
}: {
  currentAudit: AuditStatusResponse | null;
  currentResults: AuditResultsResponse | null;
  comparisonSummary: ComparisonSummary | null;
}): number {
  return (
    getFiniteNumber(currentResults?.score_breakdown?.final_score) ??
    getFiniteNumber(currentResults?.score_breakdown?.competitiveness_score) ??
    getFiniteNumber(currentResults?.score) ??
    getFiniteNumber(currentAudit?.score_breakdown?.final_score) ??
    getFiniteNumber(currentAudit?.score) ??
    getFiniteNumber(comparisonSummary?.competitiveness_score) ??
    getFiniteNumber(comparisonSummary?.user_score) ??
    0
  );
}

function getDisplayedPrimaryScore({
  currentAudit,
  currentResults,
  comparisonSummary,
}: {
  currentAudit: AuditStatusResponse | null;
  currentResults: AuditResultsResponse | null;
  comparisonSummary: ComparisonSummary | null;
}): number {
  return (
    getFiniteNumber(currentResults?.score_breakdown?.primary_page_score) ??
    getFiniteNumber(currentAudit?.score_breakdown?.primary_page_score) ??
    getFiniteNumber(comparisonSummary?.primary_page_score) ??
    getDisplayedFinalScore({ currentAudit, currentResults, comparisonSummary })
  );
}

function hasCompetitivenessContext(breakdown: ScoreBreakdown | null | undefined): boolean {
  const competitiveness = breakdown?.competitiveness;
  return Boolean(
    competitiveness &&
      typeof competitiveness === "object" &&
      "context_available" in competitiveness &&
      competitiveness.context_available === true,
  );
}

function getScoreFactorId(item: ScoreFactor, index: number): string {
  return item.code ?? item.key ?? `${item.label}:${index}`;
}

function getFactorSearchText(item: ScoreFactor): string {
  return `${item.label} ${item.code ?? ""} ${item.key ?? ""}`.toLowerCase();
}

function getFactorImpactLabel(value: number, tone: "positive" | "negative"): string {
  const magnitude = Math.abs(value);
  if (tone === "positive") {
    if (magnitude >= 12) {
      return "Сильно помогает";
    }
    if (magnitude >= 6) {
      return "Заметно помогает";
    }
    return "Небольшой плюс";
  }

  if (magnitude >= 12) {
    return "Сильно мешает";
  }
  if (magnitude >= 6) {
    return "Заметно мешает";
  }
  return "Небольшое ограничение";
}

function getScoreFactorUserExplanation(item: ScoreFactor, tone: "positive" | "negative"): string {
  const text = getFactorSearchText(item);
  const isPositive = tone === "positive";

  if (/смысл|semantic|соответ|релевант|relevance|intent|тема|topic|query/.test(text)) {
    return isPositive
      ? "Страница хорошо попадает в тему запроса: пользователю проще понять, что это именно тот ответ или услуга."
      : "Странице нужно яснее показать связь с запросом: объект, услуга или намерение пользователя считываются недостаточно уверенно.";
  }

  if (/ключ|keyword|coverage|phrase|вхожд|prominence/.test(text)) {
    return isPositive
      ? "Важные слова запроса уже заметны в содержании и помогают поисковой системе связать страницу с темой."
      : "Важные слова запроса стоит добавить естественно: в заголовок, первый экран, описания услуги или ответы на вопросы.";
  }

  if (/title|заголов|heading|h1|h2/.test(text)) {
    return isPositive
      ? "Заголовки помогают быстро понять тему страницы и поддерживают соответствие запросу."
      : "Заголовки стоит сделать точнее: пользователь и поисковая система должны сразу видеть, чему посвящена страница.";
  }

  if (/коммер|commercial|цена|price|стоим|купить|заказать|order|контакт|phone|trust|довер/.test(text)) {
    return isPositive
      ? "На странице есть признаки доверия и готовности к действию: контакты, понятные условия или путь к заявке."
      : "Усилите коммерческую часть: добавьте понятные условия, контакты, доверие, форму заявки или ценовой ориентир там, где это уместно.";
  }

  if (/текст|content|word|полнот|depth|coverage|ответ/.test(text)) {
    return isPositive
      ? "Страница достаточно раскрывает тему и даёт пользователю полезный ответ по запросу."
      : "Раскройте тему подробнее: добавьте важные детали, варианты выбора, ограничения, примеры или ответы на частые вопросы.";
  }

  if (/technical|index|canonical|redirect|viewport|status|fetch|http|доступ|индекс/.test(text)) {
    return isPositive
      ? "Техническая часть не мешает странице обрабатываться и попадать в сравнение."
      : "Проверьте техническую доступность: индексацию, canonical, редиректы, корректный ответ страницы и мобильное отображение.";
  }

  return isPositive
    ? "Этот фактор усиливает страницу в сравнении с запросом и конкурентами."
    : "Этот фактор ограничивает конкурентность страницы. Его стоит проверить перед следующей итерацией улучшений.";
}

function getScoreFactorEmptyText(tone: "positive" | "negative"): string {
  return tone === "positive"
    ? "Сильные стороны появятся после завершения аудита."
    : "Явных ограничений в этом блоке не найдено. Проверьте рекомендации ниже, если хотите усилить страницу точечно.";
}

function collectScoreFactors(breakdown: ScoreBreakdown, tone: "positive" | "negative"): ScoreFactor[] {
  const directFactors =
    tone === "positive"
      ? breakdown.positives ?? breakdown.top_positive_factors ?? []
      : breakdown.negatives ?? breakdown.top_negative_factors ?? [];
  const sourceFactors =
    directFactors.length > 0
      ? directFactors
      : (breakdown.factor_groups ?? []).flatMap((group) =>
          group.items.filter((item) => (tone === "positive" ? item.impact >= 0 : item.impact < 0)),
        );
  const seen = new Set<string>();

  return sourceFactors
    .filter((item) => (tone === "positive" ? item.impact > 0 : item.impact < 0))
    .filter((item) => {
      const id = getScoreFactorId(item, seen.size);
      if (seen.has(id)) {
        return false;
      }
      seen.add(id);
      return true;
    })
    .slice(0, 5);
}

function getScoreMethodologyText(
  breakdown?: ScoreBreakdown | null,
  lowScoreReason?: AuditLowScoreReason | null,
): string {
  if (lowScoreReason && (lowScoreReason.isBlocking || lowScoreReason.category === "query_mismatch")) {
    return lowScoreReason.message;
  }

  const earlyStopView = getEarlyStopMismatchView(breakdown);
  if (earlyStopView) {
    return earlyStopView.message;
  }

  if (hasCompetitivenessContext(breakdown)) {
    return "Сначала проверяется, отвечает ли страница именно на введённый запрос. Если тема совпадает, итоговая оценка учитывает качество страницы и то, как она выглядит на фоне реально обработанных страниц из выдачи.";
  }

  return "Сначала оценивается соответствие страницы запросу: тема, намерение пользователя и полнота ответа. Сравнение с конкурентами появится после обработки страниц из выдачи.";
}

const scoreExplanationPrinciples = [
  {
    title: "Соответствие запросу",
    detail: "Страница должна быть про тот же объект, услугу или вопрос, который ввёл пользователь.",
  },
  {
    title: "Полнота ответа",
    detail: "Учитывается, насколько страница раскрывает тему и помогает принять решение.",
  },
  {
    title: "Готовность к действию",
    detail: "Для коммерческих запросов важны понятные контакты, доверие и путь к заявке или покупке.",
  },
  {
    title: "Фон выдачи",
    detail: "Когда конкуренты обработаны, оценка показывает, насколько страница сильна рядом с ними.",
  },
];

function LowScoreReasonBanner({
  reason,
  compact = false,
}: {
  reason: AuditLowScoreReason | null;
  compact?: boolean;
}) {
  if (!reason || reason.kind === "unknown") {
    return null;
  }

  return (
    <div className={`low-score-reason low-score-reason--${reason.tone}${compact ? " low-score-reason--compact" : ""}`}>
      <div className="low-score-reason__header">
        <span>{reason.badge}</span>
        <strong>{reason.title}</strong>
      </div>
      <p>{reason.message}</p>
      {reason.recoveryActions.length > 0 ? (
        <ul className="low-score-reason__actions">
          {reason.recoveryActions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ScoreFactorList({
  title,
  items = [],
  tone,
  subtitle,
}: {
  title: string;
  items?: ScoreFactor[];
  tone: "positive" | "negative";
  subtitle: string;
}) {
  return (
    <div className={`score-factor-group score-factor-group--${tone}`}>
      <div className="score-factor-group__header">
        <h4 className="score-factor-group__title">{title}</h4>
        <p>{subtitle}</p>
      </div>
      {items.length > 0 ? (
        <div className="score-factor-list">
          {items.map((item, index) => {
            const detail = getScoreFactorUserExplanation(item, tone);

            return (
              <article key={getScoreFactorId(item, index)} className={`score-factor score-factor--${tone}`}>
                <div className="score-factor__top">
                  <strong>{getHumanReadableLabel(item.label)}</strong>
                  <span className={`score-factor__impact score-factor__impact--${tone}`}>
                    {getFactorImpactLabel(item.impact, tone)}
                  </span>
                </div>
                {detail ? <p className="score-factor__detail">{detail}</p> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">{getScoreFactorEmptyText(tone)}</div>
      )}
    </div>
  );
}

function ScoreBreakdownCard({
  breakdown,
  lowScoreReason,
}: {
  breakdown: ScoreBreakdown | null | undefined;
  lowScoreReason: AuditLowScoreReason | null;
}) {
  if (!breakdown) {
    return (
      <Card
        title="Что означает оценка"
        subtitle="После завершения аудита здесь появится понятное объяснение результата, сильных сторон и просадок."
      >
        <div className="empty-state">Дождитесь завершения анализа, чтобы увидеть расшифровку итоговой оценки.</div>
      </Card>
    );
  }

  const positiveFactors = collectScoreFactors(breakdown, "positive");
  const negativeFactors = collectScoreFactors(breakdown, "negative");
  const methodology = getScoreMethodologyText(breakdown, lowScoreReason);
  const earlyStopView = getEarlyStopMismatchView(breakdown);

  if (lowScoreReason?.isBlocking) {
    return (
      <Card
        title="Что означает оценка"
        subtitle="Сначала нужно восстановить доступность страницы; обычные SEO-выводы сейчас не главный результат."
      >
        <div className="score-breakdown score-breakdown--recovery">
          <LowScoreReasonBanner reason={lowScoreReason} />
          <div className="metric-strip metric-strip--comparison">
            <div className="metric-box">
              <span className="metric-box__label">Итоговая оценка</span>
              <strong className="metric-box__value">{breakdown.final_score}</strong>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (earlyStopView) {
    return (
      <Card title="Что означает оценка" subtitle="Аудит остановлен до сравнения с выдачей, чтобы не смешивать разные темы.">
        <div className="score-breakdown score-breakdown--early-stop">
          <div className="early-stop-state">
            <div>
              <strong>{earlyStopView.title}</strong>
              <p>{earlyStopView.message}</p>
            </div>
            {earlyStopView.score !== null ? <span>{formatScoreValue(earlyStopView.score)}</span> : null}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="score-overview-section">
      <Card
        title="Что означает оценка"
        subtitle="Оценка показывает, насколько страница подходит под запрос и насколько уверенно конкурирует в выдаче."
      >
        <div className="score-breakdown score-breakdown--meaning">
          <p className="score-breakdown__methodology">{methodology}</p>

          <div className="score-meaning-layout">
            <div className="score-meaning-total">
              <span>Итоговая оценка</span>
              <strong>{formatScoreValue(breakdown.final_score)}</strong>
              <p>Сначала проверяется соответствие запросу. Если страница подходит, дальше учитывается качество ответа и фон выдачи.</p>
            </div>

            <div className="score-explanation-principles">
              {scoreExplanationPrinciples.map((principle) => (
                <article key={principle.title} className="score-principle-card">
                  <strong>{principle.title}</strong>
                  <p>{principle.detail}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card
        title="Что влияет на оценку"
        subtitle="Сильные стороны и проблемы показаны простым языком: что уже помогает странице и что стоит улучшить, чтобы она увереннее конкурировала по запросу."
      >
        <div className="score-breakdown">
          <div className="score-breakdown__grid">
            <ScoreFactorList
              title="Что помогает странице"
              subtitle="Сигналы, из-за которых страница выглядит сильнее по этому запросу."
              items={positiveFactors}
              tone="positive"
            />
            <ScoreFactorList
              title="Что мешает странице"
              subtitle="Места, где страница может проигрывать запросу или конкурентам."
              items={negativeFactors}
              tone="negative"
            />
          </div>
        </div>
      </Card>
    </div>
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
      : "Система загружает целевую страницу, проверяет её соответствие запросу и отдельно собирает конкурентов для сравнения и рекомендаций. Данные обновляются автоматически.";

  return (
    <div className="feedback-banner feedback-banner--info">
      <strong>{title}</strong>
      <div>{message}</div>
    </div>
  );
}

function getCompetitorStatusText(competitor: CompetitorResult, excluded: boolean): string {
  if (excluded) {
    return getCompetitorContextStatusLabel(competitor.competitor_context_status);
  }
  if (competitor.competitor_context_status === "accepted") {
    return "В расчёте";
  }
  return competitor.fetch_status === "success" ? "Обработан" : "Недоступен";
}

function getCompetitorNote(competitor: CompetitorResult, excluded: boolean): string {
  if (excluded) {
    return "Кандидат отделён от конкурентного расчёта.";
  }
  if (competitor.fetch_status === "failed") {
    return competitor.fetch_error_message ?? competitor.fetch_error_code ?? "Страница не обработана";
  }
  return `Способ загрузки: ${getFetchMethodLabel(competitor.fetch_method)}`;
}

function CompetitorListItem({ competitor, excluded = false }: { competitor: CompetitorResult; excluded?: boolean }) {
  const statusClass = excluded ? "status-pill--muted" : `status-pill--fetch-${competitor.fetch_status}`;

  return (
    <article className={`competitor-list__item${excluded ? " competitor-list__item--excluded" : ""}`}>
      <div>
        <div className="competitor-list__domain">{competitor.domain}</div>
        <div className="competitor-list__title">{competitor.title || "Без заголовка"}</div>
        <div className="competitor-list__url">{competitor.url}</div>
        <div className="competitor-list__note">{getCompetitorNote(competitor, excluded)}</div>
      </div>
      <div className="competitor-list__side">
        <span className={`status-pill ${statusClass}`}>{getCompetitorStatusText(competitor, excluded)}</span>
        {!excluded ? <div className="competitor-list__score">{competitor.score !== null ? Math.round(competitor.score) : "—"}</div> : null}
      </div>
    </article>
  );
}

function buildAcceptedComparisonItems(
  targetUrl: string | undefined,
  userScore: number,
  competitors: CompetitorResult[] | null | undefined,
  fallbackItems: CompetitorScore[],
): CompetitorScore[] {
  if (!competitors || competitors.length === 0) {
    return fallbackItems;
  }

  const acceptedCompetitors = getAcceptedCompetitors(competitors).filter(
    (competitor) => competitor.fetch_status === "success" && typeof competitor.score === "number",
  );

  if (acceptedCompetitors.length === 0) {
    return [];
  }

  return [
    {
      name: getDomain(targetUrl ?? "Ваш сайт"),
      score: Math.round(userScore),
      isUser: true,
    },
    ...acceptedCompetitors.map((competitor) => ({
      name: competitor.domain,
      score: Math.round(competitor.score ?? 0),
    })),
  ];
}

function filterAcceptedPageRows(rows: PageRow[], competitors: CompetitorResult[] | null | undefined): PageRow[] {
  const excludedUrls = new Set(getExcludedCompetitors(competitors).map((competitor) => competitor.url));
  if (excludedUrls.size === 0) {
    return rows;
  }
  return rows.filter((row) => !excludedUrls.has(row.url));
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
  const rawCompetitors = currentResults?.competitor_results ?? currentAudit?.competitor_results;
  const contextStats = buildCompetitorContextStats(comparisonSummary, rawCompetitors);
  const contextSummary = formatCompetitorContextSummary(contextStats);
  const foundCount = contextStats.collected;
  const analyzedCount = contextStats.accepted;
  const finalScore = getDisplayedFinalScore({ currentAudit, currentResults, comparisonSummary });
  const displayedCompetitorScores = buildAcceptedComparisonItems(
    currentAudit?.target_url,
    finalScore,
    rawCompetitors,
    competitorScores,
  );
  const primaryScore = getDisplayedPrimaryScore({ currentAudit, currentResults, comparisonSummary });
  const competitorAverageScore =
    getCompetitivenessMetric(currentResults?.score_breakdown, "competitor_average_score") ??
    getCompetitivenessMetric(currentAudit?.score_breakdown, "competitor_average_score") ??
    getFiniteNumber(comparisonSummary?.competitors_average_score);
  const marketDifference =
    competitorAverageScore !== null
      ? finalScore - competitorAverageScore
      : getFiniteNumber(comparisonSummary?.score_difference);
  const scoreConfidence = buildScoreConfidenceView({
    audit: currentAudit,
    results: currentResults,
    recommendations,
    comparisonSummary,
  });
  const showDataQualityBadge = scoreConfidence.warningCount > 0 || scoreConfidence.errorCount > 0;
  const earlyStopView =
    getEarlyStopMismatchView(currentResults?.score_breakdown) ?? getEarlyStopMismatchView(currentAudit?.score_breakdown);
  const competitorContextNotice = getCompetitorContextNotice(comparisonSummary);
  const lowScoreReason = buildAuditLowScoreReason({
    audit: currentAudit,
    results: currentResults,
    recommendations,
    comparisonSummary,
  });
  const hasLowScoreReason = lowScoreReason.kind !== "unknown";
  const heroTitle = earlyStopView?.title ?? (hasLowScoreReason ? lowScoreReason.title : currentAudit?.query);

  return (
    <div className="workspace-grid">
      <Card className="workspace-hero">
        <div className="workspace-hero__content">
          <div>
            <span className="eyebrow-pill">Обзор аудита</span>
            <h2 className="workspace-hero__title">{currentAudit ? getDomain(currentAudit.target_url) : "Аудит"}</h2>
            {currentAudit ? <p className="workspace-hero__target">{getDisplayUrl(currentAudit.target_url)}</p> : null}
            <p className="workspace-hero__text">
              {heroTitle ?? "Запустите аудит, чтобы увидеть метрики, сравнение и рекомендации."}
            </p>
            {earlyStopView ? <p className="workspace-hero__text workspace-hero__text--notice">{earlyStopView.message}</p> : null}

            {currentAudit ? (
              <div className="workspace-meta">
                <span className="workspace-meta__item">Статус: {getAuditStatusLabel(currentAudit.status as AuditStatus)}</span>
                <span className="workspace-meta__item">Запущен: {formatDate(currentAudit.created_at)}</span>
                <span className="workspace-meta__item">Загрузка: {getFetchMethodLabel(currentResults?.target_fetch_method ?? currentAudit.target_fetch_method)}</span>
                {showDataQualityBadge ? (
                  <span className={`score-confidence__badge score-confidence__badge--${scoreConfidence.tone}`}>
                    {scoreConfidence.compactLabel}
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>

          <ScoreRing
            value={Math.round(finalScore)}
            label={earlyStopView ? "Не подходит" : lowScoreReason.isBlocking ? "Недоступна" : undefined}
          />
        </div>
      </Card>

      {hasLowScoreReason ? <LowScoreReasonBanner reason={lowScoreReason} compact /> : null}

      <div className="metric-strip workspace-metric-strip">
        <div className="metric-box">
          <span className="metric-box__label">Конкурентная оценка</span>
          <strong className="metric-box__value">{formatScoreValue(finalScore)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Оценка самой страницы</span>
          <strong className="metric-box__value">{formatScoreValue(primaryScore)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Средняя оценка конкурентов</span>
          <strong className="metric-box__value">{formatScoreValue(competitorAverageScore)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Разница с рынком</span>
          <strong className="metric-box__value">{formatSignedScoreValue(marketDifference)}</strong>
        </div>
        <div className="metric-box">
          <span className="metric-box__label">Конкуренты</span>
          <strong className="metric-box__value">{earlyStopView ? "Не запускалось" : `${analyzedCount}/${foundCount}`}</strong>
          {earlyStopView ? <p className="metric-box__note">Страница не отвечает теме запроса.</p> : null}
        </div>
      </div>

      <Card
        className="workspace-competitor-card"
        title="Сравнение с конкурентами"
        subtitle="Чем выше полоса, тем конкурентнее страница по этому запросу. Ваша страница выделена первой, рядом показаны реально обработанные конкуренты из выдачи."
      >
        {earlyStopView ? (
          <div className="early-stop-state early-stop-state--compact">
            <div>
              <strong>{earlyStopView.title}</strong>
              <p>{earlyStopView.message}</p>
            </div>
          </div>
        ) : displayedCompetitorScores.length > 0 ? (
          <>
            <ComparisonChart items={displayedCompetitorScores} />
            {contextSummary ? <p className="competitor-context-summary">{contextSummary}</p> : null}
          </>
        ) : (
          <div className="empty-state">
            {competitorContextNotice ?? contextSummary ?? "Конкурентные страницы ещё не собраны или не удалось обработать ни одну страницу."}
          </div>
        )}
      </Card>

      <ScoreBreakdownCard
        breakdown={currentResults?.score_breakdown ?? currentAudit?.score_breakdown}
        lowScoreReason={lowScoreReason}
      />

      <Card
        className="workspace-recommendations-card"
        title="Ключевые рекомендации"
        subtitle="Первые действия, которые сильнее всего влияют на качество страницы."
      >
        {lowScoreReason.isBlocking ? (
          <LowScoreReasonBanner reason={lowScoreReason} />
        ) : topRecommendationItems.length > 0 ? (
          <RecommendationPreviewList items={topRecommendationItems} />
        ) : (
          <div className="empty-state">Рекомендации появятся после завершения обработки аудита.</div>
        )}
      </Card>
    </div>
  );
}

function CompetitorsPanel({
  currentAudit,
  currentResults,
  competitorScores,
  comparisonSummary,
  loading,
  error,
  failureContext,
}: Pick<
  AuditWorkspaceProps,
  "currentAudit" | "currentResults" | "competitorScores" | "comparisonSummary" | "loading" | "error"
> & {
  failureContext: FailureContext | null;
}) {
  const competitors = currentResults?.competitor_results ?? currentAudit?.competitor_results ?? [];
  const acceptedCompetitors = getAcceptedCompetitors(competitors);
  const excludedCompetitors = getExcludedCompetitors(competitors);
  const contextStats = buildCompetitorContextStats(comparisonSummary, competitors);
  const contextSummary = formatCompetitorContextSummary(contextStats);
  const foundCount = contextStats.collected;
  const analyzedCount = contextStats.accepted;
  const failedCount = contextStats.failed;
  const finalScore = getDisplayedFinalScore({ currentAudit, currentResults, comparisonSummary });
  const displayedCompetitorScores = buildAcceptedComparisonItems(
    currentAudit?.target_url,
    finalScore,
    competitors,
    competitorScores,
  );
  const competitorContextNotice = getCompetitorContextNotice(comparisonSummary);
  const earlyStopView =
    getEarlyStopMismatchView(currentResults?.score_breakdown) ?? getEarlyStopMismatchView(currentAudit?.score_breakdown);

  return (
    <Card
      title="Конкурентные страницы"
      subtitle="Реальные результаты из поисковой выдачи по введённому запросу."
    >
      {loading ? <div className="empty-state">Подбираем конкурентные страницы...</div> : null}
      {!loading && error ? <div className="feedback-banner feedback-banner--error">{error}</div> : null}
      {!loading && !error && earlyStopView ? (
        <div className="early-stop-state early-stop-state--compact">
          <div>
            <strong>{earlyStopView.title}</strong>
            <p>{earlyStopView.message}</p>
          </div>
        </div>
      ) : null}
      {!loading && !error && failureContext?.stage === "search" ? (
        <FailureContextBanner context={failureContext} title="Сравнение с конкурентами не построено" />
      ) : null}

      {!loading && !error && !earlyStopView && competitors.length === 0 && failureContext?.stage !== "search" ? (
        <div className="empty-state">
          По этому запросу пока не удалось собрать релевантные страницы конкурентов. Повторите аудит позже или уточните поисковый запрос.
        </div>
      ) : null}

      {!loading && !error && !earlyStopView && competitors.length > 0 ? (
        <>
          <div className="metric-strip metric-strip--comparison">
            {contextStats.hasQualityV2 ? (
              <>
                <div className="metric-box">
                  <span className="metric-box__label">В расчёте</span>
                  <strong className="metric-box__value">{`${analyzedCount}/${foundCount}`}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Заменены</span>
                  <strong className="metric-box__value">{contextStats.replacements}</strong>
                </div>
                <div className="metric-box">
                  <span className="metric-box__label">Исключены</span>
                  <strong className="metric-box__value">{contextStats.discarded}</strong>
                </div>
              </>
            ) : (
              <>
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
              </>
            )}
          </div>

          {displayedCompetitorScores.length > 0 ? <ComparisonChart items={displayedCompetitorScores} /> : null}
          {contextSummary ? <p className="competitor-context-summary">{contextSummary}</p> : null}
          {competitorContextNotice ? (
            <div className="feedback-banner feedback-banner--info">{competitorContextNotice}</div>
          ) : null}

          {acceptedCompetitors.length > 0 ? (
            <div className="competitor-list">
              {acceptedCompetitors.map((competitor) => (
                <CompetitorListItem key={competitor.url} competitor={competitor} />
              ))}
            </div>
          ) : (
            <div className="empty-state">Валидные конкуренты для расчёта пока не найдены.</div>
          )}

          {excludedCompetitors.length > 0 ? (
            <div className="competitor-list competitor-list--excluded">
              <div className="competitor-list__section-title">Не вошли в расчёт</div>
              {excludedCompetitors.map((competitor) => (
                <CompetitorListItem key={competitor.url} competitor={competitor} excluded />
              ))}
            </div>
          ) : null}
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
  const workspaceCompetitors = currentResults?.competitor_results ?? currentAudit.competitor_results;
  const displayedPageRows = filterAcceptedPageRows(pageRows, workspaceCompetitors);
  const lowScoreReason = buildAuditLowScoreReason({
    audit: currentAudit,
    results: currentResults,
    recommendations,
    comparisonSummary,
  });

  return (
    <div className="workspace">
      <div className="workspace__header">
        <div>
          <p className="content__eyebrow">Рабочее пространство аудита</p>
          <h1 className="content__title">{getDisplayUrl(currentAudit.target_url)}</h1>
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
          <AuditPage rows={displayedPageRows} auditStatus={auditStatus} loading={loading} error={error} />
        ) : null}

        {activeTab === "competitors" ? (
          <CompetitorsPanel
            currentAudit={currentAudit}
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
            lowScoreReason={lowScoreReason}
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
