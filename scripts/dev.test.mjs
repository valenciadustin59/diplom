import assert from "node:assert/strict";
import os from "node:os";
import test from "node:test";
import {
  buildBackendRuntimeEnv,
  buildCeleryWorkerArgs,
  buildFrontendDevArgs,
  CELERY_AUDIT_QUEUES,
  CELERY_WORKER_PROFILES,
  resolveSemanticAutoscaleConfig,
  resolveWorkerAutoscaleConfigs,
  SEMANTIC_QUEUE_NAME,
  SEMANTIC_WORKER_PROFILE_NAME,
  WORKER_AUTOSCALE_DEFAULT_PROFILES,
} from "./dev.mjs";
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
  assert.deepEqual(CELERY_WORKER_PROFILES.map((profile) => profile.name), [
    "pipeline",
    "network",
    "heavy_analysis",
    "semantic_cpu",
    "cpu_ml",
  ]);
  assert.deepEqual([...CELERY_AUDIT_QUEUES].sort(), [
    "audits.pipeline",
    "audits.fetch",
    "audits.heavy_analysis",
    "audits.semantic",
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

test("buildCeleryWorkerArgs subscribes semantic worker only to semantic queue", () => {
  const args = buildCeleryWorkerArgs(SEMANTIC_WORKER_PROFILE_NAME);
  const queueIndex = args.indexOf("-Q");
  const hostnameIndex = args.indexOf("--hostname");
  assert.notEqual(queueIndex, -1);
  assert.notEqual(hostnameIndex, -1);
  assert.equal(args[hostnameIndex + 1], "site-audit.semantic_cpu@%h");
  assert.equal(args[queueIndex + 1], SEMANTIC_QUEUE_NAME);
});

test("buildCeleryWorkerArgs can give scaled semantic workers unique hostnames", () => {
  const args = buildCeleryWorkerArgs(SEMANTIC_WORKER_PROFILE_NAME, { hostnameSuffix: "2" });
  const hostnameIndex = args.indexOf("--hostname");
  assert.notEqual(hostnameIndex, -1);
  assert.equal(args[hostnameIndex + 1], "site-audit.semantic_cpu.2@%h");
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

test("resolveSemanticAutoscaleConfig defaults to fixed minimum semantic worker", () => {
  const config = resolveSemanticAutoscaleConfig(["node", "scripts/dev.mjs"], {});
  assert.equal(config.enabled, false);
  assert.equal(config.mode, "off");
  assert.equal(config.profileName, SEMANTIC_WORKER_PROFILE_NAME);
  assert.equal(config.queueName, SEMANTIC_QUEUE_NAME);
  assert.equal(config.minWorkers, 1);
});

test("resolveSemanticAutoscaleConfig enables auto mode from CLI and clamps max to min", () => {
  const config = resolveSemanticAutoscaleConfig(
    ["node", "scripts/dev.mjs", "--semantic-autoscale=auto"],
    {
      SEMANTIC_WORKER_MIN: "2",
      SEMANTIC_WORKER_MAX: "1",
      SEMANTIC_WORKER_SCALE_UP_DEPTH: "3",
      SEMANTIC_WORKER_SCALE_UP_WAIT_MS: "7000",
      SEMANTIC_WORKER_SCALE_DOWN_IDLE_MS: "9000",
      SEMANTIC_WORKER_POLL_INTERVAL_MS: "1100",
    },
  );
  assert.equal(config.enabled, true);
  assert.equal(config.mode, "auto");
  assert.equal(config.minWorkers, 2);
  assert.equal(config.maxWorkers, 2);
  assert.equal(config.scaleUpDepth, 3);
  assert.equal(config.scaleUpWaitMs, 7000);
  assert.equal(config.scaleDownIdleMs, 9000);
  assert.equal(config.pollIntervalMs, 1100);
});

test("resolveWorkerAutoscaleConfigs enables elastic dev workers for non-pipeline profiles", () => {
  const configs = resolveWorkerAutoscaleConfigs(["node", "scripts/dev.mjs", "--worker-autoscale=auto"], {});
  assert.deepEqual(configs.map((config) => config.profileName), WORKER_AUTOSCALE_DEFAULT_PROFILES);
  assert.equal(configs.some((config) => config.profileName === "pipeline"), false);
  const network = configs.find((config) => config.profileName === "network");
  const networkProfile = CELERY_WORKER_PROFILES.find((profile) => profile.name === "network");
  assert.ok(network);
  assert.ok(networkProfile);
  assert.deepEqual(network.queueNames, networkProfile.queues);
  assert.equal(network.minWorkers, 1);
  assert.equal(network.maxWorkers, 3);
});

test("resolveWorkerAutoscaleConfigs supports selected profiles and profile-specific limits", () => {
  const configs = resolveWorkerAutoscaleConfigs(
    ["node", "scripts/dev.mjs", "--worker-autoscale", "auto", "--worker-autoscale-profiles=network,cpu_ml"],
    {
      NETWORK_WORKER_MIN: "2",
      NETWORK_WORKER_MAX: "4",
      CPU_ML_WORKER_SCALE_UP_DEPTH: "5",
    },
  );
  assert.deepEqual(configs.map((config) => config.profileName), ["network", "cpu_ml"]);
  assert.equal(configs[0].minWorkers, 2);
  assert.equal(configs[0].maxWorkers, 4);
  assert.equal(configs[1].scaleUpDepth, 5);
});

test("resolveWorkerAutoscaleConfigs keeps pipeline as a fixed orchestration worker", () => {
  assert.throws(
    () => resolveWorkerAutoscaleConfigs(["node", "scripts/dev.mjs", "--worker-autoscale=auto", "--worker-autoscale-profiles=pipeline"], {}),
    /pipeline worker must stay fixed/,
  );
});

test("buildFrontendDevArgs binds Vite to loopback IPv4 for smoke checks", () => {
  assert.deepEqual(buildFrontendDevArgs(), ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"]);
});
