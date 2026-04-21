import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const rootDir = process.cwd();
const backendDir = path.join(rootDir, "backend");
const frontendDir = path.join(rootDir, "frontend");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const includeWorker = process.argv.includes("--with-worker");

const children = [];
let shuttingDown = false;

export function buildBackendRuntimeEnv(extraEnv = {}, sourceEnv = process.env) {
  return {
    SERP_PROVIDER: sourceEnv.SERP_PROVIDER ?? "searxng",
    SEARXNG_BASE_URL: sourceEnv.SEARXNG_BASE_URL ?? "http://127.0.0.1:8888",
    SEARXNG_LANGUAGE: sourceEnv.SEARXNG_LANGUAGE ?? "ru-RU",
    CELERY_BROKER_URL: sourceEnv.CELERY_BROKER_URL ?? "redis://127.0.0.1:6379/0",
    CELERY_RESULT_BACKEND: sourceEnv.CELERY_RESULT_BACKEND ?? "redis://127.0.0.1:6379/0",
    ...extraEnv,
  };
}

function resolveBackendPython() {
  const candidates = [
    path.join(backendDir, ".venv", "Scripts", "python.exe"),
    path.join(backendDir, ".venv", "bin", "python"),
  ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function isPortFree(port, host = "127.0.0.1") {
  return new Promise((resolve) => {
    const server = net.createServer();

    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });

    server.listen(port, host);
  });
}

async function findAvailablePort(startPort, host = "127.0.0.1", attempts = 20) {
  for (let offset = 0; offset < attempts; offset += 1) {
    const port = startPort + offset;
    if (await isPortFree(port, host)) {
      return port;
    }
  }

  throw new Error(`Не удалось найти свободный порт, начиная с ${startPort}.`);
}

function runProcess(name, command, args, cwd, extraEnv = {}) {
  const child = spawn(command, args, {
    cwd,
    shell: true,
    env: { ...process.env, ...extraEnv },
  });

  child.stdout.on("data", (chunk) => {
    process.stdout.write(`[${name}] ${chunk}`);
  });

  child.stderr.on("data", (chunk) => {
    process.stderr.write(`[${name}] ${chunk}`);
  });

  child.on("exit", (code) => {
    if (!shuttingDown && code && code !== 0) {
      console.error(`[${name}] процесс завершился с кодом ${code}`);
      stopAll(code);
    }
  });

  children.push(child);
}

function buildCeleryWorkerArgs() {
  const args = ["-m", "celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=info", "-Q", "audits"];

  // Celery on Windows is most reliable in local development with the solo pool.
  if (process.platform === "win32") {
    args.push("--pool=solo");
  }

  return args;
}

function stopAll(code = 0) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;

  for (const child of children) {
    if (!child.killed) {
      child.kill();
    }
  }

  process.exit(code);
}

async function main() {
  const backendPort = await findAvailablePort(8000);
  const apiUrl = `http://127.0.0.1:${backendPort}`;

  console.log("Запуск backend и frontend одной командой...");
  console.log(`Backend API: ${apiUrl}`);
  console.log(`Celery worker: ${includeWorker ? "enabled" : "disabled"}`);

  runProcess(
    "backend",
    resolveBackendPython(),
    ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", String(backendPort)],
    backendDir,
    buildBackendRuntimeEnv({ BACKEND_PORT: String(backendPort) }),
  );

  runProcess("frontend", npmCommand, ["run", "dev"], frontendDir, {
    VITE_API_URL: apiUrl,
  });

  if (includeWorker) {
    runProcess("worker", resolveBackendPython(), buildCeleryWorkerArgs(), backendDir, buildBackendRuntimeEnv());
  }

  process.on("SIGINT", () => stopAll(0));
  process.on("SIGTERM", () => stopAll(0));
}

const isDirectExecution = Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectExecution) {
  main().catch((error) => {
    console.error(`[dev] ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  });
}
