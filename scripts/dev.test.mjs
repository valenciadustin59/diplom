import assert from "node:assert/strict";
import os from "node:os";
import test from "node:test";
import { buildBackendRuntimeEnv, buildCeleryWorkerArgs, CELERY_AUDIT_QUEUES, CELERY_WORKER_PROFILES } from "./dev.mjs";
test("buildBackendRuntimeEnv provides local development defaults", () => {
  const env = buildBackendRuntimeEnv({ BACKEND_PORT: "8000" }, {});
  assert.equal(env.SERP_PROVIDER, "searxng");
  assert.equal(env.SEARXNG_BASE_URL, "http://127.0.0.1:8888");
  assert.equal(env.SEARXNG_LANGUAGE, "ru-RU");
  assert.equal(env.CELERY_BROKER_URL, "redis://127.0.0.1:6379/0");
  assert.equal(env.CELERY_RESULT_BACKEND, "redis://127.0.0.1:6379/0");
  assert.equal(env.BACKEND_PORT, "8000");
});
test("buildBackendRuntimeEnv preserves explicit source environment values", () => {
  const env = buildBackendRuntimeEnv(
    {},
    {
      SERP_PROVIDER: "custom-provider",
      SEARXNG_BASE_URL: "http://internal-search:8080",
      SEARXNG_LANGUAGE: "en-US",
      CELERY_BROKER_URL: "redis://redis.internal:6380/0",
      CELERY_RESULT_BACKEND: "redis://redis.internal:6380/1",
    },
  );
  assert.equal(env.SERP_PROVIDER, "custom-provider");
  assert.equal(env.SEARXNG_BASE_URL, "http://internal-search:8080");
  assert.equal(env.SEARXNG_LANGUAGE, "en-US");
  assert.equal(env.CELERY_BROKER_URL, "redis://redis.internal:6380/0");
  assert.equal(env.CELERY_RESULT_BACKEND, "redis://redis.internal:6380/1");
});
test("worker topology profiles cover distributed audit queues exactly once", () => {
  assert.deepEqual(CELERY_WORKER_PROFILES.map((profile) => profile.name), ["pipeline", "network", "heavy_analysis", "cpu_ml"]);
  assert.deepEqual([...CELERY_AUDIT_QUEUES].sort(), [
    "audits.pipeline",
    "audits.fetch",
    "audits.heavy_analysis",
    "audits.competitors",
    "audits.competitor_pages",
    "audits.features",
    "audits.scoring",
    "audits.recommendations",
    "audits.finalize",
  ].sort());
});
test("buildCeleryWorkerArgs subscribes network worker only to network-affinity queues", () => {
  const args = buildCeleryWorkerArgs("network");
  const queueIndex = args.indexOf("-Q");
  const hostnameIndex = args.indexOf("--hostname");
  const networkProfile = CELERY_WORKER_PROFILES.find((profile) => profile.name === "network");
  assert.notEqual(queueIndex, -1);
  assert.notEqual(hostnameIndex, -1);
  assert.ok(networkProfile);
  assert.equal(args[hostnameIndex + 1], "site-audit.network@%h");
  assert.equal(args[queueIndex + 1], networkProfile.queues.join(","));
  assert.match(args[queueIndex + 1], /audits\.competitor_pages/);
  assert.doesNotMatch(args[queueIndex + 1], /audits\.scoring/);
  assert.doesNotMatch(args[queueIndex + 1], /audits\.heavy_analysis/);
});

test("buildCeleryWorkerArgs subscribes heavy-analysis worker only to analyzer queue", () => {
  const args = buildCeleryWorkerArgs("heavy_analysis");
  const queueIndex = args.indexOf("-Q");
  const hostnameIndex = args.indexOf("--hostname");
  assert.notEqual(queueIndex, -1);
  assert.notEqual(hostnameIndex, -1);
  assert.equal(args[hostnameIndex + 1], "site-audit.heavy_analysis@%h");
  assert.equal(args[queueIndex + 1], "audits.heavy_analysis");
});
test("buildCeleryWorkerArgs preserves platform-specific execution settings", () => {
  const args = buildCeleryWorkerArgs("cpu_ml");
  if (os.platform() === "win32") {
    assert.match(args.join(" "), /--pool=solo/);
    assert.equal(args.includes("--concurrency"), false);
  } else {
    assert.equal(args.includes("--pool=solo"), false);
    assert.match(args.join(" "), /--concurrency 2/);
  }
});
