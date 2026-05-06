import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const TERMINAL_STATUSES = new Set(["completed", "completed_with_warnings", "failed"]);
const SUCCESS_STATUSES = new Set(["completed", "completed_with_warnings"]);

const DEFAULT_CASES = [
  {
    id: "relevant-industrial-cranes",
    query: "козловой кран купить",
    target_url: "https://pzpo.ru/crane/cat-krany-kozlovye/",
    top_n: 3,
    expectation: "relevant",
    min_score: 35,
  },
  {
    id: "unrelated-wine-shop-for-cranes",
    query: "купить козловой кран",
    target_url: "https://winemore.ru/",
    top_n: 3,
    expectation: "mismatch",
    max_score: 35,
  },
  {
    id: "relevant-service-without-buy-modifier",
    query: "занятия пилатес москва",
    target_url: "https://pilatesmed.ru/",
    top_n: 3,
    expectation: "relevant",
    min_score: 30,
  },
];

function createConfig(sourceEnv = process.env) {
  return {
    apiBaseUrl: (sourceEnv.D96_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, ""),
    frontendBaseUrl: (sourceEnv.D96_FRONTEND_BASE_URL || "http://127.0.0.1:5173").replace(/\/$/, ""),
    outputPath:
      sourceEnv.D96_SMOKE_OUTPUT ||
      path.join("output", "runtime-smoke", "d96-rosberta-live-smoke-summary.json"),
    pollAttempts: Number(sourceEnv.D96_SMOKE_POLL_ATTEMPTS || 180),
    pollDelayMs: Number(sourceEnv.D96_SMOKE_POLL_DELAY_MS || 2000),
    cases: DEFAULT_CASES,
    expectedRuntimeModel: {
      dataset_version: sourceEnv.D96_EXPECTED_DATASET_VERSION || "dataset-v7-final",
      model_schema_version: sourceEnv.D96_EXPECTED_MODEL_SCHEMA_VERSION || "v4",
    },
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getNumber(value, fallback = null) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      accept: "application/json",
      ...(options.body === undefined ? {} : { "content-type": "application/json" }),
      ...(options.headers || {}),
    },
    ...options,
  });
  const bodyText = await response.text();
  const payload = bodyText.trim() ? JSON.parse(bodyText) : null;
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${url}: ${bodyText.slice(0, 500)}`);
  }
  return payload;
}

async function fetchText(url) {
  const response = await fetch(url, { headers: { accept: "text/html,*/*" } });
  return {
    status: response.status,
    body: await response.text(),
  };
}

function apiUrl(config, route) {
  return `${config.apiBaseUrl}${route}`;
}

async function createAudit(config, item) {
  return fetchJson(apiUrl(config, "/audits"), {
    method: "POST",
    body: JSON.stringify({
      query: item.query,
      target_url: item.target_url,
      top_n: item.top_n,
    }),
  });
}

async function pollAudit(config, auditId) {
  let latest = null;
  for (let attempt = 1; attempt <= config.pollAttempts; attempt += 1) {
    latest = await fetchJson(apiUrl(config, `/audits/${auditId}`));
    if (TERMINAL_STATUSES.has(String(latest?.status || ""))) {
      return { audit: latest, attemptsUsed: attempt };
    }
    await sleep(config.pollDelayMs);
  }
  throw new Error(`Audit ${auditId} did not finish. Last payload: ${formatJson(latest)}`);
}

function summarizeReady(payload) {
  const celery = payload?.checks?.celery_workers ?? {};
  const workers = getArray(celery.workers).map(String).sort();
  const expectedQueues = getArray(celery.expected_queues).map(String).sort();
  return {
    ready_status: String(payload?.status || ""),
    worker_count: getNumber(celery.worker_count, 0),
    workers,
    expected_queues: expectedQueues,
    missing_queues: getArray(celery.missing_queues).map(String).sort(),
    semantic_worker_present: workers.some((name) => name.includes("semantic_cpu")),
    semantic_queue_expected: expectedQueues.includes("audits.semantic"),
  };
}

function summarizeModel(payload) {
  return {
    status: payload?.status ?? null,
    artifact_sha1: payload?.artifact_sha1 ?? null,
    dataset_version: payload?.dataset?.dataset_version ?? null,
    model_schema_version: payload?.model?.model_schema_version ?? null,
    model_type: payload?.model?.model_type ?? null,
    artifact_version: payload?.model?.artifact_version ?? null,
  };
}

function summarizeMetrics(payload) {
  const queues = payload?.queue_pressure?.queues ?? {};
  const semantic = queues["audits.semantic"] ?? {};
  return {
    metrics_status: payload?.status ?? null,
    workers_status: payload?.workers?.status ?? null,
    queue_pressure_status: payload?.queue_pressure?.status ?? null,
    semantic_queue_depth: getNumber(semantic.depth, 0),
    semantic_queue_workers: getArray(semantic.workers).map(String).sort(),
    semantic_pressure_status: semantic.pressure_status ?? null,
  };
}

function extractEarlyStop(results) {
  const direct = results?.early_stop;
  if (isRecord(direct)) {
    return direct;
  }
  const guardrail = results?.score_breakdown?.relevance_guardrail;
  if (isRecord(guardrail) && guardrail.early_stop === true) {
    return {
      early_stop: true,
      reason: guardrail.reason ?? guardrail.early_stop_decision?.reason ?? null,
      score_basis: results?.comparison_summary?.score_basis ?? null,
    };
  }
  return null;
}

function summarizeCase({ item, audit, attemptsUsed, results, recommendations, diagnostics }) {
  const competitorResults = getArray(results?.competitor_results);
  const accepted = competitorResults.filter((candidate) => candidate?.competitor_context_status === "accepted");
  const discarded = competitorResults.filter((candidate) => candidate?.competitor_context_status === "discarded");
  const unused = competitorResults.filter((candidate) => candidate?.competitor_context_status === "unused");
  const summary = results?.comparison_summary ?? {};
  const quality = summary?.competitor_context_quality ?? {};
  const features = results?.features ?? {};
  const semanticProviderCode = getNumber(features.semantic_provider_code);
  const recommendationPayload = recommendations?.recommendations ?? {};

  return {
    id: item.id,
    query: item.query,
    target_url: item.target_url,
    top_n: item.top_n,
    expectation: item.expectation,
    audit_id: String(audit?.id || ""),
    status: audit?.status ?? null,
    poll_attempts: attemptsUsed,
    score: getNumber(results?.score),
    early_stop: extractEarlyStop(results),
    target_fetch_status: results?.target_fetch_status ?? null,
    target_fetch_method: results?.target_fetch_method ?? null,
    semantic_provider_code: semanticProviderCode,
    semantic_model_code: getNumber(features.semantic_model_code),
    semantic_fallback_used: getNumber(features.semantic_fallback_used, 0),
    semantic_embedding_failure: getNumber(features.semantic_embedding_failure, 0),
    semantic_similarity: getNumber(features.semantic_similarity),
    semantic_similarity_raw: getNumber(features.semantic_similarity_raw),
    query_core_keyword_coverage_ratio: getNumber(features.query_core_keyword_coverage_ratio),
    query_intent_modifier_coverage_ratio: getNumber(features.query_intent_modifier_coverage_ratio),
    competitor_context_status: summary?.competitor_context_status ?? null,
    competitor_context_quality: quality,
    competitor_results_count: competitorResults.length,
    accepted_competitors: accepted.length,
    discarded_competitors: discarded.length,
    unused_competitors: unused.length,
    replacement_attempts: getNumber(quality.replacement_attempts, 0),
    replacements_used: getNumber(quality.replacements_used, 0),
    discard_reasons: quality.discard_reasons ?? {},
    recommendation_total: getNumber(recommendationPayload?.summary?.total_recommendations, 0),
    recommendation_groups: getArray(recommendationPayload?.groups).length,
    fan_out: diagnostics?.fan_out ?? null,
  };
}

function validateSummary(summary, config) {
  const failures = [];

  if (summary.ready.ready_status !== "ready") {
    failures.push(`ready status is ${summary.ready.ready_status}`);
  }
  if (!summary.ready.semantic_worker_present || !summary.ready.semantic_queue_expected) {
    failures.push("semantic worker/queue is not present in readiness");
  }
  if (summary.ready.missing_queues.length > 0) {
    failures.push(`missing queues: ${summary.ready.missing_queues.join(", ")}`);
  }
  if (summary.model.dataset_version !== config.expectedRuntimeModel.dataset_version) {
    failures.push(`dataset mismatch: ${summary.model.dataset_version}`);
  }
  if (summary.model.model_schema_version !== config.expectedRuntimeModel.model_schema_version) {
    failures.push(`schema mismatch: ${summary.model.model_schema_version}`);
  }

  for (const item of summary.cases) {
    if (!SUCCESS_STATUSES.has(String(item.status || ""))) {
      failures.push(`${item.id}: status ${item.status}`);
      continue;
    }
    if (item.semantic_provider_code !== 2) {
      failures.push(`${item.id}: expected RoSBERTa provider code 2, got ${item.semantic_provider_code}`);
    }
    if (item.semantic_embedding_failure !== 0) {
      failures.push(`${item.id}: semantic embedding failure`);
    }
    if (item.expectation === "mismatch" && !(typeof item.score === "number" && item.score <= item.max_score)) {
      failures.push(`${item.id}: expected mismatch score <= ${item.max_score}, got ${item.score}`);
    }
    if (item.expectation === "relevant") {
      if (item.early_stop) {
        failures.push(`${item.id}: relevant page was early-stopped`);
      }
      if (!(typeof item.score === "number" && item.score >= item.min_score)) {
        failures.push(`${item.id}: expected relevant score >= ${item.min_score}, got ${item.score}`);
      }
      if (!isRecord(item.competitor_context_quality)) {
        failures.push(`${item.id}: missing competitor context quality`);
      }
    }
  }

  return failures;
}

async function runD96RosbertaLiveSmoke(config = createConfig()) {
  const readyPayload = await fetchJson(apiUrl(config, "/health/ready"));
  const modelPayload = await fetchJson(apiUrl(config, "/health/model"));
  const metricsBefore = await fetchJson(apiUrl(config, "/health/metrics"));
  const frontendRoot = await fetchText(`${config.frontendBaseUrl}/`);

  const caseSummaries = [];
  for (const item of config.cases) {
    const created = await createAudit(config, item);
    const auditId = String(created.id);
    const { audit, attemptsUsed } = await pollAudit(config, auditId);
    const results = await fetchJson(apiUrl(config, `/audits/${auditId}/results`));
    const recommendations = await fetchJson(apiUrl(config, `/audits/${auditId}/recommendations`));
    const diagnostics = await fetchJson(apiUrl(config, `/audits/${auditId}/events/diagnostics`));
    const caseSummary = summarizeCase({ item, audit, attemptsUsed, results, recommendations, diagnostics });
    caseSummary.max_score = item.max_score ?? null;
    caseSummary.min_score = item.min_score ?? null;
    caseSummaries.push(caseSummary);
  }

  const metricsAfter = await fetchJson(apiUrl(config, "/health/metrics"));
  const summary = {
    generated_at: new Date().toISOString(),
    api_base_url: config.apiBaseUrl,
    frontend_base_url: config.frontendBaseUrl,
    frontend_root_status: frontendRoot.status,
    frontend_root_has_shell: frontendRoot.body.includes("root") && frontendRoot.body.includes("script"),
    ready: summarizeReady(readyPayload),
    model: summarizeModel(modelPayload),
    metrics_before: summarizeMetrics(metricsBefore),
    metrics_after: summarizeMetrics(metricsAfter),
    cases: caseSummaries,
  };
  summary.failures = validateSummary(summary, config);
  summary.status = summary.failures.length === 0 ? "passed" : "failed";

  await mkdir(path.dirname(config.outputPath), { recursive: true });
  await writeFile(config.outputPath, `${formatJson(summary)}\n`, "utf8");
  if (summary.status !== "passed") {
    throw new Error(`D96 RoSBERTa live smoke failed:\n- ${summary.failures.join("\n- ")}`);
  }
  return summary;
}

async function main() {
  try {
    const summary = await runD96RosbertaLiveSmoke();
    console.log(formatJson(summary));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

const isDirectExecution = Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectExecution) {
  main();
}

export { createConfig, runD96RosbertaLiveSmoke };
