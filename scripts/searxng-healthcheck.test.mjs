import assert from "node:assert/strict";
import test from "node:test";

import { checkWithRetry, createHealthcheckConfig } from "./searxng-healthcheck.mjs";

test("checkWithRetry retries until SearxNG becomes ready", async () => {
  let attempts = 0;
  const observedSleeps = [];
  const config = createHealthcheckConfig({
    SEARXNG_BASE_URL: "http://127.0.0.1:8888",
    SEARXNG_HEALTHCHECK_ATTEMPTS: "4",
    SEARXNG_HEALTHCHECK_DELAY_MS: "5",
  });

  const result = await checkWithRetry({
    config,
    sleepImpl: async (delayMs) => {
      observedSleeps.push(delayMs);
    },
    fetchImpl: async () => {
      attempts += 1;
      if (attempts < 3) {
        throw new Error("fetch failed");
      }

      return {
        ok: true,
        headers: {
          get(name) {
            return name === "content-type" ? "text/plain" : null;
          },
        },
        async text() {
          return "OK";
        },
      };
    },
  });

  assert.equal(result.status, "ok");
  assert.equal(result.baseUrl, "http://127.0.0.1:8888");
  assert.equal(result.healthEndpoint, "http://127.0.0.1:8888/healthz");
  assert.equal(result.attemptsUsed, 3);
  assert.deepEqual(observedSleeps, [5, 5]);
});
