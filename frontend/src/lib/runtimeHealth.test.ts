import { describe, expect, it } from "vitest";
import { buildRuntimeHealthModel } from "./runtimeHealth";
import type {
  RuntimeLivenessResponse,
  RuntimeMetricsResponse,
  RuntimeModelRegistryResponse,
  RuntimeModelMonitoringResponse,
  RuntimeModelStatusResponse,
  RuntimeReadinessResponse,
} from "../types";

const workerTopology = {
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

function createLiveness(): RuntimeLivenessResponse {
  return {
    status: "ok",
    app_name: "site-audit",
    environment: "local",
    checked_at: "2026-01-01T10:00:00Z",
  };
}

function createReadiness(overrides: Partial<RuntimeReadinessResponse> = {}): RuntimeReadinessResponse {
  return {
    status: "ready",
    app_name: "site-audit",
    environment: "local",
    checked_at: "2026-01-01T10:00:00Z",
    checks: {
      database: { status: "ok", required: true },
      redis: { status: "ok", required: true },
      serp: { status: "ok", required: true },
      celery_workers: { status: "ok", required: true, worker_count: 2, missing_queues: [] },
    },
    orchestration: {
      expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
      broker_url: "redis://localhost:6379/0",
      result_backend: "redis://localhost:6379/0",
      worker_topology: workerTopology,
    },
    ...overrides,
  };
}

function createMetrics(overrides: Partial<RuntimeMetricsResponse> = {}): RuntimeMetricsResponse {
  return {
    status: "ok",
    app_name: "site-audit",
    environment: "local",
    checked_at: "2026-01-01T10:00:00Z",
    orchestration: {
      expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
      broker_url: "redis://localhost:6379/0",
      result_backend: "redis://localhost:6379/0",
      worker_topology: workerTopology,
    },
    database: { status: "ok" },
    broker: {
      status: "ok",
      queue_depths: { "audits.pipeline": 0, "audits.heavy_analysis": 0 },
      total_depth: 0,
    },
    workers: {
      status: "ok",
      online_count: 2,
      workers: {},
      active_tasks_total: 0,
      reserved_tasks_total: 0,
      scheduled_tasks_total: 0,
      expected_queues: ["audits.pipeline", "audits.heavy_analysis"],
      missing_queues: [],
      queue_activity: {},
      topology: {
        status: "ok",
        profiles: {
          pipeline: {
            queues: ["audits.pipeline"],
            covered_queues: ["audits.pipeline"],
            missing_queues: [],
            workers: ["pipeline@test"],
            worker_count: 1,
          },
          heavy_analysis: {
            queues: ["audits.heavy_analysis"],
            covered_queues: ["audits.heavy_analysis"],
            missing_queues: [],
            workers: ["heavy@test"],
            worker_count: 1,
          },
        },
        missing_queues: [],
      },
      topology_contract: workerTopology,
    },
    queue_pressure: {
      status: "ok",
      queues: {
        "audits.pipeline": {
          depth: 0,
          workers: ["pipeline@test"],
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
          depth: 0,
          workers: ["heavy@test"],
          worker_count: 1,
          estimated_concurrency: 2,
          active_tasks: 0,
          reserved_tasks: 0,
          scheduled_tasks: 0,
          inflight_tasks: 0,
          available_capacity_estimate: 2,
          pressure_status: "idle",
          reasons: [],
        },
      },
      backlogged_queues: [],
      stuck_queues: [],
    },
    execution_detector: { status: "ok", alerts: [], summary: { alert_count: 0 } },
    ...overrides,
  };
}

function createModelStatus(overrides: Partial<RuntimeModelStatusResponse> = {}): RuntimeModelStatusResponse {
  return {
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
    ...overrides,
  };
}

function createModelRegistry(overrides: Partial<RuntimeModelRegistryResponse> = {}): RuntimeModelRegistryResponse {
  return {
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
          mae: 11.774165,
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
        expected_artifact_sha1: "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
        artifact_sha1_matches: true,
        metadata_path:
          "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json",
        metadata_sha1: "metadata-sha-rollback",
        expected_metadata_sha1: "metadata-sha-rollback",
        metadata_sha1_matches: true,
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
      target_artifact_path:
        "artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl",
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
    ...overrides,
  };
}

function createModelMonitoring(overrides: Partial<RuntimeModelMonitoringResponse> = {}): RuntimeModelMonitoringResponse {
  return {
    status: "warning",
    checked_at: "2026-05-02T00:00:00Z",
    window_days: 30,
    window_start: "2026-04-02T00:00:00Z",
    window_end: "2026-05-02T00:00:00Z",
    total_audits: 4,
    audits_with_model_info: 3,
    legacy_or_unknown_count: 1,
    status_counts: { completed: 2, completed_with_warnings: 1, failed: 1 },
    warning_count: 1,
    warning_message_count: 1,
    failure_count: 1,
    active_model: {
      artifact_version: "dataset-v3-d37-20260501200434",
      model_schema_version: "v3",
      dataset_version: "dataset-v3-d37",
    },
    score_distribution: {
      sample_size: 3,
      average: 66.6667,
      min: 40,
      max: 90,
      p25: 55,
      p50: 70,
      p75: 80,
      low_score_count: 1,
      high_score_count: 1,
      low_score_threshold: 50,
      high_score_threshold: 80,
    },
    competitor_coverage: {
      sample_size: 3,
      total_found: 6,
      total_analyzed: 5,
      total_failed: 1,
      average_found: 2,
      average_analyzed: 1.6667,
      average_failed: 0.3333,
      coverage_ratio: 0.8333,
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
        audit_count: 3,
        status_counts: { completed: 2, completed_with_warnings: 1 },
        warning_count: 1,
        warning_message_count: 1,
        failure_count: 0,
        score_distribution: {
          sample_size: 3,
          average: 66.6667,
          min: 40,
          max: 90,
          p25: 55,
          p50: 70,
          p75: 80,
          low_score_count: 1,
          high_score_count: 1,
          low_score_threshold: 50,
          high_score_threshold: 80,
        },
        competitor_coverage: {
          sample_size: 3,
          total_found: 6,
          total_analyzed: 5,
          total_failed: 1,
          average_found: 2,
          average_analyzed: 1.6667,
          average_failed: 0.3333,
          coverage_ratio: 0.8333,
        },
        last_audit_at: "2026-05-01T20:00:00Z",
      },
    ],
    ...overrides,
  };
}

describe("runtime health model", () => {
  it("summarizes ready runtime and queue coverage", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
      modelStatus: createModelStatus(),
    });

    expect(model.statusLabel).toBe("Рабочий стек готов");
    expect(model.metrics.find((metric) => metric.label === "Готовность")?.value).toBe("готов");
    expect(model.workerProfiles).toHaveLength(2);
    expect(model.modelStatus?.statusLabel).toBe("Расчёт score доступен");
    expect(model.modelStatus?.shortLabel).toBe("Оценка качества страницы · v3");
    expect(model.modelStatus?.datasetLabel).toContain("dataset-v3-d37");
    expect(model.modelStatus?.metricRows).toHaveLength(0);
    expect(model.queues.find((queue) => queue.name === "audits.heavy_analysis")?.pressureLabel).toBe("простаивает");
    expect(model.issues[0].title).toBe("Рабочий стек готов к новым аудитам");
  });

  it("shows the lightweight SearXNG health endpoint in component details", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness({
        checks: {
          database: { status: "ok", required: true },
          redis: { status: "ok", required: true },
          serp: {
            status: "ok",
            required: true,
            provider: "searxng",
            base_url: "http://127.0.0.1:8888",
            health_endpoint: "http://127.0.0.1:8888/healthz",
          },
          celery_workers: { status: "ok", required: true, worker_count: 2, missing_queues: [] },
        },
      }),
      metrics: createMetrics(),
    });

    expect(model.components.find((component) => component.id === "serp")?.detail).toBe(
      "http://127.0.0.1:8888; проверка готовности: http://127.0.0.1:8888/healthz.",
    );
  });

  it("does not treat historical stuck audit rows as a current stack failure", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics({
        status: "degraded",
        execution_detector: {
          status: "degraded",
          alerts: [{ code: "stuck_processing_audits", severity: "error", count: 3 }],
          summary: { alert_count: 1, stuck_processing_count: 3 },
        },
      }),
    });

    expect(model.statusLabel).toBe("Рабочий стек готов");
    expect(model.statusTone).toBe("ok");
    expect(model.statusDetail).toContain("можно запускать новый аудит");
    expect(model.issues.map((issue) => issue.title)).not.toContain("Есть зависшие аудиты");
    expect(model.issues[0].title).toBe("Рабочий стек готов к новым аудитам");
  });

  it("surfaces missing workers and stuck queues with recovery guidance", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness({
        status: "not_ready",
        checks: {
          database: { status: "ok", required: true },
          redis: { status: "ok", required: true },
          serp: { status: "ok", required: true },
          celery_workers: {
            status: "error",
            required: true,
            worker_count: 1,
            missing_queues: ["audits.heavy_analysis"],
          },
        },
      }),
      metrics: createMetrics({
        status: "degraded",
        workers: {
          ...createMetrics().workers,
          status: "degraded",
          online_count: 1,
          missing_queues: ["audits.heavy_analysis"],
          topology: {
            status: "error",
            profiles: {
              pipeline: {
                queues: ["audits.pipeline"],
                covered_queues: ["audits.pipeline"],
                missing_queues: [],
                workers: ["pipeline@test"],
                worker_count: 1,
              },
              heavy_analysis: {
                queues: ["audits.heavy_analysis"],
                covered_queues: [],
                missing_queues: ["audits.heavy_analysis"],
                workers: [],
                worker_count: 0,
              },
            },
            missing_profiles: ["heavy_analysis"],
            profiles_with_missing_queues: ["heavy_analysis"],
            missing_queues: ["audits.heavy_analysis"],
          },
        },
        queue_pressure: {
          ...createMetrics().queue_pressure,
          status: "degraded",
          queues: {
            ...createMetrics().queue_pressure.queues,
            "audits.heavy_analysis": {
              depth: 3,
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
          stuck_queues: ["audits.heavy_analysis"],
        },
        execution_detector: {
          status: "degraded",
          alerts: [{ code: "queue_without_workers", severity: "error", queue: "audits.heavy_analysis", depth: 3 }],
          summary: { alert_count: 1 },
        },
      }),
    });

    expect(model.ready).toBe(false);
    expect(model.statusTone).toBe("error");
    expect(model.workerProfiles.find((profile) => profile.name === "heavy_analysis")?.statusLabel).toBe("требуется воркер");
    expect(model.queues.find((queue) => queue.name === "audits.heavy_analysis")?.pressureLabel).toBe("без воркеров");
    expect(model.issues.map((issue) => issue.title).join(" ")).toContain("Очередь audits.heavy_analysis без воркеров");
  });

  it("summarizes active model monitoring usage and legacy audit counts", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
      modelStatus: createModelStatus(),
      modelMonitoring: createModelMonitoring(),
    });

    expect(model.modelMonitoring?.statusLabel).toBe("Есть предупреждения");
    expect(model.modelMonitoring?.shortLabel).toBe("Данные score в 3 из 4 аудитов");
    expect(model.modelMonitoring?.legacyLabel).toBe("1 старых записей");
    expect(model.modelMonitoring?.summaryMetrics.find((metric) => metric.label === "Предупреждения/ошибки")?.value).toBe("1/1");
    expect(model.modelMonitoring?.scoreMetrics.find((metric) => metric.label === "Score p50")?.value).toBe("70");
    expect(model.modelMonitoring?.competitorMetrics.find((metric) => metric.label === "Coverage")?.value).toBe("83%");
    expect(model.modelMonitoring?.usageRows[0].modelLabel).toBe("CatBoostRegressor · v3");
    expect(model.modelMonitoring?.usageRows[0].competitorCoverageLabel).toContain("5/6");
  });

  it("summarizes model registry records and rollback dry-run evidence", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
      modelStatus: createModelStatus(),
      modelRegistry: createModelRegistry(),
    });

    expect(model.modelRegistry?.statusLabel).toBe("готово");
    expect(model.modelRegistry?.shortLabel).toContain("dataset-v3-d37-20260501200434");
    expect(model.modelRegistry?.shortLabel).toContain("rollback");
    expect(model.modelRegistry?.summaryMetrics.find((metric) => metric.label === "Records")?.value).toBe("2");
    expect(model.modelRegistry?.summaryMetrics.find((metric) => metric.label === "Rollback check")?.value).toBe("готово");
    expect(model.modelRegistry?.records[0].modelLabel).toContain("CatBoostRegressor · v3");
    expect(model.modelRegistry?.records[0].evidenceLabels.join(" ")).toContain("d38-smoke-summary.json");
    expect(model.modelRegistry?.records[1].roleLabel).toBe("rollback");
    expect(model.modelRegistry?.records[1].modelLabel).toContain("RandomForestRegressor · v1");
    expect(model.modelRegistry?.rollbackCheck?.dryRunLabel).toContain("UI не выполняет rollback");
  });

  it("keeps model registry warnings visible when rollback metadata is incomplete", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
      modelStatus: createModelStatus(),
      modelRegistry: createModelRegistry({
        status: "warning",
        summary: {
          record_count: 2,
          current_count: 1,
          rollback_count: 1,
          archived_count: 0,
          warning_count: 2,
        },
        records: createModelRegistry().records.map((record) =>
          record.role === "rollback"
            ? {
                ...record,
                status: "warning",
                metadata_sha1: null,
                warnings: [
                  {
                    code: "metadata_missing",
                    message: "Public metadata sidecar is missing.",
                    path: "artifacts/versions/missing.metadata.json",
                  },
                ],
              }
            : record,
        ),
        rollback_check: {
          ...createModelRegistry().rollback_check,
          status: "warning",
          warnings: [
            {
              code: "rollback_metadata_present",
              status: "warn",
              label: "Rollback metadata sidecar exists.",
              detail: "The public metadata sidecar keeps dataset, schema and model evidence visible after rollback.",
              path: "artifacts/versions/missing.metadata.json",
            },
          ],
        },
      }),
    });

    expect(model.modelRegistry?.tone).toBe("warning");
    expect(model.modelRegistry?.detail).toContain("предупреждения");
    expect(model.modelRegistry?.records[1].warningLabels.join(" ")).toContain("Public metadata sidecar is missing.");
    expect(model.modelRegistry?.rollbackCheck?.statusLabel).toBe("требует проверки");
  });

  it("keeps model monitoring empty state explicit", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
      modelStatus: createModelStatus(),
      modelMonitoring: createModelMonitoring({
        status: "empty",
        total_audits: 2,
        audits_with_model_info: 0,
        legacy_or_unknown_count: 2,
        status_counts: { completed: 2 },
        warning_count: 0,
        warning_message_count: 0,
        failure_count: 0,
        score_distribution: {
          sample_size: 0,
          average: null,
          min: null,
          max: null,
          p25: null,
          p50: null,
          p75: null,
          low_score_count: 0,
          high_score_count: 0,
          low_score_threshold: 50,
          high_score_threshold: 80,
        },
        competitor_coverage: {
          sample_size: 0,
          total_found: 0,
          total_analyzed: 0,
          total_failed: 0,
          average_found: null,
          average_analyzed: null,
          average_failed: null,
          coverage_ratio: null,
        },
        model_usage: [],
      }),
    });

    expect(model.modelMonitoring?.empty).toBe(true);
    expect(model.modelMonitoring?.statusLabel).toBe("Нет runtime-данных");
    expect(model.modelMonitoring?.shortLabel).toBe("Нет новых данных по score");
    expect(model.modelMonitoring?.detail).toContain("старые строки учтены отдельно");
  });
});
