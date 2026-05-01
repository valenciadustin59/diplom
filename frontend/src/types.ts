export type AuditStatus = "queued" | "processing" | "completed" | "completed_with_warnings" | "failed";
export type AuditTab = "overview" | "report" | "timeline" | "pages" | "competitors" | "recommendations";
export type FailureStage = "fetch" | "heavy_analysis" | "features" | "scoring" | "search" | "recommendations" | "pipeline";

export type FailureContext = {
  stage: FailureStage;
  code: string | null;
  message: string;
  details: Record<string, unknown> | null;
};

export type RecommendationPriority = "high" | "medium" | "low";
export type RecommendationGroupKey = "technical_seo" | "commercial_trust" | "semantic_intent" | "competitor_gap";
export type RecommendationGroupStatus = "critical" | "attention" | "monitor" | "competitive" | "not_enough_data";
export type RecommendationTrend = "behind" | "ahead" | "aligned";

export type RecommendationEvidence = {
  label: string;
  value: string;
  benchmark: string | null;
  benchmark_label: string | null;
};

export type Recommendation = {
  code: string;
  priority: RecommendationPriority;
  impact: RecommendationPriority;
  title: string;
  message: string;
  expected_outcome: string;
  evidence: RecommendationEvidence[];
  related_metrics: string[];
};

export type RecommendationDeviation = {
  code: string;
  label: string;
  unit: string;
  current_value: number;
  benchmark_value: number;
  benchmark_label: string;
  delta: number;
  gap: number;
  trend: RecommendationTrend;
  priority: RecommendationPriority;
  summary: string;
};

export type RecommendationGroup = {
  key: RecommendationGroupKey;
  label: string;
  description: string;
  status: RecommendationGroupStatus;
  items: Recommendation[];
  deviations: RecommendationDeviation[];
  empty_state: string;
};

export type RecommendationsSummary = {
  total_recommendations: number;
  high_priority_count: number;
  medium_priority_count: number;
  low_priority_count: number;
  groups_with_issues: number;
  competitor_context: boolean;
  score_gap_vs_competitors: number | null;
};

export type RecommendationsBundle = {
  schema_version: string;
  summary: RecommendationsSummary;
  groups: RecommendationGroup[];
};

export type ScoreFactor = {
  code?: string;
  key?: string;
  label: string;
  impact: number;
  detail?: string;
  value?: number | string | null;
};

export type ScoreBreakdown = {
  final_score: number;
  rule_score: number;
  ml_score: number;
  methodology?: string;
  interaction_signals?: Record<string, number>;
  positives?: ScoreFactor[];
  negatives?: ScoreFactor[];
  factors?: ScoreFactor[];
  top_positive_factors?: ScoreFactor[];
  top_negative_factors?: ScoreFactor[];
  serp_relative_factors?: Array<Record<string, unknown>>;
  model_info?: Record<string, unknown>;
  weights?: Record<string, number>;
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
  feature_schema_version: string | null;
  heavy_analysis: Record<string, unknown> | null;
  query_intent: Record<string, unknown> | null;
  features: Record<string, number> | null;
  score: number | null;
  score_breakdown: ScoreBreakdown | null;
  competitor_results: CompetitorResult[] | null;
  comparison_summary: ComparisonSummary | null;
  recommendations: RecommendationsBundle | null;
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
  feature_schema_version: string | null;
  target_snapshot_summary: Record<string, unknown> | null;
  heavy_analysis: Record<string, unknown> | null;
  query_intent: Record<string, unknown> | null;
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

export type AuditTimelineEvent = {
  id: number;
  audit_id: string;
  processing_version: number | null;
  stage: string;
  event: string;
  duration_ms: number | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type AuditTimelineEventsResponse = {
  audit_id: string;
  processing_version: number | null;
  events: AuditTimelineEvent[];
};

export type AuditTimelineStageDiagnostics = {
  stage: string;
  dispatch_count: number;
  started_count: number;
  completed_count: number;
  failed_count: number;
  aborted_count: number;
  terminal_count: number;
  total_duration_ms: number | null;
  average_duration_ms: number | null;
  max_duration_ms: number | null;
  critical_path_mode: string;
  critical_path_duration_ms: number | null;
  first_event_at: string | null;
  last_event_at: string | null;
  latest_event: string | null;
};

export type AuditTimelineCriticalPathStage = {
  stage: string;
  contribution_duration_ms: number | null;
  mode: string;
  terminal_count: number;
};

export type AuditTimelineFanOut = {
  stage: string;
  dispatch_count: number;
  started_count: number;
  terminal_count: number;
  in_flight_count: number;
  total_duration_ms: number | null;
  average_duration_ms: number | null;
  max_duration_ms: number | null;
  critical_path_duration_ms: number | null;
};

export type AuditTimelineDiagnosticsResponse = {
  audit_id: string;
  processing_version: number | null;
  status: AuditStatus;
  event_count: number;
  dispatch_count: number;
  started_at: string | null;
  finished_at: string | null;
  total_duration_ms: number | null;
  terminal_stage: string | null;
  terminal_event: string | null;
  critical_path_duration_ms: number | null;
  critical_path_stages: AuditTimelineCriticalPathStage[];
  stage_breakdown: AuditTimelineStageDiagnostics[];
  fan_out: AuditTimelineFanOut | null;
};

export type AuditRecommendationsResponse = {
  audit_id: string;
  status: AuditStatus;
  recommendations: RecommendationsBundle | null;
  failure_context: FailureContext | null;
  error_message: string | null;
};

export type RuntimeComponentStatus = "ok" | "ready" | "not_ready" | "degraded" | "warning" | "error" | "skipped" | string;

export type RuntimeHealthCheck = {
  status: RuntimeComponentStatus;
  required?: boolean;
  error?: string;
  [key: string]: unknown;
};

export type RuntimeWorkerTopologyProfile = {
  name: string;
  workload_class: string;
  description: string;
  recommended_concurrency: number;
  queues: string[];
};

export type RuntimeWorkerTopologyContract = {
  profiles: RuntimeWorkerTopologyProfile[];
  expected_queues: string[];
};

export type RuntimeWorkerTopologyCoverage = {
  workload_class?: string;
  description?: string;
  recommended_concurrency?: number;
  queues: string[];
  covered_queues?: string[];
  missing_queues?: string[];
  workers: string[];
  worker_count: number;
};

export type RuntimeWorkerTopology = {
  status: RuntimeComponentStatus;
  profiles: Record<string, RuntimeWorkerTopologyCoverage>;
  worker_profiles?: Record<string, RuntimeHealthCheck>;
  invalid_workers?: string[];
  missing_profiles?: string[];
  profiles_with_missing_queues?: string[];
  missing_queues?: string[];
};

export type RuntimeWorkerSnapshot = {
  queues: string[];
  active_tasks: number;
  reserved_tasks: number;
  scheduled_tasks: number;
  pool_max_concurrency: number;
  pid?: number | null;
  profile_name?: string | null;
  profile_status?: RuntimeComponentStatus | null;
};

export type RuntimeQueuePressureStatus = "idle" | "busy" | "waiting" | "draining" | "backlogged" | "stuck" | string;

export type RuntimeQueueSnapshot = {
  depth: number;
  workers: string[];
  worker_count: number;
  estimated_concurrency: number;
  active_tasks: number;
  reserved_tasks: number;
  scheduled_tasks: number;
  inflight_tasks: number;
  available_capacity_estimate: number;
  pressure_status: RuntimeQueuePressureStatus;
  reasons: string[];
};

export type RuntimeLivenessResponse = {
  status: RuntimeComponentStatus;
  app_name: string;
  environment: string;
  checked_at: string;
};

export type RuntimeReadinessResponse = {
  status: RuntimeComponentStatus;
  app_name: string;
  environment: string;
  checked_at: string;
  checks: {
    database?: RuntimeHealthCheck;
    redis?: RuntimeHealthCheck;
    celery_workers?: RuntimeHealthCheck;
    serp?: RuntimeHealthCheck;
    [key: string]: RuntimeHealthCheck | undefined;
  };
  orchestration: {
    expected_queues: string[];
    broker_url: string;
    result_backend: string;
    worker_topology: RuntimeWorkerTopologyContract;
  };
};

export type RuntimeMetricsResponse = {
  status: RuntimeComponentStatus;
  app_name: string;
  environment: string;
  checked_at: string;
  orchestration: {
    expected_queues: string[];
    broker_url: string;
    result_backend: string;
    worker_topology: RuntimeWorkerTopologyContract;
  };
  database: RuntimeHealthCheck;
  broker: RuntimeHealthCheck & {
    queue_depths?: Record<string, number>;
    total_depth?: number;
  };
  workers: RuntimeHealthCheck & {
    online_count?: number;
    workers?: Record<string, RuntimeWorkerSnapshot>;
    active_tasks_total?: number;
    reserved_tasks_total?: number;
    scheduled_tasks_total?: number;
    expected_queues?: string[];
    missing_queues?: string[];
    queue_activity?: Record<string, Omit<RuntimeQueueSnapshot, "depth" | "pressure_status" | "reasons">>;
    topology?: RuntimeWorkerTopology;
    topology_contract?: RuntimeWorkerTopologyContract;
    warning?: string;
  };
  queue_pressure: RuntimeHealthCheck & {
    queues?: Record<string, RuntimeQueueSnapshot>;
    backlogged_queues?: string[];
    stuck_queues?: string[];
    thresholds?: Record<string, number>;
  };
  execution_detector: RuntimeHealthCheck & {
    alerts?: Array<Record<string, unknown>>;
    summary?: Record<string, number>;
    thresholds?: Record<string, number>;
  };
};

export type RuntimeModelStatusSection = Record<string, unknown> | null;

export type RuntimeModelStatusResponse = {
  status: RuntimeComponentStatus;
  checked_at: string;
  artifact_path?: string | null;
  artifact_sha1?: string | null;
  metadata_path?: string | null;
  metadata_sha1?: string | null;
  error?: string | null;
  model: RuntimeModelStatusSection;
  dataset: RuntimeModelStatusSection;
  metrics_summary: Record<string, unknown>;
  publish: Record<string, unknown>;
  rollback: Record<string, unknown>;
};

export type AuditSummary = {
  id: string;
  domain: string;
  query: string;
  targetUrl: string;
  topN: number;
  score: number;
  status: AuditStatus;
  createdAt: string;
  createdAtTimestamp: number | null;
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
