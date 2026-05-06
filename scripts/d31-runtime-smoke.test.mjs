import assert from "node:assert/strict";
import test from "node:test";

import { checkFrontendHtml, createSmokeConfig, runD31RuntimeSmoke } from "./d31-runtime-smoke.mjs";

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async text() {
      return JSON.stringify(payload);
    },
  };
}

function textResponse(bodyText, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async text() {
      return bodyText;
    },
  };
}

test("checkFrontendHtml reads the full Vite shell, not just the first bytes", () => {
  const html = `${"x".repeat(600)}<div id="root"></div><script type="module" src="/src/main.tsx"></script>`;

  assert.deepEqual(checkFrontendHtml(html), {
    has_root: true,
    has_vite_entry: true,
  });
});

test("runD31RuntimeSmoke writes a validated summary from live endpoint shapes", async () => {
  const config = createSmokeConfig({
    D31_API_BASE_URL: "http://api.test",
    D31_FRONTEND_BASE_URL: "http://frontend.test",
    D31_SMOKE_OUTPUT: "output/runtime-smoke/test-d31.json",
    D31_SMOKE_POLL_ATTEMPTS: "3",
    D31_SMOKE_POLL_DELAY_MS: "1",
  });
  let auditPollCount = 0;
  const sleeps = [];
  const writes = [];
  const mkdirs = [];
  const shellHtml = `${" ".repeat(450)}<div id="root"></div><script type="module" src="/src/main.tsx"></script>`;

  const fetchImpl = async (url, options = {}) => {
    const parsedUrl = new URL(url);
    const method = options.method || "GET";
    const route = `${method} ${parsedUrl.origin}${parsedUrl.pathname}${parsedUrl.search}`;

    switch (route) {
      case "GET http://api.test/health/ready":
        return jsonResponse({
          status: "ready",
          checks: {
            celery_workers: {
              worker_count: 5,
              workers: [
                "site-audit.cpu_ml@host",
                "site-audit.heavy_analysis@host",
                "site-audit.network@host",
                "site-audit.pipeline@host",
                "site-audit.semantic_cpu@host",
              ],
              missing_queues: [],
              topology_contract: { required_profile_count: 5 },
            },
          },
        });
      case "GET http://api.test/health/metrics":
        return jsonResponse({
          status: "degraded",
          workers: { status: "ok" },
          queue_pressure: { status: "ok" },
          database: { audits: { stuck_processing_count: 3 } },
          broker: { total_depth: 0 },
        });
      case "POST http://api.test/audits": {
        const postedPayload = JSON.parse(options.body);
        assert.equal(postedPayload.target_url, "https://smartremontmsk.ru/");
        assert.equal(postedPayload.top_n, 2);
        return jsonResponse({ id: "audit-1", status: "queued" }, 201);
      }
      case "GET http://api.test/audits/audit-1":
        auditPollCount += 1;
        return jsonResponse({ id: "audit-1", status: auditPollCount === 1 ? "processing" : "completed" });
      case "GET http://api.test/audits/audit-1/results":
        return jsonResponse({
          audit_id: "audit-1",
          status: "completed",
          score: 69.5249,
          competitor_results: [
            { score: 71.2, features: { word_count: 1200 } },
            { score: 67.1, features: { word_count: 900 } },
          ],
          score_breakdown: {
            model_info: {
              dataset_version: "ru_commercial_dataset-20260421-primary",
              artifact_version: "ru_commercial_dataset-20260421-primary-20260421174901",
              model_schema_version: "v1",
              model_type: "RandomForestRegressor",
            },
          },
        });
      case "GET http://api.test/audits/audit-1/recommendations":
        return jsonResponse({
          audit_id: "audit-1",
          status: "completed",
          recommendations: {
            summary: {
              total_recommendations: 13,
              competitor_context: true,
            },
            groups: [{ key: "technical_seo" }, { key: "commercial_trust" }, { key: "semantic_intent" }, { key: "competitor_gap" }],
          },
        });
      case "GET http://api.test/audits/audit-1/events/diagnostics":
        return jsonResponse({
          audit_id: "audit-1",
          status: "completed",
          fan_out: {
            stage: "competitor_page",
            dispatch_count: 2,
            started_count: 2,
            terminal_count: 2,
            in_flight_count: 0,
          },
          critical_path_stages: [
            { stage: "fetch", mode: "serial_sum" },
            { stage: "competitor_page", mode: "fan_out_max" },
          ],
        });
      default:
        if (parsedUrl.origin === "http://frontend.test") {
          return textResponse(shellHtml);
        }
        throw new Error(`Unexpected fetch route: ${route}`);
    }
  };

  const summary = await runD31RuntimeSmoke({
    config,
    fetchImpl,
    sleepImpl: async (delayMs) => {
      sleeps.push(delayMs);
    },
    mkdirImpl: async (...args) => {
      mkdirs.push(args);
    },
    writeFileImpl: async (...args) => {
      writes.push(args);
    },
  });

  assert.equal(summary.audit_id, "audit-1");
  assert.equal(summary.health_ready_status, "ready");
  assert.equal(summary.ready_worker_count, 5);
  assert.equal(summary.ready_required_profile_count, 5);
  assert.equal(summary.competitors_analyzed, 2);
  assert.equal(summary.recommendation_total, 13);
  assert.equal(summary.critical_path_modes.competitor_page, "fan_out_max");
  assert.equal(summary.model_info.dataset_version, "ru_commercial_dataset-20260421-primary");
  assert.equal(Object.values(summary.frontend_routes).every((route) => route.has_root && route.has_vite_entry), true);
  assert.deepEqual(sleeps, [1]);
  assert.deepEqual(mkdirs, [["output/runtime-smoke", { recursive: true }]]);
  assert.equal(writes.length, 1);
  assert.equal(writes[0][0], "output/runtime-smoke/test-d31.json");
  assert.match(writes[0][1], /"audit_id": "audit-1"/);
});
