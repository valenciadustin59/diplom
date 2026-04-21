import process from "node:process";
import { pathToFileURL } from "node:url";

export function createHealthcheckConfig(sourceEnv = process.env) {
  const baseUrl = (sourceEnv.SEARXNG_BASE_URL || "http://127.0.0.1:8888").replace(/\/$/, "");

  return {
    baseUrl,
    url: `${baseUrl}/search?q=test&format=json`,
    maxAttempts: Number(sourceEnv.SEARXNG_HEALTHCHECK_ATTEMPTS || 15),
    delayMs: Number(sourceEnv.SEARXNG_HEALTHCHECK_DELAY_MS || 2000),
  };
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export async function checkOnce({
  fetchImpl = fetch,
  config = createHealthcheckConfig(),
} = {}) {
  const response = await fetchImpl(config.url, {
    headers: {
      accept: "application/json",
      "user-agent": "diplom-healthcheck/1.0",
    },
  });

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`HTTP ${response.status}: ${body.slice(0, 200)}`);
  }

  if (!contentType.includes("json")) {
    const body = await response.text();
    throw new Error(`Expected JSON, got '${contentType}'. Body: ${body.slice(0, 200)}`);
  }

  const payload = await response.json();
  const results = Array.isArray(payload.results) ? payload.results : [];

  return {
    status: "ok",
    baseUrl: config.baseUrl,
    resultsCount: results.length,
  };
}

export async function checkWithRetry({
  fetchImpl = fetch,
  sleepImpl = sleep,
  config = createHealthcheckConfig(),
} = {}) {
  let lastError = null;

  for (let attempt = 1; attempt <= config.maxAttempts; attempt += 1) {
    try {
      const result = await checkOnce({ fetchImpl, config });
      return {
        ...result,
        attemptsUsed: attempt,
      };
    } catch (error) {
      lastError = error;

      if (attempt < config.maxAttempts) {
        await sleepImpl(config.delayMs);
      }
    }
  }

  throw (lastError instanceof Error ? lastError : new Error(String(lastError)));
}

async function main() {
  const config = createHealthcheckConfig();

  try {
    const result = await checkWithRetry({ config });
    console.log(JSON.stringify(result, null, 2));
    return;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const hint =
      config.baseUrl === "http://127.0.0.1:8888"
        ? "Проверьте, что локальный SearxNG поднят через npm run searxng:up."
        : "Проверьте, что указанный SearxNG instance доступен и возвращает format=json.";

    console.error(
      JSON.stringify(
        {
          status: "error",
          baseUrl: config.baseUrl,
          message,
          attemptsUsed: config.maxAttempts,
          hint,
        },
        null,
        2,
      ),
    );
    process.exit(1);
  }
}

const isDirectExecution = Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectExecution) {
  main();
}
