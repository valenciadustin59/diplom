import { describe, expect, it } from "vitest";
import { buildRuntimeHealthModel } from "./runtimeHealth";
import type { RuntimeLivenessResponse, RuntimeMetricsResponse, RuntimeReadinessResponse } from "../types";

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

describe("runtime health model", () => {
  it("summarizes ready runtime and queue coverage", () => {
    const model = buildRuntimeHealthModel({
      live: createLiveness(),
      readiness: createReadiness(),
      metrics: createMetrics(),
    });

    expect(model.statusLabel).toBe("Рабочий стек готов");
    expect(model.metrics.find((metric) => metric.label === "Готовность")?.value).toBe("готов");
    expect(model.workerProfiles).toHaveLength(2);
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
});
