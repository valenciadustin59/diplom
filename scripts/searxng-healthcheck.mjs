const baseUrl = (process.env.SEARXNG_BASE_URL || "http://127.0.0.1:8888").replace(/\/$/, "");
const url = `${baseUrl}/search?q=test&format=json`;

async function main() {
  try {
    const response = await fetch(url, {
      headers: {
        "accept": "application/json",
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
    console.log(
      JSON.stringify(
        {
          status: "ok",
          baseUrl,
          resultsCount: results.length,
        },
        null,
        2,
      ),
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const hint =
      baseUrl === "http://127.0.0.1:8888"
        ? "Проверьте, что локальный SearxNG поднят через npm run searxng:up."
        : "Проверьте, что указанный SearxNG instance доступен и возвращает format=json.";
    console.error(
      JSON.stringify(
        {
          status: "error",
          baseUrl,
          message,
          hint,
        },
        null,
        2,
      ),
    );
    process.exit(1);
  }
}

main();
