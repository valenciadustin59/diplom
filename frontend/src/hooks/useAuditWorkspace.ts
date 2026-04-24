import { useCallback, useEffect, useMemo, useState } from "react";
import { auditsApi, ApiError } from "../api/api";
import type {
  AuditCreatePayload,
  AuditResultsResponse,
  AuditStatus,
  AuditStatusResponse,
  AuditSummary,
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

function mapSummary(audit: AuditStatusResponse): AuditSummary {
  return {
    id: audit.id,
    domain: getDomainFromUrl(audit.target_url),
    query: audit.query,
    score: Math.round(audit.score ?? 0),
    status: audit.status,
    createdAt: formatCreatedAt(audit.created_at),
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
  const [recentAudits, setRecentAudits] = useState<AuditSummary[]>([]);
  const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null);
  const [currentAudit, setCurrentAudit] = useState<AuditStatusResponse | null>(null);
  const [results, setResults] = useState<AuditResultsResponse | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsBundle | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refreshAudits = useCallback(async () => {
    try {
      setLoadingRecent(true);
      const audits = await auditsApi.list();
      setRecentAudits(audits.map(mapSummary));
    } catch (nextError) {
      setWorkspaceError(getErrorMessage(nextError));
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  const loadAuditBundle = useCallback(
    async (auditId: string, options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false;

      try {
        if (!silent) {
          setLoadingAudit(true);
        }
        setWorkspaceError(null);

        const status = await auditsApi.getStatus(auditId);
        setCurrentAudit(status);

        const [nextResults, nextRecommendations] = await Promise.all([
          auditsApi.getResults(auditId),
          auditsApi.getRecommendations(auditId),
        ]);

        setResults(nextResults);
        setRecommendations(nextRecommendations.recommendations);
      } catch (nextError) {
        setWorkspaceError(getErrorMessage(nextError));
      } finally {
        if (!silent) {
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
    void loadAuditBundle(selectedAuditId);
  }, [selectedAuditId, loadAuditBundle]);

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
        setCurrentAudit(audit);
        setSelectedAuditId(audit.id);
        setResults(null);
        setRecommendations(null);
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
    setSelectedAuditId(auditId);
    setCurrentAudit(null);
    setResults(null);
    setRecommendations(null);
    setSuccess(null);
    setWorkspaceError(null);
  }, []);

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
    pageRows,
    overallScore,
    competitorScores,
    comparisonSummary,
    auditStatus,
    selectedAuditId,
    loadingRecent,
    loadingAudit,
    submitting,
    submissionError,
    workspaceError,
    success,
    createAudit,
    refreshAudits,
    selectAudit,
  };
}
