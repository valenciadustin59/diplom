import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";
const rootDir = process.cwd();
const backendDir = path.join(rootDir, "backend");
const frontendDir = path.join(rootDir, "frontend");
const workerTopologyProfilesPath = path.join(backendDir, "app", "worker_topology_profiles.json");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const includeWorker = process.argv.includes("--with-worker");
const frontendHost = "127.0.0.1";
const frontendPort = Number(process.env.FRONTEND_PORT ?? 5173);
const rawWorkerTopology = JSON.parse(readFileSync(workerTopologyProfilesPath, "utf8"));
export const CELERY_WORKER_PROFILES = rawWorkerTopology.profiles.map((profile) => ({
  name: String(profile.name),
  workloadClass: String(profile.workload_class),
  description: String(profile.description),
  recommendedConcurrency: Math.max(Number(profile.recommended_concurrency ?? 1), 1),
  queues: [...new Set((profile.queues ?? []).map((queueName) => String(queueName)))].sort(),
}));
export const CELERY_AUDIT_QUEUES = [...new Set(CELERY_WORKER_PROFILES.flatMap((profile) => profile.queues))];
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
function resolveWorkerProfile(profileName) {
  const profile = CELERY_WORKER_PROFILES.find((item) => item.name === profileName);
  if (!profile) {
    throw new Error(`╨Э╨╡╨╕╨╖╨▓╨╡╤Б╤В╨╜╤Л╨╣ worker topology profile: ${profileName}`);
  }
  return profile;
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
  throw new Error(`╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╜╨░╨╣╤В╨╕ ╤Б╨▓╨╛╨▒╨╛╨┤╨╜╤Л╨╣ ╨┐╨╛╤А╤В, ╨╜╨░╤З╨╕╨╜╨░╤П ╤Б ${startPort}.`);
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
      console.error(`[${name}] ╨┐╤А╨╛╤Ж╨╡╤Б╤Б ╨╖╨░╨▓╨╡╤А╤И╨╕╨╗╤Б╤П ╤Б ╨║╨╛╨┤╨╛╨╝ ${code}`);
      stopAll(code);
    }
  });
  children.push(child);
}
export function buildCeleryWorkerArgs(profileName) {
  const profile = resolveWorkerProfile(profileName);
  const args = [
    "-m",
    "celery",
    "-A",
    "app.celery_app:celery_app",
    "worker",
    "--loglevel=info",
    "--hostname",
    `site-audit.${profile.name}@%h`,
    "-Q",
    profile.queues.join(","),
  ];
  if (process.platform !== "win32") {
    args.push("--concurrency", String(profile.recommendedConcurrency));
  }
  // Celery on Windows is most reliable in local development with the solo pool.
  if (process.platform === "win32") {
    args.push("--pool=solo");
  }
  return args;
}

export function buildFrontendDevArgs(port = 5173, host = "127.0.0.1") {
  return ["run", "dev", "--", "--host", host, "--port", String(port), "--strictPort"];
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
  if (!(await isPortFree(frontendPort, frontendHost))) {
    throw new Error(
      `Frontend port ${frontendHost}:${frontendPort} is already in use. Stop the old dev server before running npm run dev:full.`,
    );
  }

  const backendPort = await findAvailablePort(8000);
  const apiUrl = `http://127.0.0.1:${backendPort}`;
  console.log("╨Ч╨░╨┐╤Г╤Б╨║ backend ╨╕ frontend ╨╛╨┤╨╜╨╛╨╣ ╨║╨╛╨╝╨░╨╜╨┤╨╛╨╣...");
  console.log(`Backend API: ${apiUrl}`);
  console.log(`Celery worker topology: ${includeWorker ? CELERY_WORKER_PROFILES.map((profile) => profile.name).join(", ") : "disabled"}`);
  runProcess(
    "backend",
    resolveBackendPython(),
    ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", String(backendPort)],
    backendDir,
    buildBackendRuntimeEnv({ BACKEND_PORT: String(backendPort) }),
  );
  runProcess("frontend", npmCommand, buildFrontendDevArgs(frontendPort, frontendHost), frontendDir, {
    VITE_API_URL: apiUrl,
  });
  if (includeWorker) {
    for (const profile of CELERY_WORKER_PROFILES) {
      runProcess(
        `worker:${profile.name}`,
        resolveBackendPython(),
        buildCeleryWorkerArgs(profile.name),
        backendDir,
        buildBackendRuntimeEnv(),
      );
    }
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
