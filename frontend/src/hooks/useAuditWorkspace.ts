import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { auditsApi, ApiError } from "../api/api";
import type {
  AuditCreatePayload,
  AuditListItemResponse,
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditSummary,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  ComparisonSummary,
  CompetitorResult,
  CompetitorScore,
  PageRow,
  RecommendationsBundle,
} from "../types";

const ACTIVE_AUDIT_POLL_INTERVAL_MS = 1000;
const ACTIVE_HISTORY_REFRESH_INTERVAL_MS = 12000;

function getDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatCreatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getCreatedAtTimestamp(value: string): number | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.getTime();
}

function mapSummary(audit: AuditListItemResponse): AuditSummary {
  return {
    id: audit.id,
    domain: getDomainFromUrl(audit.target_url),
    query: audit.query,
    targetUrl: audit.target_url,
    topN: audit.top_n,
    score: Math.round(audit.score ?? 0),
    status: audit.status,
    createdAt: formatCreatedAt(audit.created_at),
    createdAtTimestamp: getCreatedAtTimestamp(audit.created_at),
    scoreBreakdown: audit.score_breakdown,
    comparisonSummary: audit.comparison_summary ?? null,
  };
}

function buildComparisonChartItems(
  userUrl: string | undefined,
  userScore: number | null | undefined,
  competitors: CompetitorResult[] | null | undefined,
): CompetitorScore[] {
  const analyzedCompetitors = (competitors ?? []).filter(
    (competitor) => competitor.fetch_status === "success" && typeof competitor.score === "number",
  );

  if (typeof userScore !== "number" || analyzedCompetitors.length === 0) {
    return [];
  }

  return [
    {
      name: getDomainFromUrl(userUrl ?? "Ваш сайт"),
      score: Math.round(userScore),
      isUser: true,
    },
    ...analyzedCompetitors.map((competitor) => ({
      name: competitor.domain,
      score: Math.round(competitor.score ?? 0),
    })),
  ];
}

function buildPageRows(
  audit: AuditStatusResponse | null,
  results: AuditResultsResponse | null,
): PageRow[] {
  if (!audit) {
    return [];
  }

  const features = results?.features ?? audit.features ?? {};
  const titlePresent = Number(features.title_present ?? 0) > 0;
  const titleLength = Number(features.title_length ?? 0);
  const semanticSimilarity = Number(features.semantic_similarity ?? 0);
  const textLength = Number(features.text_length_chars ?? results?.extracted_text?.length ?? 0);

  const rows: PageRow[] = [
    {
      id: audit.id,
      url: audit.target_url,
      pageType: "Основная страница",
      score: Math.round(results?.score ?? audit.score ?? 0),
      textLength,
      seoTitle: titlePresent ? `Заголовок найден (${titleLength} симв.)` : "Заголовок отсутствует",
      queryMatch: semanticSimilarity,
      fetchStatus: results?.target_fetch_status ?? audit.target_fetch_status ?? "success",
      fetchNote:
        results?.target_fetch_error_message ??
        audit.target_fetch_error_message ??
        "Страница обработана",
    },
  ];

  for (const competitor of results?.competitor_results ?? []) {
    const competitorFeatures = competitor.features ?? {};
    const isAnalyzed = competitor.fetch_status === "success" && typeof competitor.score === "number";
    rows.push({
      id: `${audit.id}:${competitor.url}`,
      url: competitor.url,
      pageType: isAnalyzed ? "Конкурент" : "Конкурент (не обработан)",
      score: Math.round(competitor.score ?? 0),
      textLength: Number(competitorFeatures.text_length_chars ?? 0),
      seoTitle: competitor.title || "Заголовок отсутствует",
      queryMatch: Number(competitorFeatures.semantic_similarity ?? 0),
      fetchStatus: competitor.fetch_status,
      fetchNote:
        competitor.fetch_status === "success"
          ? "Страница обработана"
          : competitor.fetch_error_message ?? competitor.fetch_error_code ?? "Страница не обработана",
    });
  }

  return rows;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Непредвиденная ошибка";
}

export function useAuditWorkspace() {
  const loadRequestRef = useRef(0);
  const lastSilentHistoryRefreshRef = useRef(0);
  const recentAuditsLoadedRef = useRef(false);
  const selectedAuditIdRef = useRef<string | null>(null);
  const [recentAudits, setRecentAudits] = useState<AuditSummary[]>([]);
  const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null);
  const [currentAudit, setCurrentAudit] = useState<AuditStatusResponse | null>(null);
  const [results, setResults] = useState<AuditResultsResponse | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsBundle | null>(null);
  const [timelineDiagnostics, setTimelineDiagnostics] = useState<AuditTimelineDiagnosticsResponse | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<AuditTimelineEventsResponse | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    selectedAuditIdRef.current = selectedAuditId;
  }, [selectedAuditId]);

  const refreshAudits = useCallback(async (options?: { silent?: boolean }) => {
    const shouldShowLoading = !options?.silent && !recentAuditsLoadedRef.current;
    try {
      if (shouldShowLoading) {
        setLoadingRecent(true);
      }
      const audits = await auditsApi.list();
      setRecentAudits(audits.map(mapSummary));
      recentAuditsLoadedRef.current = true;
      setRecentError(null);
    } catch (nextError) {
      setRecentError(getErrorMessage(nextError));
    } finally {
      if (shouldShowLoading) {
        setLoadingRecent(false);
      }
    }
  }, []);

  const loadAuditBundle = useCallback(
    async (auditId: string, options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false;
      const requestId = ++loadRequestRef.current;

      try {
        if (!silent) {
          setLoadingAudit(true);
        }
        setWorkspaceError(null);

        const status = await auditsApi.getStatus(auditId);
        if (requestId !== loadRequestRef.current) {
          return;
        }
        setCurrentAudit(status);
        const statusRecommendations = status.recommendations ?? null;

        const [nextResults, nextRecommendations, nextTimelineDiagnostics, nextTimelineEvents] = await Promise.allSettled([
          auditsApi.getResults(auditId),
          auditsApi.getRecommendations(auditId),
          auditsApi.getTimelineDiagnostics(auditId),
          auditsApi.getTimelineEvents(auditId),
        ] as const);

        if (requestId !== loadRequestRef.current) {
          return;
        }

        if (nextResults.status === "fulfilled") {
          setResults(nextResults.value);
        } else {
          setResults(null);
        }

        if (nextRecommendations.status === "fulfilled") {
          setRecommendations(nextRecommendations.value.recommendations ?? statusRecommendations);
        } else {
          setRecommendations(statusRecommendations);
        }

        if (nextTimelineDiagnostics.status === "fulfilled") {
          setTimelineDiagnostics(nextTimelineDiagnostics.value);
        } else {
          setTimelineDiagnostics(null);
        }

        if (nextTimelineEvents.status === "fulfilled") {
          setTimelineEvents(nextTimelineEvents.value);
        } else {
          setTimelineEvents(null);
        }
      } catch (nextError) {
        if (requestId !== loadRequestRef.current) {
          return;
        }
        setWorkspaceError(getErrorMessage(nextError));
      } finally {
        if (requestId === loadRequestRef.current && !silent) {
          setLoadingAudit(false);
        }
      }
    },
    [],
  );

  const loadAuditProgress = useCallback(
    async (auditId: string) => {
      const [statusResult, timelineEventsResult] = await Promise.allSettled([
        auditsApi.getStatus(auditId),
        auditsApi.getTimelineEvents(auditId),
      ] as const);

      if (selectedAuditIdRef.current !== auditId) {
        return;
      }

      if (statusResult.status === "fulfilled") {
        const status = statusResult.value;
        setCurrentAudit(status);
        setWorkspaceError(null);

        if (status.recommendations) {
          setRecommendations((current) => current ?? status.recommendations ?? null);
        }

        if (status.status !== "queued" && status.status !== "processing") {
          void loadAuditBundle(auditId, { silent: true });
          void refreshAudits({ silent: true });
        }
      }

      if (timelineEventsResult.status === "fulfilled") {
        setTimelineEvents(timelineEventsResult.value);
      }
    },
    [loadAuditBundle, refreshAudits],
  );

  useEffect(() => {
    void refreshAudits();
  }, [refreshAudits]);

  useEffect(() => {
    if (!selectedAuditId) {
      return;
    }

    const status = currentAudit?.status;
    if (status !== "queued" && status !== "processing") {
      return;
    }

    const timerId = window.setInterval(() => {
      void loadAuditProgress(selectedAuditId);
      const now = Date.now();
      if (now - lastSilentHistoryRefreshRef.current >= ACTIVE_HISTORY_REFRESH_INTERVAL_MS) {
        lastSilentHistoryRefreshRef.current = now;
        void refreshAudits({ silent: true });
      }
    }, ACTIVE_AUDIT_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timerId);
    };
  }, [currentAudit?.status, loadAuditProgress, refreshAudits, selectedAuditId]);

  const createAudit = useCallback(
    async (payload: AuditCreatePayload): Promise<AuditStatusResponse | null> => {
      try {
        setSubmitting(true);
        setSubmissionError(null);
        setWorkspaceError(null);
        setSuccess(null);

        const audit = await auditsApi.create(payload);
        loadRequestRef.current += 1;
        setCurrentAudit(audit);
        setSelectedAuditId(audit.id);
        setResults(null);
        setRecommendations(null);
        setTimelineDiagnostics(null);
        setTimelineEvents(null);
        setSuccess("Аудит успешно запущен.");
        await refreshAudits();
        return audit;
      } catch (nextError) {
        setSubmissionError(getErrorMessage(nextError));
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshAudits],
  );

  const selectAudit = useCallback((auditId: string) => {
    loadRequestRef.current += 1;
    setSelectedAuditId(auditId);
    setCurrentAudit(null);
    setResults(null);
    setRecommendations(null);
    setTimelineDiagnostics(null);
    setTimelineEvents(null);
    setSuccess(null);
    setWorkspaceError(null);
    void loadAuditBundle(auditId);
  }, [loadAuditBundle]);

  const overallScore = Math.round(results?.score ?? currentAudit?.score ?? 0);
  const comparisonSummary = (results?.comparison_summary ?? currentAudit?.comparison_summary ?? null) as ComparisonSummary | null;
  const competitorScores = useMemo(
    () =>
      buildComparisonChartItems(
        currentAudit?.target_url,
        results?.score ?? currentAudit?.score,
        results?.competitor_results ?? currentAudit?.competitor_results,
      ),
    [
      currentAudit?.competitor_results,
      currentAudit?.score,
      currentAudit?.target_url,
      results?.competitor_results,
      results?.score,
    ],
  );
  const pageRows = useMemo(() => buildPageRows(currentAudit, results), [currentAudit, results]);
  const auditStatus = (currentAudit?.status ?? "queued") as AuditStatus;

  return {
    recentAudits,
    currentAudit,
    currentResults: results,
    recommendations,
    timelineDiagnostics,
    timelineEvents,
    pageRows,
    overallScore,
    competitorScores,
    comparisonSummary,
    auditStatus,
    selectedAuditId,
    loadingRecent,
    loadingAudit,
    recentError,
    submitting,
    submissionError,
    workspaceError,
    success,
    createAudit,
    refreshAudits,
    selectAudit,
  };
}
