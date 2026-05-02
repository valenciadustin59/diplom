import { describe, expect, it } from "vitest";
import { runtimeApi } from "../api/api";
import { loadRuntimeHealthSnapshot } from "./useRuntimeHealth";

describe("loadRuntimeHealthSnapshot", () => {
  it("loads launch-critical runtime health without registry or monitoring polling", async () => {
    const originalApi = { ...runtimeApi };
    let registryCalled = false;
    let monitoringCalled = false;
    runtimeApi.getLiveness = async () => ({
      status: "ok",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-05-02T00:00:00Z",
    });
    runtimeApi.getReadiness = async () => ({
      status: "ready",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-05-02T00:00:00Z",
      checks: {
        database: { status: "ok", required: true },
        redis: { status: "ok", required: true },
        serp: { status: "ok", required: true },
        celery_workers: { status: "ok", required: true, worker_count: 1, missing_queues: [] },
      },
      orchestration: {
        expected_queues: [],
        broker_url: "redis://localhost:6379/0",
        result_backend: "redis://localhost:6379/0",
        worker_topology: { profiles: [], expected_queues: [] },
      },
    });
    runtimeApi.getMetrics = async () => ({
      status: "ok",
      app_name: "site-audit",
      environment: "local",
      checked_at: "2026-05-02T00:00:00Z",
      orchestration: {
        expected_queues: [],
        broker_url: "redis://localhost:6379/0",
        result_backend: "redis://localhost:6379/0",
        worker_topology: { profiles: [], expected_queues: [] },
      },
      database: { status: "ok" },
      broker: { status: "ok", queue_depths: {}, total_depth: 0 },
      workers: { status: "ok", online_count: 1, workers: {}, missing_queues: [], queue_activity: {} },
      queue_pressure: { status: "ok", queues: {}, backlogged_queues: [], stuck_queues: [] },
      execution_detector: { status: "ok", alerts: [], summary: { alert_count: 0 } },
    });
    runtimeApi.getModelStatus = async () => ({
      status: "active",
      checked_at: "2026-05-02T00:00:00Z",
      artifact_path: "artifacts/page_quality_model.pkl",
      artifact_sha1: "29c4b29455f795a535da94b2c6f36ef603d003eb",
      metadata_path: "artifacts/page_quality_model.metadata.json",
      metadata_sha1: "metadata-sha",
      model: {
        model_type: "CatBoostRegressor",
        model_schema_version: "v3",
        feature_count: 148,
        artifact_version: "dataset-v3-d37-20260501200434",
      },
      dataset: {
        dataset_version: "dataset-v3-d37",
        rows_count: 885,
        queries_count: 99,
      },
      metrics_summary: {},
      publish: {},
      rollback: { available: true },
    });
    runtimeApi.getModelRegistry = async () => {
      registryCalled = true;
      throw new Error("registry unavailable");
    };
    runtimeApi.getModelMonitoring = async () => {
      monitoringCalled = true;
      throw new Error("monitoring unavailable");
    };

    try {
      const snapshot = await loadRuntimeHealthSnapshot();

      expect(snapshot.runtimeHealth?.modelStatus?.shortLabel).toBe("Оценка качества страницы · v3");
      expect(snapshot.runtimeHealth?.modelRegistry).toBeNull();
      expect(snapshot.runtimeHealth?.modelMonitoring).toBeNull();
      expect(snapshot.runtimeError).toBeNull();
      expect(registryCalled).toBe(false);
      expect(monitoringCalled).toBe(false);
    } finally {
      Object.assign(runtimeApi, originalApi);
    }
  });
});
