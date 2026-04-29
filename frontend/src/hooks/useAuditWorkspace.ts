import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { auditsApi, ApiError } from "../api/api";
import type {
  AuditCreatePayload,
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

function mapSummary(audit: AuditStatusResponse): AuditSummary {
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
      seoTitle: titlePresent ? `Title найден (${titleLength} симв.)` : "Title отсутствует",
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
      seoTitle: competitor.title || "Title отсутствует",
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

  const refreshAudits = useCallback(async () => {
    try {
      setLoadingRecent(true);
      const audits = await auditsApi.list();
      setRecentAudits(audits.map(mapSummary));
      setRecentError(null);
    } catch (nextError) {
      setRecentError(getErrorMessage(nextError));
    } finally {
      setLoadingRecent(false);
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
      void loadAuditBundle(selectedAuditId, { silent: true });
      void refreshAudits();
    }, 3000);

    return () => {
      window.clearInterval(timerId);
    };
  }, [currentAudit?.status, loadAuditBundle, refreshAudits, selectedAuditId]);

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
