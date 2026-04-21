import assert from "node:assert/strict";
import test from "node:test";

import { buildBackendRuntimeEnv, buildCeleryWorkerArgs, CELERY_AUDIT_QUEUES } from "./dev.mjs";

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

test("buildCeleryWorkerArgs subscribes worker to all distributed audit queues", () => {
  const args = buildCeleryWorkerArgs();
  const queueIndex = args.indexOf("-Q");
  const queues = args[queueIndex + 1];

  assert.notEqual(queueIndex, -1);
  assert.equal(queues, CELERY_AUDIT_QUEUES.join(","));
  assert.match(queues, /audits\.competitor_pages/);
});
