export type AuditStatus = "queued" | "processing" | "completed" | "completed_with_warnings" | "failed";
export type AuditTab = "overview" | "pages" | "competitors" | "recommendations";
export type FailureStage = "fetch" | "features" | "scoring" | "search" | "recommendations" | "pipeline";

export type FailureContext = {
  stage: FailureStage;
  code: string | null;
  message: string;
  details: Record<string, unknown> | null;
};

export type Recommendation = {
  code: string;
  priority: "high" | "medium" | "low";
  message: string;
};

export type ScoreFactor = {
  code: string;
  label: string;
  impact: number;
  detail: string;
};

export type ScoreBreakdown = {
  final_score: number;
  rule_score: number;
  ml_score: number;
  methodology: string;
  interaction_signals?: Record<string, number>;
  positives: ScoreFactor[];
  negatives: ScoreFactor[];
  factors: ScoreFactor[];
};

export type FetchStatus = "success" | "failed";
export type FetchMethod = "http" | "http_retry" | "browser" | null;

export type WarningMessage = string;

export type AuditCreatePayload = {
  query: string;
  target_url: string;
  top_n?: number;
};

export type AuditStatusResponse = {
  id: string;
  query: string;
  target_url: string;
  top_n: number;
  status: AuditStatus;
  created_at: string;
  updated_at: string | null;
  extracted_text: string | null;
  features: Record<string, number> | null;
  score: number | null;
  score_breakdown: ScoreBreakdown | null;
  competitor_results: CompetitorResult[] | null;
  comparison_summary: ComparisonSummary | null;
  recommendations: Recommendation[] | null;
  target_fetch_status: FetchStatus | null;
  target_fetch_method: FetchMethod;
  target_fetch_error_code: string | null;
  target_fetch_error_message: string | null;
  failure_context: FailureContext | null;
  warnings: WarningMessage[] | null;
  error_message: string | null;
};

export type AuditResultsResponse = {
  audit_id: string;
  status: AuditStatus;
  score: number | null;
  extracted_text: string | null;
  features: Record<string, number> | null;
  score_breakdown: ScoreBreakdown | null;
  competitor_results: CompetitorResult[] | null;
  comparison_summary: ComparisonSummary | null;
  target_fetch_status: FetchStatus | null;
  target_fetch_method: FetchMethod;
  target_fetch_error_code: string | null;
  target_fetch_error_message: string | null;
  failure_context: FailureContext | null;
  warnings: WarningMessage[] | null;
  error_message: string | null;
};

export type AuditRecommendationsResponse = {
  audit_id: string;
  status: AuditStatus;
  recommendations: Recommendation[];
  failure_context: FailureContext | null;
  error_message: string | null;
};

export type AuditSummary = {
  id: string;
  domain: string;
  query: string;
  score: number;
  status: AuditStatus;
  createdAt: string;
};

export type CompetitorScore = {
  name: string;
  score: number;
  isUser?: boolean;
};

export type CompetitorResult = {
  url: string;
  domain: string;
  title: string;
  snippet?: string;
  serp_rank?: number;
  serp_page?: number;
  fetch_status: FetchStatus;
  fetch_method: FetchMethod;
  fetch_error_code: string | null;
  fetch_error_message: string | null;
  score: number | null;
  features: Record<string, number> | null;
};

export type ComparisonSummary = {
  user_score: number;
  competitors_average_score: number;
  score_difference: number;
  competitors_count: number;
  competitors_found?: number;
  competitors_analyzed?: number;
  competitors_failed?: number;
};

export type PageRow = {
  id: string;
  url: string;
  pageType: string;
  score: number;
  textLength: number;
  seoTitle: string;
  queryMatch: number;
  fetchStatus: FetchStatus;
  fetchNote: string;
};
