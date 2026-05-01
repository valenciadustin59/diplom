import { useCallback, useEffect, useState } from "react";
import { ApiError, runtimeApi } from "../api/api";
import { buildRuntimeHealthModel, type RuntimeHealthModel } from "../lib/runtimeHealth";
import type {
  RuntimeLivenessResponse,
  RuntimeMetricsResponse,
  RuntimeModelMonitoringResponse,
  RuntimeModelStatusResponse,
  RuntimeReadinessResponse,
} from "../types";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Не удалось загрузить диагностику рабочего стека";
}

function getSettledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

function getRejectedMessages(results: PromiseSettledResult<unknown>[]): string[] {
  return results.flatMap((result) => (result.status === "rejected" ? [getErrorMessage(result.reason)] : []));
}

export function useRuntimeHealth() {
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealthModel | null>(null);
  const [loadingRuntime, setLoadingRuntime] = useState(true);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  const loadRuntimeHealth = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoadingRuntime(true);
    }

    const results = await Promise.allSettled([
      runtimeApi.getLiveness(),
      runtimeApi.getReadiness(),
      runtimeApi.getMetrics(),
      runtimeApi.getModelStatus(),
      runtimeApi.getModelMonitoring(),
    ] as const);
    const [liveResult, readinessResult, metricsResult, modelStatusResult, modelMonitoringResult] = results;
    const live = getSettledValue<RuntimeLivenessResponse>(liveResult);
    const readiness = getSettledValue<RuntimeReadinessResponse>(readinessResult);
    const metrics = getSettledValue<RuntimeMetricsResponse>(metricsResult);
    const modelStatus = getSettledValue<RuntimeModelStatusResponse>(modelStatusResult);
    const modelMonitoring = getSettledValue<RuntimeModelMonitoringResponse>(modelMonitoringResult);

    if (!live && !readiness && !metrics && !modelStatus && !modelMonitoring) {
      setRuntimeError(getRejectedMessages(results).join(" ") || "Диагностика рабочего стека недоступна.");
      setRuntimeHealth(null);
    } else {
      setRuntimeError(getRejectedMessages(results).join(" ") || null);
      setRuntimeHealth(buildRuntimeHealthModel({ live, readiness, metrics, modelStatus, modelMonitoring }));
    }

    if (!silent) {
      setLoadingRuntime(false);
    }
  }, []);

  useEffect(() => {
    void loadRuntimeHealth();
  }, [loadRuntimeHealth]);

  useEffect(() => {
    const timerId = window.setInterval(() => {
      void loadRuntimeHealth({ silent: true });
    }, 5000);

    return () => {
      window.clearInterval(timerId);
    };
  }, [loadRuntimeHealth]);

  return {
    runtimeHealth,
    loadingRuntime,
    runtimeError,
    refreshRuntimeHealth: loadRuntimeHealth,
  };
}
