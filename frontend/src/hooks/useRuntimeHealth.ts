import { useCallback, useEffect, useState } from "react";
import { ApiError, runtimeApi } from "../api/api";
import { buildRuntimeHealthModel, type RuntimeHealthModel } from "../lib/runtimeHealth";
import type {
  RuntimeLivenessResponse,
  RuntimeMetricsResponse,
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

export type RuntimeHealthSnapshot = {
  runtimeHealth: RuntimeHealthModel | null;
  runtimeError: string | null;
};

export async function loadRuntimeHealthSnapshot(): Promise<RuntimeHealthSnapshot> {
  const results = await Promise.allSettled([
    runtimeApi.getLiveness(),
    runtimeApi.getReadiness(),
    runtimeApi.getMetrics(),
    runtimeApi.getModelStatus(),
  ] as const);
  const [liveResult, readinessResult, metricsResult, modelStatusResult] = results;
  const live = getSettledValue<RuntimeLivenessResponse>(liveResult);
  const readiness = getSettledValue<RuntimeReadinessResponse>(readinessResult);
  const metrics = getSettledValue<RuntimeMetricsResponse>(metricsResult);
  const modelStatus = getSettledValue<RuntimeModelStatusResponse>(modelStatusResult);
  const runtimeError = getRejectedMessages(results).join(" ") || null;

  if (!live && !readiness && !metrics && !modelStatus) {
    return {
      runtimeError: runtimeError || "Диагностика рабочего стека недоступна.",
      runtimeHealth: null,
    };
  }

  return {
    runtimeError,
    runtimeHealth: buildRuntimeHealthModel({ live, readiness, metrics, modelStatus }),
  };
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

    const snapshot = await loadRuntimeHealthSnapshot();
    setRuntimeError(snapshot.runtimeError);
    setRuntimeHealth(snapshot.runtimeHealth);

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
