import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuditTabs } from "../components/AuditTabs";
import { AuditWorkspace, EmptyWorkspace } from "../components/AuditWorkspace";
import { ControlRail } from "../components/ControlRail";
import { RecommendationsPage } from "../pages/RecommendationsPage";
import { RuntimeStatusCompactCard, RuntimeStatusPage } from "../pages/RuntimeStatusPage";
import type {
  AuditResultsResponse,
  AuditStatusResponse,
  AuditTimelineDiagnosticsResponse,
  AuditTimelineEventsResponse,
  FailureContext,
  RecommendationsBundle,
} from "../types";
import { buildRuntimeHealthModel } from "./runtimeHealth";
import { resolveAuditFailureContext } from "./ui";

function createAudit(overrides: Partial<AuditStatusResponse> = {}): AuditStatusResponse {
  return {
    id: "audit-1",
    query: "seo audit",
    target_url: "https://example.com",
    top_n: 10,
    status: "queued",
    created_at: "2026-01-01T10:00:00",
    updated_at: null,
    extracted_text: null,
    feature_schema_version: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score: null,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    recommendations: null,
    target_fetch_status: null,
    target_fetch_method: null,
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
    ...overrides,
  };
}

function createResults(overrides: Partial<AuditResultsResponse> = {}): AuditResultsResponse {
  return {
    audit_id: "audit-1",
    status: "queued",
    score: null,
    extracted_text: null,
    feature_schema_version: null,
    target_snapshot_summary: null,
    heavy_analysis: null,
    query_intent: null,
    features: null,
    score_breakdown: null,
    competitor_results: null,
    comparison_summary: null,
    target_fetch_status: null,
    target_fetch_method: null,
    target_fetch_error_code: null,
    target_fetch_error_message: null,
    failure_context: null,
    warnings: null,
    error_message: null,
    ...overrides,
  };
}

function createTimelineDiagnostics(
  overrides: Partial<AuditTimelineDiagnosticsResponse> = {},
): AuditTimelineDiagnosticsResponse {
  return {
    audit_id: "audit-1",
    processing_version: 1,
    status: "completed",
    event_count: 18,
    dispatch_count: 9,
    started_at: "2026-01-01T10:00:01",
    finished_at: "2026-01-01T10:00:11",
    total_duration_ms: 10_000,
    terminal_stage: "finalize",
    terminal_event: "completed",
    critical_path_duration_ms: 8_500,
    critical_path_stages: [
      {
        stage: "heavy_analysis",
        contribution_duration_ms: 3_200,
        mode: "serial",
        terminal_count: 1,
      },
    ],
    stage_breakdown: [
      {
        stage: "heavy_analysis",
        dispatch_count: 1,
        started_count: 1,
        completed_count: 1,
        failed_count: 0,
        aborted_count: 0,
        terminal_count: 1,
        total_duration_ms: 3_200,
        average_duration_ms: 3_200,
        max_duration_ms: 3_200,
        critical_path_mode: "serial",
        critical_path_duration_ms: 3_200,
        first_event_at: "2026-01-01T10:00:02",
        last_event_at: "2026-01-01T10:00:05",
        latest_event: "completed",
      },
    ],
    fan_out: null,
    ...overrides,
  };
}

function createTimelineEvents(overrides: Partial<AuditTimelineEventsResponse> = {}): AuditTimelineEventsResponse {
  return {
    audit_id: "audit-1",
    processing_version: 1,
    events: [
      {
        id: 1,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "heavy_analysis",
        event: "dispatched",
        duration_ms: null,
        details: { queue: "audits.heavy_analysis" },
        created_at: "2026-01-01T10:00:02",
      },
      {
        id: 2,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "heavy_analysis",
        event: "completed",
        duration_ms: 3_200,
        details: { overall_score: 72, risk_level: "medium" },
        created_at: "2026-01-01T10:00:05",
      },
      {
        id: 3,
        audit_id: "audit-1",
        processing_version: 1,
        stage: "competitor_analysis",
        event: "dispatched",
        duration_ms: null,
        details: { queue: "audits.competitor_analysis", domain: "competitor.example" },
        created_at: "2026-01-01T10:00:06",
      },
    ],
    ...overrides,
  };
}

const runtimeTopology = {
  expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
  profiles: [
    {
      name: "pipeline",
      workload_class: "pipeline",
      description: "Pipeline orchestration.",
      recommended_concurrency: 1,
      queues: ["audits.pipeline"],
    },
    {
      name: "heavy_analysis",
      workload_class: "heavy_analysis",
      description: "Heavy analysis.",
      recommended_concurrency: 2,
      queues: ["audits.heavy_analysis"],
    },
  ],
};

const runtimeModelRegistry = {
  status: "ok",
  checked_at: "2026-05-02T00:00:00Z",
  artifact_family: "page_quality_model",
  active_artifact_sha1: "29c4b29455f795a535da94b2c6f36ef603d003eb",
  rollback_artifact_sha1: "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
  summary: {
    record_count: 2,
    current_count: 1,
    rollback_count: 1,
    archived_count: 0,
    warning_count: 0,
  },
  records: [
    {
      id: "current:dataset-v3-d37-20260501200434",
      role: "current",
      status: "ok",
      artifact_path: "artifacts/page_quality_model.pkl",
      artifact_sha1: "29c4b29455f795a535da94b2c6f36ef603d003eb",
      metadata_path: "artifacts/page_quality_model.metadata.json",
      metadata_sha1: "metadata-sha-current",
      model: {
        model_type: "CatBoostRegressor",
        model_schema_version: "v3",
        feature_count: 148,
        artifact_version: "dataset-v3-d37-20260501200434",
        published_at: "2026-05-01T20:04:34Z",
      },
      dataset: {
        dataset_version: "dataset-v3-d37",
        rows_count: 885,
        queries_count: 99,
      },
      metrics_summary: {
        top_3_hit_rate: 0.95,
        ndcg_at_10: 0.945929,
      },
      publish: {
        selected_candidate: "pointwise_catboost",
        publish_recommendation: "publish_candidate",
      },
      evidence: {
        publish_report_path: "artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json",
        publish_report_markdown_path: "artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.md",
        shadow_report_path: "artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json",
        smoke_summary_path: "../output/runtime-smoke/d38-smoke-summary.json",
      },
      warnings: [],
    },
    {
      id: "rollback:ru_commercial_dataset-20260421-primary-20260421174901",
      role: "rollback",
      status: "ok",
      artifact_path: "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl",
      artifact_sha1: "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
      metadata_path: "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json",
      metadata_sha1: "metadata-sha-rollback",
      model: {
        model_type: "RandomForestRegressor",
        model_schema_version: "v1",
        feature_count: 59,
        artifact_version: "ru_commercial_dataset-20260421-primary-20260421174901",
        published_at: "2026-04-21T17:49:01Z",
      },
      dataset: {
        dataset_version: "ru_commercial_dataset-20260421-primary",
        rows_count: 436,
        queries_count: 47,
      },
      metrics_summary: {
        top_3_hit_rate: 0.9,
        ndcg_at_10: 0.844962,
      },
      publish: {
        publish_action: "rollback_reference",
      },
      evidence: {
        publish_report_path: "artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json",
        rollback_source: "controlled_publish_rollback_reference",
      },
      warnings: [],
    },
  ],
  rollback_check: {
    status: "ok",
    dry_run_only: true,
    target_artifact_path: "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl",
    target_artifact_sha1: "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
    target_metadata_path:
      "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json",
    target_metadata_sha1: "metadata-sha-rollback",
    checklist: [
      {
        code: "dry_run_only",
        status: "info",
        label: "Rollback is read-only in the product UI.",
        detail: "The UI exposes evidence and checklist state only; actual rollback remains an engineering operation.",
      },
      {
        code: "rollback_metadata_present",
        status: "pass",
        label: "Rollback metadata sidecar exists.",
        detail: "The public metadata sidecar keeps dataset, schema and model evidence visible after rollback.",
        path: "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json",
      },
    ],
    warnings: [],
  },
  invariants: {
    dry_run_only: true,
    does_not_execute_rollback: true,
    does_not_mutate_model_artifacts: true,
  },
};

const runtimeWorkspaceProps = {
  runtimeHealth: buildRuntimeHealthModel({
    live: {
      status: "ok",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-01-01T10:00:00Z",
    },
    readiness: {
      status: "not_ready",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-01-01T10:00:00Z",
      checks: {
        database: { status: "ok", required: true, database_url: "sqlite:///app.db" },
        redis: { status: "ok", required: true, broker_url: "redis://localhost:6379/0" },
        serp: { status: "ok", required: true, provider: "searxng", base_url: "http://localhost:8080" },
        celery_workers: {
          status: "error",
          required: true,
          worker_count: 1,
          workers: ["site-audit.pipeline@test"],
          expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
          missing_queues: ["audits.heavy_analysis"],
        },
      },
      orchestration: {
        expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
        broker_url: "redis://localhost:6379/0",
        result_backend: "redis://localhost:6379/0",
        worker_topology: runtimeTopology,
      },
    },
    metrics: {
      status: "degraded",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-01-01T10:00:00Z",
      orchestration: {
        expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
        broker_url: "redis://localhost:6379/0",
        result_backend: "redis://localhost:6379/0",
        worker_topology: runtimeTopology,
      },
      database: { status: "ok" },
      broker: {
        status: "ok",
        queue_depths: { "audits.pipeline": 0, "audits.heavy_analysis": 2 },
        total_depth: 2,
      },
      workers: {
        status: "degraded",
        online_count: 1,
        workers: {
          "site-audit.pipeline@test": {
            queues: ["audits.pipeline"],
            active_tasks: 0,
            reserved_tasks: 0,
            scheduled_tasks: 0,
            pool_max_concurrency: 1,
            profile_name: "pipeline",
            profile_status: "ok",
          },
        },
        active_tasks_total: 0,
        reserved_tasks_total: 0,
        scheduled_tasks_total: 0,
        expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
        missing_queues: ["audits.heavy_analysis"],
        queue_activity: {},
        topology: {
          status: "error",
          profiles: {
            pipeline: {
              workload_class: "pipeline",
              description: "Pipeline orchestration.",
              recommended_concurrency: 1,
              queues: ["audits.pipeline"],
              covered_queues: ["audits.pipeline"],
              missing_queues: [],
              workers: ["site-audit.pipeline@test"],
              worker_count: 1,
            },
            heavy_analysis: {
              workload_class: "heavy_analysis",
              description: "Heavy analysis.",
              recommended_concurrency: 2,
              queues: ["audits.heavy_analysis"],
              covered_queues: [],
              missing_queues: ["audits.heavy_analysis"],
              workers: [],
              worker_count: 0,
            },
          },
          worker_profiles: {},
          invalid_workers: [],
          missing_profiles: ["heavy_analysis"],
          profiles_with_missing_queues: ["heavy_analysis"],
          missing_queues: ["audits.heavy_analysis"],
        },
        topology_contract: runtimeTopology,
      },
      queue_pressure: {
        status: "degraded",
        queues: {
          "audits.pipeline": {
            depth: 0,
            workers: ["site-audit.pipeline@test"],
            worker_count: 1,
            estimated_concurrency: 1,
            active_tasks: 0,
            reserved_tasks: 0,
            scheduled_tasks: 0,
            inflight_tasks: 0,
            available_capacity_estimate: 1,
            pressure_status: "idle",
            reasons: [],
          },
          "audits.heavy_analysis": {
            depth: 2,
            workers: [],
            worker_count: 0,
            estimated_concurrency: 0,
            active_tasks: 0,
            reserved_tasks: 0,
            scheduled_tasks: 0,
            inflight_tasks: 0,
            available_capacity_estimate: 0,
            pressure_status: "stuck",
            reasons: ["no_workers_serving_queue"],
          },
        },
        backlogged_queues: [],
        stuck_queues: ["audits.heavy_analysis"],
      },
      execution_detector: {
        status: "degraded",
        alerts: [
          {
            code: "queue_without_workers",
            severity: "error",
            queue: "audits.heavy_analysis",
            depth: 2,
          },
        ],
        summary: { alert_count: 1 },
      },
    },
    modelStatus: {
      status: "active",
      checked_at: "2026-05-01T20:05:00Z",
      artifact_path: "artifacts/page_quality_model.pkl",
      artifact_sha1: "29c4b29455f795a535da94b2c6f36ef603d003eb",
      metadata_path: "artifacts/page_quality_model.metadata.json",
      metadata_sha1: "metadata-sha",
      model: {
        model_type: "CatBoostRegressor",
        model_schema_version: "v3",
        feature_count: 148,
        artifact_version: "dataset-v3-d37-20260501200434",
        published_at: "2026-05-01T20:04:34Z",
      },
      dataset: {
        dataset_version: "dataset-v3-d37",
        rows_count: 885,
        queries_count: 99,
      },
      metrics_summary: {
        top_3_hit_rate: 0.95,
        ndcg_at_10: 0.945929,
        mae: 11.774165,
      },
      publish: {
        selected_candidate: "pointwise_catboost",
        publish_recommendation: "publish_candidate",
      },
      rollback: {
        available: true,
        model_sha1: "rollback-sha",
      },
    },
    modelRegistry: runtimeModelRegistry,
    modelMonitoring: {
      status: "ok",
      checked_at: "2026-05-02T00:00:00Z",
      window_days: 30,
      window_start: "2026-04-02T00:00:00Z",
      window_end: "2026-05-02T00:00:00Z",
      total_audits: 3,
      audits_with_model_info: 2,
      legacy_or_unknown_count: 1,
      status_counts: { completed: 2, completed_with_warnings: 1 },
      warning_count: 1,
      warning_message_count: 1,
      failure_count: 0,
      active_model: {
        artifact_version: "dataset-v3-d37-20260501200434",
        model_schema_version: "v3",
        dataset_version: "dataset-v3-d37",
      },
      score_distribution: {
        sample_size: 2,
        average: 76.2,
        min: 72.4,
        max: 80,
        p25: 74.3,
        p50: 76.2,
        p75: 78.1,
        low_score_count: 0,
        high_score_count: 1,
        low_score_threshold: 50,
        high_score_threshold: 80,
      },
      competitor_coverage: {
        sample_size: 2,
        total_found: 4,
        total_analyzed: 3,
        total_failed: 1,
        average_found: 2,
        average_analyzed: 1.5,
        average_failed: 0.5,
        coverage_ratio: 0.75,
      },
      model_usage: [
        {
          key: "dataset-v3-d37-20260501200434|v3|dataset-v3-d37|CatBoostRegressor|local_dataset",
          artifact_version: "dataset-v3-d37-20260501200434",
          model_schema_version: "v3",
          dataset_version: "dataset-v3-d37",
          model_type: "CatBoostRegressor",
          source: "local_dataset",
          artifact_family: "page_quality_model",
          feature_count: 148,
          is_active_model: true,
          audit_count: 2,
          status_counts: { completed: 1, completed_with_warnings: 1 },
          warning_count: 1,
          warning_message_count: 1,
          failure_count: 0,
          score_distribution: {
            sample_size: 2,
            average: 76.2,
            min: 72.4,
            max: 80,
            p25: 74.3,
            p50: 76.2,
            p75: 78.1,
            low_score_count: 0,
            high_score_count: 1,
            low_score_threshold: 50,
            high_score_threshold: 80,
          },
          competitor_coverage: {
            sample_size: 2,
            total_found: 4,
            total_analyzed: 3,
            total_failed: 1,
            average_found: 2,
            average_analyzed: 1.5,
            average_failed: 0.5,
            coverage_ratio: 0.75,
          },
          last_audit_at: "2026-05-01T20:00:00Z",
        },
      ],
    },
  }),
  loadingRuntime: false,
  runtimeError: null,
  onRefreshRuntime: () => undefined,
};

const emptyWorkspaceBaseProps = {
  recentAudits: [],
  activeAuditId: null,
  loadingRecent: false,
  recentError: null,
  submitting: false,
  submissionError: null,
  success: null,
  ...runtimeWorkspaceProps,
  onOpenRuntime: () => undefined,
  onRefreshRecent: () => undefined,
  onCreateAudit: () => Promise.resolve(true),
  onRepeatAudit: () => Promise.resolve(),
  onSelectAudit: () => undefined,
};

function createRecommendationsBundle(): RecommendationsBundle {
  return {
    schema_version: "recommendations-v2",
    summary: {
      total_recommendations: 1,
      high_priority_count: 1,
      medium_priority_count: 0,
      low_priority_count: 0,
      groups_with_issues: 1,
      competitor_context: true,
      score_gap_vs_competitors: -5.4,
    },
    groups: [
      {
        key: "technical_seo",
        label: "Technical SEO",
        description: "Technical description",
        status: "critical",
        items: [
          {
            code: "TECHNICAL_INDEXING_BLOCK",
            priority: "high",
            impact: "high",
            title: "Есть блокирующая проблема индексации",
            message: "Страница закрыта от индексации.",
            expected_outcome: "Исправление может заметно поднять итоговую оценку.",
            evidence: [
              {
                label: "Индексируемость страницы",
                value: "Нет",
                benchmark: "Да",
                benchmark_label: "Среднее по конкурентам",
              },
            ],
            related_metrics: ["page_indexable"],
          },
        ],
        deviations: [
          {
            code: "page_indexable",
            label: "Индексируемость страницы",
            unit: "binary",
            current_value: 0,
            benchmark_value: 1,
            benchmark_label: "Среднее по конкурентам",
            delta: -1,
            gap: 1,
            trend: "behind",
            priority: "high",
            summary: "Страница отстаёт от среднего по конкурентам.",
          },
        ],
        empty_state: "No issues",
      },
      {
        key: "commercial_trust",
        label: "Commercial and Trust",
        description: "Commercial description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "semantic_intent",
        label: "Semantic and Intent",
        description: "Semantic description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
      {
        key: "competitor_gap",
        label: "Competitor Gap",
        description: "Gap description",
        status: "competitive",
        items: [],
        deviations: [],
        empty_state: "No issues",
      },
    ],
  };
}

describe("resolveAuditFailureContext", () => {
  it("prefers explicit failure_context from results", () => {
    const context: FailureContext = {
      stage: "scoring",
      code: "runtime_error",
      message: "model calibration failed",
      details: null,
    };

    const audit = createAudit({
      status: "failed",
      error_message: "stale audit error",
    });
    const results = createResults({
      status: "failed",
      failure_context: context,
      error_message: "model calibration failed",
    });

    expect(resolveAuditFailureContext(audit, results)).toEqual(context);
  });

  it("builds fallback fetch context when structured failure_context is absent", () => {
    const audit = createAudit({
      status: "failed",
      target_fetch_status: "failed",
      target_fetch_method: "browser",
      target_fetch_error_code: "http_403",
      target_fetch_error_message: "HTTP 403",
      error_message: "HTTP 403",
    });

    expect(resolveAuditFailureContext(audit, null)).toEqual({
      stage: "fetch",
      code: "http_403",
      message: "HTTP 403",
      details: {
        fetch_method: "browser",
      },
    });
  });
});

describe("RecommendationsPage", () => {
  it("renders failure diagnostics for failed audit", () => {
    const context: FailureContext = {
      stage: "search",
      code: "runtime_error",
      message: "SERP provider unavailable",
      details: null,
    };

    const markup = renderToStaticMarkup(
      <RecommendationsPage
        recommendations={null}
        auditStatus="failed"
        loading={false}
        error={null}
        failureContext={context}
      />,
    );

    expect(markup).toContain("Рекомендации не сформированы");
    expect(markup).toContain("поиск и анализ конкурентов");
    expect(markup).toContain("SERP provider unavailable");
    expect(markup).toContain("runtime_error");
  });

  it("renders grouped recommendation sections", () => {
    const markup = renderToStaticMarkup(
      <RecommendationsPage
        recommendations={createRecommendationsBundle()}
        auditStatus="completed"
        loading={false}
        error={null}
        failureContext={null}
      />,
    );

    expect(markup).toContain("Техническое SEO");
    expect(markup).toContain("Коммерция и доверие");
    expect(markup).toContain("Есть блокирующая проблема индексации");
    expect(markup).toContain("План действий");
    expect(markup).toContain("Статус действия");
    expect(markup).toContain("Не начато");
    expect(markup).toContain("Закрыто 0/1");
    expect(markup).toContain("Среднее по конкурентам");
  });
});

describe("AuditWorkspace", () => {
  it("renders the root navigation entry for stack diagnostics", () => {
    const markup = renderToStaticMarkup(
      <ControlRail
        activeView="new"
        onOpenNew={() => undefined}
        onOpenHistory={() => undefined}
        onOpenRuntime={() => undefined}
      />,
    );

    expect(markup).toContain("Новый аудит");
    expect(markup).toContain("История");
    expect(markup).toContain("Стек");
  });

  it("renders current in-flight history records returned by the API", () => {
    const markup = renderToStaticMarkup(
      <EmptyWorkspace
        {...emptyWorkspaceBaseProps}
        mode="history"
        loadingRecent={true}
        recentAudits={[
          {
            id: "audit-stale",
            domain: "stale.example",
            query: "старый аудит в обработке",
            targetUrl: "https://stale.example/landing",
            topN: 10,
            score: 0,
            status: "processing",
            createdAt: "2 мая 2026 г., 10:00",
            createdAtTimestamp: Date.UTC(2026, 4, 2, 10, 0, 0),
            scoreBreakdown: null,
          },
        ]}
      />,
    );

    expect(markup).toContain("История аудитов");
    expect(markup).toContain("stale.example");
    expect(markup).toContain("старый аудит в обработке");
    expect(markup).toContain("Состояние рабочего стека");
    expect(markup).toContain("Открыть последний успешный");
    expect(markup).toContain("Повторить аудит");
    expect(markup).toContain("Скрыть локально");
    expect(markup).toContain("Скрытые локально");
    expect(markup).toContain("Архивные");
    expect(markup).toContain("Открыть стек");
    expect(markup).not.toContain("Загружаем историю аудитов");
  });

  it("renders score breakdowns that use top factor fields", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        {...runtimeWorkspaceProps}
        currentAudit={createAudit({
          status: "completed",
          score: 48.3,
          comparison_summary: {
            user_score: 48.3,
            competitors_average_score: 68.7,
            score_difference: -20.4,
            competitors_count: 2,
          },
        })}
        currentResults={createResults({
          status: "completed",
          score: 48.3,
          score_breakdown: {
            final_score: 48.3,
            rule_score: 23.8,
            ml_score: 68.4,
            model_info: {
              model_type: "CatBoostRegressor",
              model_schema_version: "v3",
              dataset_version: "dataset-v3-d37",
              artifact_version: "dataset-v3-d37-20260501200434",
              feature_count: 148,
              dataset_rows: 885,
              metrics_summary: {
                top_3_hit_rate: 0.95,
                ndcg_at_10: 0.945929,
                mae: 11.774165,
              },
            },
            top_positive_factors: [
              {
                key: "semantic_relevance",
                label: "Semantic relevance",
                impact: 5.6,
                value: 0.28,
              },
            ],
            top_negative_factors: [
              {
                key: "commercial_completeness",
                label: "Commercial completeness",
                impact: -3.5,
                value: 0,
              },
            ],
          },
        })}
        recommendations={null}
        timelineDiagnostics={null}
        timelineEvents={null}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 48.3,
          competitors_average_score: 68.7,
          score_difference: -20.4,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="overview"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Смысловое соответствие");
    expect(markup).toContain("Оффер и запись/заявка");
    expect(markup).toContain("Короткая расшифровка результата без технических деталей модели.");
    expect(markup).toContain("не складываются в финальную оценку");
    expect(markup).toContain("вес -3.5");
    expect(markup).not.toContain("Активная модель score");
    expect(markup).not.toContain("dataset-v3-d37");
    expect(markup).not.toContain("Значение фактора");
    expect(markup).not.toContain("Доверие к score");
  });

  it("renders score confidence warnings for incomplete audit data", () => {
    const longWarning =
      "Очень длинное предупреждение о неполном конкурентном покрытии, которое должно переноситься внутри карточки доверия к score без поломки узкой раскладки.";
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        {...runtimeWorkspaceProps}
        currentAudit={createAudit({
          status: "completed_with_warnings",
          score: 58,
          feature_schema_version: null,
          heavy_analysis: null,
          warnings: [longWarning],
          comparison_summary: {
            user_score: 58,
            competitors_average_score: 0,
            score_difference: 0,
            competitors_count: 3,
            competitors_found: 3,
            competitors_analyzed: 0,
            competitors_failed: 3,
          },
        })}
        currentResults={createResults({
          status: "completed_with_warnings",
          score: 58,
          feature_schema_version: null,
          heavy_analysis: null,
          target_fetch_status: "success",
          target_fetch_method: "browser",
          warnings: [longWarning],
          score_breakdown: {
            final_score: 58,
            rule_score: 55,
            ml_score: 61,
          },
          comparison_summary: {
            user_score: 58,
            competitors_average_score: 0,
            score_difference: 0,
            competitors_count: 3,
            competitors_found: 3,
            competitors_analyzed: 0,
            competitors_failed: 3,
          },
        })}
        recommendations={null}
        timelineDiagnostics={null}
        timelineEvents={null}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 58,
          competitors_average_score: 0,
          score_difference: 0,
          competitors_count: 3,
          competitors_found: 3,
          competitors_analyzed: 0,
          competitors_failed: 3,
        }}
        auditStatus="completed_with_warnings"
        loading={false}
        error={null}
        activeTab="overview"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Данные: частичные");
    expect(markup).toContain(longWarning);
    expect(markup).toContain("score-confidence__badge--warning");
    expect(markup).not.toContain("Доверие к score");
  });

  it("renders audit report dashboard with export actions and runtime evidence", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        {...runtimeWorkspaceProps}
        currentAudit={createAudit({
          status: "completed",
          score: 72.4,
          feature_schema_version: "v2",
          query_intent: { label: "commercial", confidence: 0.8 },
          heavy_analysis: { summary: "ok" },
          target_fetch_status: "success",
          target_fetch_method: "http",
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
          },
        })}
        currentResults={createResults({
          status: "completed",
          score: 72.4,
          feature_schema_version: "v2",
          target_snapshot_summary: {
            status_code: 200,
            fetch_method: "http",
          },
          target_fetch_status: "success",
          target_fetch_method: "http",
          heavy_analysis: { summary: "ok" },
          query_intent: { label: "commercial", confidence: 0.8 },
          features: {
            technical_seo_score: 0.8,
            commercial_trust_score: 0.6,
            semantic_similarity: 0.72,
            intent_alignment_score: 0.68,
          },
          score_breakdown: {
            final_score: 72.4,
            rule_score: 70,
            ml_score: 74,
            model_info: {
              model_type: "CatBoostRegressor",
              model_schema_version: "v3",
              dataset_version: "dataset-v3-d37",
              artifact_version: "dataset-v3-d37-20260501200434",
              feature_count: 148,
              dataset_rows: 885,
              metrics_summary: {
                top_3_hit_rate: 0.95,
                ndcg_at_10: 0.945929,
                mae: 11.774165,
              },
            },
          },
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
            competitors_found: 2,
            competitors_analyzed: 2,
            competitors_failed: 0,
          },
          competitor_results: [
            {
              url: "https://competitor.example/",
              domain: "competitor.example",
              title: "Competitor",
              fetch_status: "success",
              fetch_method: "http",
              fetch_error_code: null,
              fetch_error_message: null,
              score: 78.2,
              features: null,
            },
          ],
        })}
        recommendations={createRecommendationsBundle()}
        timelineDiagnostics={createTimelineDiagnostics()}
        timelineEvents={createTimelineEvents()}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 72.4,
          competitors_average_score: 78.2,
          score_difference: -5.8,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="report"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Отчёт аудита");
    expect(markup).toContain("Скачать Markdown");
    expect(markup).not.toContain("Доверие к score");
    expect(markup).toContain("SEO-сигналы");
    expect(markup).not.toContain("Статус модели");
    expect(markup).not.toContain("CatBoostRegressor");
    expect(markup).not.toContain("dataset-v3-d37");
    expect(markup).not.toContain("Top-3");
    expect(markup).toContain("report-table--recommendations");
    expect(markup).toContain("Доказательство распределённого выполнения");
    expect(markup).toContain("Углублённый анализ");
  });

  it("renders audit execution timeline with stages, queues, fan-out and critical path", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        {...runtimeWorkspaceProps}
        currentAudit={createAudit({
          status: "completed",
          score: 72.4,
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
          },
        })}
        currentResults={createResults({
          status: "completed",
          score: 72.4,
        })}
        recommendations={createRecommendationsBundle()}
        timelineDiagnostics={createTimelineDiagnostics({
          fan_out: {
            stage: "competitor_analysis",
            dispatch_count: 1,
            started_count: 1,
            terminal_count: 0,
            in_flight_count: 1,
            total_duration_ms: null,
            average_duration_ms: null,
            max_duration_ms: null,
            critical_path_duration_ms: null,
          },
        })}
        timelineEvents={createTimelineEvents()}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 72.4,
          competitors_average_score: 78.2,
          score_difference: -5.8,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="timeline"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("Таймлайн выполнения аудита");
    expect(markup).toContain("События таймлайна");
    expect(markup).toContain("Отправлено в очереди");
    expect(markup).toContain("Критический путь");
    expect(markup).toContain("Жизненный цикл этапов");
    expect(markup).toContain("Вклад в критический путь");
    expect(markup).toContain("Параллельные ветки");
    expect(markup).toContain("Диагностика этапов");
    expect(markup).toContain("Поток событий");
    expect(markup).toContain("Сырые события из серверного журнала");
    expect(markup).toContain("Углублённый анализ");
    expect(markup).toContain("audits.heavy_analysis");
    expect(markup).not.toContain(["Run", "time contributor"].join(""));
    expect(markup).not.toContain("Fan-out stages");
    expect(markup).not.toContain("fan-out");
    expect(markup).not.toContain("Celery pipeline");
    expect(markup).not.toContain("Pipeline остановился");
    expect(markup).not.toContain(["back", "end-журнала"].join(""));
  });

  it("keeps stack diagnostics out of the audit tabs", () => {
    const markup = renderToStaticMarkup(
      <AuditTabs activeTab="overview" onChange={() => undefined} />,
    );

    expect(markup).toContain("Обзор");
    expect(markup).toContain("Таймлайн");
    expect(markup).not.toContain("Стек");
  });

  it("renders launch stack readiness compact card before creating an audit", () => {
    const markup = renderToStaticMarkup(
      <RuntimeStatusCompactCard
        model={runtimeWorkspaceProps.runtimeHealth}
        loading={false}
        error={null}
        onRefresh={() => undefined}
        onOpenFull={() => undefined}
      />,
    );

    expect(markup).toContain("Готовность рабочего стека");
    expect(markup).toContain("Рабочий стек не готов");
    expect(markup).toContain("audits.heavy_analysis");
    expect(markup).not.toContain("Активная модель");
    expect(markup).not.toContain("Оценка качества страницы · v3");
    expect(markup).not.toContain("dataset-v3-d37");
    expect(markup).toContain("Проверено:");
    expect(markup).toContain("Открыть стек");
  });

  it("does not render model monitoring noise in the stack UI", () => {
    const markup = renderToStaticMarkup(
      <RuntimeStatusPage
        model={runtimeWorkspaceProps.runtimeHealth}
        loading={false}
        error={null}
        onRefresh={() => undefined}
      />,
    );

    expect(markup).not.toContain("Мониторинг расчёта score");
    expect(markup).not.toContain("Данные score в 2 из 3 аудитов");
    expect(markup).not.toContain("Score активной модели");
    expect(markup).not.toContain("Покрытие конкурентов");
    expect(markup).not.toContain("RandomForestRegressor");
    expect(markup).not.toContain("dataset-v3-d37-20260501200434");
  });

  it("renders model principles instead of rollback registry history", () => {
    const markup = renderToStaticMarkup(
      <RuntimeStatusPage
        model={runtimeWorkspaceProps.runtimeHealth}
        loading={false}
        error={null}
        onRefresh={() => undefined}
      />,
    );

    expect(markup).toContain("Как формируется оценка");
    expect(markup).toContain("Коротко о сигналах");
    expect(markup).toContain("Понимает запрос");
    expect(markup).toContain("Проверяет качество страницы");
    expect(markup).toContain("Добавляет контекст выдачи");
    expect(markup).toContain("Даёт score и рекомендации");
    expect(markup).not.toContain("Признаки");
    expect(markup).not.toContain("148 признаков");
    expect(markup).not.toContain("Top-3");
    expect(markup).not.toContain("Данные обучения");
    expect(markup).not.toContain("dataset-v3-d37");
    expect(markup).not.toContain("Model registry и rollback evidence");
    expect(markup).not.toContain("RandomForestRegressor");
    expect(markup).not.toContain("Выполнить rollback");
  });

  it("keeps model monitoring empty state hidden from the stack UI", () => {
    const runtimeHealth = runtimeWorkspaceProps.runtimeHealth;
    const markup = renderToStaticMarkup(
      <RuntimeStatusPage
        model={{
          ...runtimeHealth,
          modelMonitoring: runtimeHealth.modelMonitoring
            ? {
                ...runtimeHealth.modelMonitoring,
                status: "empty",
                statusLabel: "Нет runtime-данных",
                tone: "muted",
                empty: true,
                shortLabel: "Нет новых данных по score",
                detail: "За выбранное окно нет завершённых аудит-записей с новыми сведениями о расчёте.",
                usageRows: [],
              }
            : null,
        }}
        loading={false}
        error={null}
        onRefresh={() => undefined}
      />,
    );

    expect(markup).not.toContain("Нет новых данных по score");
    expect(markup).not.toContain("Нет завершённых recent-аудитов с новыми сведениями о расчёте score");
    expect(markup).not.toContain("старые записи уже учтены отдельно");
  });

  it("renders report recommendations from the stored audit data when endpoint data is absent", () => {
    const markup = renderToStaticMarkup(
      <AuditWorkspace
        {...runtimeWorkspaceProps}
        currentAudit={createAudit({
          status: "completed",
          score: 72.4,
          recommendations: createRecommendationsBundle(),
          comparison_summary: {
            user_score: 72.4,
            competitors_average_score: 78.2,
            score_difference: -5.8,
            competitors_count: 2,
          },
        })}
        currentResults={null}
        recommendations={null}
        timelineDiagnostics={null}
        timelineEvents={null}
        pageRows={[]}
        competitorScores={[]}
        comparisonSummary={{
          user_score: 72.4,
          competitors_average_score: 78.2,
          score_difference: -5.8,
          competitors_count: 2,
        }}
        auditStatus="completed"
        loading={false}
        error={null}
        activeTab="report"
        onTabChange={() => undefined}
      />,
    );

    expect(markup).toContain("План рекомендаций");
    expect(markup).toContain("Есть блокирующая проблема индексации");
    expect(markup).toContain("1");
  });
});
