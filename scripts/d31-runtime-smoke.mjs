import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const TERMINAL_AUDIT_STATUSES = new Set(["completed", "completed_with_warnings", "failed"]);
const SUCCESS_AUDIT_STATUSES = new Set(["completed", "completed_with_warnings"]);
const DEFAULT_AUDIT_PAYLOAD = {
  query: "\u0440\u0435\u043c\u043e\u043d\u0442 \u043a\u0432\u0430\u0440\u0442\u0438\u0440 \u043c\u043e\u0441\u043a\u0432\u0430",
  target_url: "https://smartremontmsk.ru/",
  top_n: 2,
};
const DEFAULT_FRONTEND_ROUTE_TEMPLATES = [
  "/",
  "/audits/{audit_id}",
  "/audits/{audit_id}?tab=report",
  "/audits/{audit_id}?tab=recommendations",
  "/audits/{audit_id}?tab=timeline",
  "/audits/{audit_id}?tab=pages",
  "/audits/{audit_id}?tab=competitors",
];

export function createSmokeConfig(sourceEnv = process.env) {
  const apiBaseUrl = (sourceEnv.D31_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const frontendBaseUrl = (sourceEnv.D31_FRONTEND_BASE_URL || "http://127.0.0.1:5173").replace(/\/$/, "");

  return {
    apiBaseUrl,
    frontendBaseUrl,
    outputPath: sourceEnv.D31_SMOKE_OUTPUT || path.join("output", "runtime-smoke", "d31-smoke-summary.json"),
    pollAttempts: Number(sourceEnv.D31_SMOKE_POLL_ATTEMPTS || 90),
    pollDelayMs: Number(sourceEnv.D31_SMOKE_POLL_DELAY_MS || 2000),
    auditPayload: {
      ...DEFAULT_AUDIT_PAYLOAD,
      ...(sourceEnv.D31_SMOKE_QUERY ? { query: sourceEnv.D31_SMOKE_QUERY } : {}),
      ...(sourceEnv.D31_SMOKE_TARGET_URL ? { target_url: sourceEnv.D31_SMOKE_TARGET_URL } : {}),
      ...(sourceEnv.D31_SMOKE_TOP_N ? { top_n: Number(sourceEnv.D31_SMOKE_TOP_N) } : {}),
    },
    frontendRouteTemplates: DEFAULT_FRONTEND_ROUTE_TEMPLATES,
    expectedRuntimeModel: {
      dataset_version: sourceEnv.D31_EXPECTED_DATASET_VERSION || "ru_commercial_dataset-20260421-primary",
      model_schema_version: sourceEnv.D31_EXPECTED_MODEL_SCHEMA_VERSION || "v1",
    },
  };
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getNested(source, pathParts) {
  return pathParts.reduce((current, pathPart) => {
    if (!isRecord(current)) {
      return undefined;
    }
    return current[pathPart];
  }, source);
}

function getNumber(value, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getArray(value) {
  return Array.isArray(value) ? value : [];
}

function getObject(value) {
  return isRecord(value) ? value : {};
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function buildApiUrl(config, route) {
  return `${config.apiBaseUrl}${route}`;
}

async function fetchJson(fetchImpl, url, options = {}) {
  const response = await fetchImpl(url, {
    headers: {
      accept: "application/json",
      ...(options.body === undefined ? {} : { "content-type": "application/json" }),
      ...(options.headers || {}),
    },
    ...options,
  });
  const bodyText = await response.text();
  let payload = null;

  if (bodyText.trim()) {
    try {
      payload = JSON.parse(bodyText);
    } catch (error) {
      throw new Error(`Expected JSON from ${url}, got HTTP ${response.status}: ${bodyText.slice(0, 300)}`);
    }
  }

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${url}: ${bodyText.slice(0, 500)}`);
  }

  return payload;
}

async function fetchText(fetchImpl, url) {
  const response = await fetchImpl(url, { headers: { accept: "text/html,*/*" } });
  const bodyText = await response.text();

  return {
    status: response.status,
    ok: response.ok,
    bodyText,
  };
}

async function createAudit(fetchImpl, config) {
  return fetchJson(fetchImpl, buildApiUrl(config, "/audits"), {
    method: "POST",
    body: JSON.stringify(config.auditPayload),
  });
}

async function pollAudit(fetchImpl, sleepImpl, config, auditId) {
  let latestAudit = null;

  for (let attempt = 1; attempt <= config.pollAttempts; attempt += 1) {
    latestAudit = await fetchJson(fetchImpl, buildApiUrl(config, `/audits/${auditId}`));
    const status = typeof latestAudit?.status === "string" ? latestAudit.status : "";

    if (TERMINAL_AUDIT_STATUSES.has(status)) {
      return {
        audit: latestAudit,
        attemptsUsed: attempt,
      };
    }

    if (attempt < config.pollAttempts) {
      await sleepImpl(config.pollDelayMs);
    }
  }

  throw new Error(`Audit ${auditId} did not reach a terminal status after ${config.pollAttempts} polls. Last payload: ${formatJson(latestAudit)}`);
}

function extractReadinessSummary(readyPayload) {
  const celeryWorkers = getObject(getNested(readyPayload, ["checks", "celery_workers"]));
  const topologyContract = getObject(celeryWorkers.topology_contract);
  const topology = getObject(celeryWorkers.topology);

  return {
    health_ready_status: typeof readyPayload?.status === "string" ? readyPayload.status : null,
    ready_worker_count: getNumber(celeryWorkers.worker_count),
    ready_required_profile_count: getNumber(topologyContract.required_profile_count)
      || getNumber(topology.required_profile_count),
    ready_workers: getArray(celeryWorkers.workers).map(String).sort(),
    ready_missing_queues: getArray(celeryWorkers.missing_queues).map(String).sort(),
  };
}

function extractMetricsSummary(metricsPayload) {
  return {
    metrics_status: typeof metricsPayload?.status === "string" ? metricsPayload.status : null,
    metrics_workers_status: typeof getNested(metricsPayload, ["workers", "status"]) === "string"
      ? getNested(metricsPayload, ["workers", "status"])
      : null,
    metrics_queue_pressure_status: typeof getNested(metricsPayload, ["queue_pressure", "status"]) === "string"
      ? getNested(metricsPayload, ["queue_pressure", "status"])
      : null,
    metrics_stuck_processing_count: getNumber(getNested(metricsPayload, ["database", "audits", "stuck_processing_count"])),
    metrics_queue_total_depth: getNumber(getNested(metricsPayload, ["broker", "total_depth"])),
  };
}

function summarizeCompetitors(resultsPayload) {
  const competitors = getArray(resultsPayload?.competitor_results);
  const analyzed = competitors.filter((item) => isRecord(item) && isRecord(item.features) && typeof item.score === "number").length;

  return {
    competitors_found: competitors.length,
    competitors_analyzed: analyzed,
    competitors_failed: competitors.length - analyzed,
  };
}

function summarizeRecommendations(recommendationsPayload) {
  const recommendationPayload = getObject(recommendationsPayload?.recommendations);
  const summary = getObject(recommendationPayload.summary);
  const groups = getArray(recommendationPayload.groups);

  return {
    recommendation_total: getNumber(summary.total_recommendations),
    recommendation_groups: groups.length,
    recommendation_competitor_context: summary.competitor_context === true,
  };
}

function summarizeDiagnostics(diagnosticsPayload) {
  const fanOut = diagnosticsPayload?.fan_out ?? null;
  const criticalPathModes = Object.fromEntries(
    getArray(diagnosticsPayload?.critical_path_stages)
      .filter((stage) => isRecord(stage) && typeof stage.stage === "string" && typeof stage.mode === "string")
      .map((stage) => [stage.stage, stage.mode]),
  );

  return {
    diagnostics_status: typeof diagnosticsPayload?.status === "string" ? diagnosticsPayload.status : null,
    fan_out: fanOut,
    critical_path_modes: criticalPathModes,
  };
}

function extractModelInfo(resultsPayload) {
  const modelInfo = getObject(getNested(resultsPayload, ["score_breakdown", "model_info"]));
  const selectedKeys = [
    "dataset_version",
    "artifact_version",
    "model_schema_version",
    "model_type",
    "source",
    "artifact_family",
  ];

  return Object.fromEntries(
    selectedKeys
      .filter((key) => modelInfo[key] !== undefined && modelInfo[key] !== null)
      .map((key) => [key, modelInfo[key]]),
  );
}

export function checkFrontendHtml(bodyText) {
  return {
    has_root: /<[^>]+id=["']root["'][^>]*>/i.test(bodyText),
    has_vite_entry: bodyText.includes("/src/main.tsx")
      || /<script\b(?=[^>]*\btype=["']module["'])(?=[^>]*\bsrc=["'][^"']*\/assets\/[^"']+\.js["'])/i.test(bodyText)
      || /<link\b(?=[^>]*\brel=["']modulepreload["'])(?=[^>]*\bhref=["'][^"']*\/assets\/[^"']+\.js["'])/i.test(bodyText),
  };
}

async function fetchFrontendRoutes(fetchImpl, config, auditId) {
  const entries = [];

  for (const template of config.frontendRouteTemplates) {
    const route = template.replace("{audit_id}", auditId);
    const response = await fetchText(fetchImpl, `${config.frontendBaseUrl}${route}`);
    entries.push([
      route,
      {
        status: response.status,
        ...checkFrontendHtml(response.bodyText),
      },
    ]);
  }

  return Object.fromEntries(entries);
}

function assertSmokeSummary(summary, config) {
  const failures = [];

  if (summary.health_ready_status !== "ready") {
    failures.push(`expected /health/ready status ready, got ${summary.health_ready_status}`);
  }
  if (summary.ready_worker_count < summary.ready_required_profile_count) {
    failures.push(
      `expected at least ${summary.ready_required_profile_count} Celery workers, got ${summary.ready_worker_count}`,
    );
  }
  if (summary.ready_missing_queues.length > 0) {
    failures.push(`expected no missing queues, got ${summary.ready_missing_queues.join(",")}`);
  }
  if (!SUCCESS_AUDIT_STATUSES.has(summary.audit_status)) {
    failures.push(`expected completed audit, got ${summary.audit_status}`);
  }
  if (summary.competitors_found <= 0 || summary.competitors_analyzed <= 0) {
    failures.push(`expected analyzed competitors, got found=${summary.competitors_found}, analyzed=${summary.competitors_analyzed}`);
  }
  if (summary.fan_out?.stage !== "competitor_page") {
    failures.push(`expected competitor_page fan-out, got ${summary.fan_out?.stage ?? "none"}`);
  }
  if (summary.fan_out && summary.fan_out.dispatch_count !== summary.fan_out.terminal_count) {
    failures.push(`expected fan-out terminal count to match dispatch count, got dispatch=${summary.fan_out.dispatch_count}, terminal=${summary.fan_out.terminal_count}`);
  }
  if (summary.critical_path_modes.competitor_page !== "fan_out_max") {
    failures.push(`expected competitor_page critical path mode fan_out_max, got ${summary.critical_path_modes.competitor_page}`);
  }
  if (summary.model_info.dataset_version !== config.expectedRuntimeModel.dataset_version) {
    failures.push(`expected runtime dataset ${config.expectedRuntimeModel.dataset_version}, got ${summary.model_info.dataset_version}`);
  }
  if (summary.model_info.model_schema_version !== config.expectedRuntimeModel.model_schema_version) {
    failures.push(`expected runtime model schema ${config.expectedRuntimeModel.model_schema_version}, got ${summary.model_info.model_schema_version}`);
  }

  for (const [route, routeSummary] of Object.entries(summary.frontend_routes)) {
    if (routeSummary.status !== 200 || routeSummary.has_root !== true || routeSummary.has_vite_entry !== true) {
      failures.push(`frontend route ${route} returned invalid shell: ${formatJson(routeSummary)}`);
    }
  }

  if (failures.length > 0) {
    throw new Error(`D31 runtime smoke failed:\n- ${failures.join("\n- ")}`);
  }
}

export async function runD31RuntimeSmoke({
  config = createSmokeConfig(),
  fetchImpl = fetch,
  sleepImpl = sleep,
  writeFileImpl = writeFile,
  mkdirImpl = mkdir,
} = {}) {
  const readyPayload = await fetchJson(fetchImpl, buildApiUrl(config, "/health/ready"));
  const metricsPayload = await fetchJson(fetchImpl, buildApiUrl(config, "/health/metrics"));
  const createdAudit = await createAudit(fetchImpl, config);
  const auditId = String(createdAudit.id);
  const { audit, attemptsUsed } = await pollAudit(fetchImpl, sleepImpl, config, auditId);
  const resultsPayload = await fetchJson(fetchImpl, buildApiUrl(config, `/audits/${auditId}/results`));
  const recommendationsPayload = await fetchJson(fetchImpl, buildApiUrl(config, `/audits/${auditId}/recommendations`));
  const diagnosticsPayload = await fetchJson(fetchImpl, buildApiUrl(config, `/audits/${auditId}/events/diagnostics`));
  const frontendRoutes = await fetchFrontendRoutes(fetchImpl, config, auditId);
  const summary = {
    generated_at: new Date().toISOString(),
    audit_id: auditId,
    audit_payload: config.auditPayload,
    audit_poll_attempts: attemptsUsed,
    ...extractReadinessSummary(readyPayload),
    ...extractMetricsSummary(metricsPayload),
    audit_status: typeof audit?.status === "string" ? audit.status : null,
    score: typeof resultsPayload?.score === "number" ? resultsPayload.score : null,
    ...summarizeCompetitors(resultsPayload),
    ...summarizeRecommendations(recommendationsPayload),
    model_info: extractModelInfo(resultsPayload),
    ...summarizeDiagnostics(diagnosticsPayload),
    frontend_routes: frontendRoutes,
  };

  assertSmokeSummary(summary, config);

  await mkdirImpl(path.dirname(config.outputPath), { recursive: true });
  await writeFileImpl(config.outputPath, `${formatJson(summary)}\n`, "utf8");
  return summary;
}

async function main() {
  try {
    const summary = await runD31RuntimeSmoke();
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
