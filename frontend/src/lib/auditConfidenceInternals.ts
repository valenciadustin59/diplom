import type {
  AuditStatus,
  ScoreBreakdown,
} from "../types";
import type {
  ScoreConfidenceInput,
  ScoreConfidenceReason,
  ScoreConfidenceTone,
} from "./auditConfidence";
import type {
  CompetitorCoverage,
  ScoreConfidenceContext,
} from "./auditConfidenceContext";
import {
  asNonEmptyString,
  formatPercent,
  formatScore,
  getEffectiveFeatureSchema,
  getEffectiveHeavyAnalysis,
  getFailureLabel,
  getModelLabel,
  getWarnings,
  hasRecordValues,
  MIN_COMPETITORS_ANALYZED,
  MIN_COMPETITOR_COVERAGE_RATIO,
} from "./auditConfidenceContext";

const SUCCESS_STATUSES = new Set<AuditStatus>(["completed", "completed_with_warnings"]);
const IN_FLIGHT_STATUSES = new Set<AuditStatus>(["queued", "processing"]);

function buildReason(
  code: string,
  label: string,
  detail: string,
  tone: ScoreConfidenceTone,
): ScoreConfidenceReason {
  return { code, label, detail, tone };
}

function buildStatusReasons(status: AuditStatus | null): ScoreConfidenceReason[] {
  if (!status) {
    return [
      buildReason(
        "audit_not_selected",
        "Аудит не выбран",
        "Уверенность появится после выбора или запуска аудита.",
        "muted",
      ),
    ];
  }

  if (IN_FLIGHT_STATUSES.has(status)) {
    return [
      buildReason(
        "audit_in_progress",
        "Аудит ещё выполняется",
        "Score и data-quality проверки могут измениться после завершения этапов анализа.",
        "muted",
      ),
    ];
  }

  if (status === "failed") {
    return [
      buildReason(
        "audit_failed",
        "Аудит завершился ошибкой",
        "Итоговый score нельзя считать надёжным, пока pipeline не завершился успешно.",
        "error",
      ),
    ];
  }

  if (status === "completed_with_warnings") {
    return [
      buildReason(
        "audit_completed_with_warnings",
        "Аудит завершён с предупреждениями",
        "Primary score рассчитан; предупреждения могут ограничивать полноту сравнения, рекомендаций или отдельных источников данных.",
        "warning",
      ),
    ];
  }

  return [
    buildReason(
      "audit_completed",
      "Аудит завершён",
      "Pipeline дошёл до финализации, поэтому score можно интерпретировать вместе с data-quality проверками.",
      "ok",
    ),
  ];
}

function buildFetchReasons(input: ScoreConfidenceInput, status: AuditStatus | null): ScoreConfidenceReason[] {
  const fetchStatus = input.results?.target_fetch_status ?? input.audit?.target_fetch_status ?? null;
  const fetchMethod = input.results?.target_fetch_method ?? input.audit?.target_fetch_method ?? null;
  const fetchError = asNonEmptyString(input.results?.target_fetch_error_message) ?? asNonEmptyString(input.audit?.target_fetch_error_message);

  if (fetchStatus === "failed") {
    return [
      buildReason(
        "target_fetch_failed",
        "Целевая страница не загружена",
        fetchError ?? "Этап загрузки целевой страницы завершился ошибкой.",
        "error",
      ),
    ];
  }

  if (fetchStatus === "success") {
    if (fetchMethod === "browser" || fetchMethod === "http_retry") {
      return [
        buildReason(
          "target_fetch_fallback",
          "Загрузка целевой страницы через fallback",
          `Страница была получена методом ${fetchMethod}; score полезен, но стоит проверить, не отличался ли ответ от обычного HTTP fetch.`,
          "warning",
        ),
      ];
    }

    return [
      buildReason(
        "target_fetch_success",
        "Целевая страница загружена штатно",
        `Метод загрузки: ${fetchMethod ?? "не указан"}.`,
        "ok",
      ),
    ];
  }

  return [
    buildReason(
      "target_fetch_unknown",
      "Статус загрузки целевой страницы неизвестен",
      SUCCESS_STATUSES.has(status as AuditStatus)
        ? "В сохранённом аудите нет статуса fetch, поэтому это считается legacy/data-quality предупреждением."
        : "Статус fetch появится после прохождения этапа загрузки.",
      SUCCESS_STATUSES.has(status as AuditStatus) ? "warning" : "muted",
    ),
  ];
}

function buildFeatureReasons(input: ScoreConfidenceInput, status: AuditStatus | null): ScoreConfidenceReason[] {
  const schema = getEffectiveFeatureSchema(input);
  const heavyAnalysis = getEffectiveHeavyAnalysis(input);
  const toneWhenMissing: ScoreConfidenceTone = SUCCESS_STATUSES.has(status as AuditStatus) ? "warning" : "muted";

  return [
    schema
      ? buildReason(
          "feature_schema_present",
          "Схема признаков сохранена",
          `feature_schema_version=${schema}.`,
          "ok",
        )
      : buildReason(
          "feature_schema_missing",
          "Нет версии схемы признаков",
          SUCCESS_STATUSES.has(status as AuditStatus)
            ? "Score сохранён без feature_schema_version; это похоже на legacy или неполный audit payload."
            : "Версия признаков появится после извлечения признаков.",
          toneWhenMissing,
        ),
    heavyAnalysis
      ? buildReason(
          "heavy_analysis_present",
          "Углублённый анализ доступен",
          "Heavy analysis payload сохранён и мог участвовать в признаках модели.",
          "ok",
        )
      : buildReason(
          "heavy_analysis_missing",
          "Углублённый анализ отсутствует",
          SUCCESS_STATUSES.has(status as AuditStatus)
            ? "Score рассчитан без видимого heavy_analysis payload; проверьте полноту сохранённых данных."
            : "Heavy analysis ещё не завершён или аудит остановился раньше.",
          toneWhenMissing,
        ),
  ];
}

function buildScoreReasons(
  status: AuditStatus | null,
  breakdown: ScoreBreakdown | null,
  score: number | null,
): ScoreConfidenceReason[] {
  const modelInfo = hasRecordValues(breakdown?.model_info) ? breakdown.model_info : null;

  if (typeof score !== "number") {
    return [
      buildReason(
        "score_missing",
        "Score не рассчитан",
        SUCCESS_STATUSES.has(status as AuditStatus)
          ? "Аудит завершён, но итоговая оценка отсутствует в payload."
          : "Итоговая оценка появится после scoring stage.",
        SUCCESS_STATUSES.has(status as AuditStatus) || status === "failed" ? "error" : "muted",
      ),
    ];
  }

  const reasons = [
    buildReason(
      "score_present",
      "Score рассчитан",
      `Итоговая оценка: ${formatScore(score)}.`,
      "ok",
    ),
  ];

  if (modelInfo) {
    reasons.push(
      buildReason(
        "model_metadata_present",
        "Модель score идентифицирована",
        `${getModelLabel(modelInfo)}; score_breakdown.model_info сохранён в аудите.`,
        "ok",
      ),
    );
  } else if (breakdown) {
    reasons.push(
      buildReason(
        "missing_model_metadata",
        "Нет runtime model_info",
        "Score breakdown сохранён без metadata модели; это предупреждение для legacy или неполной записи.",
        "warning",
      ),
    );
  } else {
    reasons.push(
      buildReason(
        "missing_score_breakdown",
        "Нет расшифровки score",
        "Итоговая оценка есть, но score_breakdown отсутствует, поэтому ML/runtime metadata недоступна.",
        "warning",
      ),
    );
  }

  return reasons;
}

function buildCompetitorReasons(coverage: CompetitorCoverage, status: AuditStatus | null): ScoreConfidenceReason[] {
  if (!SUCCESS_STATUSES.has(status as AuditStatus)) {
    return [
      buildReason(
        "competitor_coverage_pending",
        "Покрытие конкурентов ещё не финальное",
        "Конкурентные страницы оцениваются после primary score и могут появиться позже.",
        "muted",
      ),
    ];
  }

  if (coverage.analyzed < MIN_COMPETITORS_ANALYZED) {
    return [
      buildReason(
        "no_competitors_analyzed",
        "Нет проанализированных конкурентов",
        "Primary score уже рассчитан по целевой странице; без конкурентов ненадёжны только сравнение с выдачей и competitor-aware рекомендации.",
        "warning",
      ),
    ];
  }

  const reasons = [
    buildReason(
      "competitor_coverage_present",
      "Конкурентное покрытие доступно",
      `Проанализировано ${coverage.analyzed} из ${coverage.found} найденных страниц; coverage=${formatPercent(coverage.ratio)}.`,
      "ok",
    ),
  ];

  if (coverage.ratio !== null && coverage.ratio < MIN_COMPETITOR_COVERAGE_RATIO) {
    reasons.push(
      buildReason(
        "low_competitor_coverage",
        "Низкое покрытие конкурентов",
        `Покрытие ниже ${formatPercent(MIN_COMPETITOR_COVERAGE_RATIO)}: ${coverage.analyzed}/${coverage.found}.`,
        "warning",
      ),
    );
  }

  if (coverage.failed > 0) {
    reasons.push(
      buildReason(
        "competitor_fetch_failures",
        "Часть конкурентов не обработана",
        `${coverage.failed} конкурентных страниц ограничили загрузку или анализ.`,
        "warning",
      ),
    );
  }

  return reasons;
}

function buildRecommendationReasons(recommendationCount: number | null, status: AuditStatus | null): ScoreConfidenceReason[] {
  if (typeof recommendationCount === "number" && recommendationCount > 0) {
    return [
      buildReason(
        "recommendations_present",
        "Рекомендации сформированы",
        `Доступно рекомендаций: ${recommendationCount}.`,
        "ok",
      ),
    ];
  }

  if (SUCCESS_STATUSES.has(status as AuditStatus)) {
    return [
      buildReason(
        "recommendations_missing",
        "Рекомендации отсутствуют или неполные",
        "Score есть, но список действий не подтверждает интерпретацию результата.",
        "warning",
      ),
    ];
  }

  return [
    buildReason(
      "recommendations_pending",
      "Рекомендации ещё не сформированы",
      "План действий появится после завершения конкурентного анализа и recommendation stage.",
      "muted",
    ),
  ];
}

function buildRuntimeWarningReasons(input: ScoreConfidenceInput): ScoreConfidenceReason[] {
  const warnings = getWarnings(input);
  const failureContext = input.results?.failure_context ?? input.audit?.failure_context ?? null;
  const reasons = warnings.map((warning) =>
    buildReason(
      `runtime_warning:${warning}`,
      "Runtime warning",
      warning,
      "warning",
    ),
  );

  if (failureContext || input.results?.error_message || input.audit?.error_message) {
    reasons.push(
      buildReason(
        "failure_context_present",
        "Есть failure context",
        getFailureLabel(input),
        "error",
      ),
    );
  }

  return reasons;
}

export function buildScoreConfidenceReasons(
  input: ScoreConfidenceInput,
  context: ScoreConfidenceContext,
): ScoreConfidenceReason[] {
  return [
    ...buildStatusReasons(context.status),
    ...buildFetchReasons(input, context.status),
    ...buildFeatureReasons(input, context.status),
    ...buildScoreReasons(context.status, context.breakdown, context.score),
    ...buildCompetitorReasons(context.coverage, context.status),
    ...buildRecommendationReasons(context.recommendationCount, context.status),
    ...buildRuntimeWarningReasons(input),
  ];
}
