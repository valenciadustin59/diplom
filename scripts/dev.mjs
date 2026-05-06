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
export const SEMANTIC_WORKER_PROFILE_NAME = "semantic_cpu";
export const SEMANTIC_QUEUE_NAME = "audits.semantic";
export const SEMANTIC_AUTOSCALE_DEFAULTS = {
  mode: "off",
  minWorkers: 1,
  maxWorkers: 3,
  scaleUpDepth: 2,
  scaleUpWaitMs: 15000,
  scaleDownIdleMs: 60000,
  pollIntervalMs: 5000,
};
export const WORKER_AUTOSCALE_DEFAULT_PROFILES = ["network", SEMANTIC_WORKER_PROFILE_NAME, "cpu_ml"];
export const WORKER_AUTOSCALE_PROFILE_DEFAULTS = {
  network: {
    minWorkers: 1,
    maxWorkers: 3,
    scaleUpDepth: 2,
    scaleUpWaitMs: 10000,
    scaleDownIdleMs: 60000,
    pollIntervalMs: 5000,
  },
  [SEMANTIC_WORKER_PROFILE_NAME]: SEMANTIC_AUTOSCALE_DEFAULTS,
  cpu_ml: {
    minWorkers: 1,
    maxWorkers: 2,
    scaleUpDepth: 2,
    scaleUpWaitMs: 10000,
    scaleDownIdleMs: 60000,
    pollIntervalMs: 5000,
  },
};
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

function readArgValue(argv, name) {
  const prefix = `${name}=`;
  const inlineValue = argv.find((arg) => arg.startsWith(prefix));
  if (inlineValue) {
    return inlineValue.slice(prefix.length);
  }
  const index = argv.indexOf(name);
  if (index !== -1) {
    const nextValue = argv[index + 1];
    if (typeof nextValue === "string" && !nextValue.startsWith("--")) {
      return nextValue;
    }
    return "true";
  }
  return undefined;
}

function parsePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeAutoscaleMode(value) {
  const normalized = String(value ?? SEMANTIC_AUTOSCALE_DEFAULTS.mode).trim().toLowerCase();
  if (["1", "true", "yes", "on", "auto"].includes(normalized)) {
    return "auto";
  }
  if (["0", "false", "no", "off", "fixed"].includes(normalized)) {
    return "off";
  }
  return SEMANTIC_AUTOSCALE_DEFAULTS.mode;
}

function normalizeProfileEnvName(profileName) {
  return String(profileName).toUpperCase().replace(/[^A-Z0-9]+/g, "_");
}

function readProfileInteger(sourceEnv, profileName, suffix, fallback) {
  const profilePrefix = normalizeProfileEnvName(profileName);
  const legacySemanticValue =
    profileName === SEMANTIC_WORKER_PROFILE_NAME ? sourceEnv[`SEMANTIC_WORKER_${suffix}`] : undefined;
  return parsePositiveInteger(
    sourceEnv[`${profilePrefix}_WORKER_${suffix}`] ?? legacySemanticValue ?? sourceEnv[`WORKER_AUTOSCALE_${suffix}`],
    fallback,
  );
}

export function resolveSemanticAutoscaleConfig(argv = process.argv, sourceEnv = process.env) {
  const mode = normalizeAutoscaleMode(
    readArgValue(argv, "--semantic-autoscale") ?? sourceEnv.SEMANTIC_WORKER_AUTOSCALE,
  );
  const minWorkers = Math.max(
    1,
    parsePositiveInteger(sourceEnv.SEMANTIC_WORKER_MIN, SEMANTIC_AUTOSCALE_DEFAULTS.minWorkers),
  );
  const maxWorkers = Math.max(
    minWorkers,
    parsePositiveInteger(sourceEnv.SEMANTIC_WORKER_MAX, SEMANTIC_AUTOSCALE_DEFAULTS.maxWorkers),
  );
  return {
    mode,
    enabled: mode === "auto",
    profileName: SEMANTIC_WORKER_PROFILE_NAME,
    queueName: SEMANTIC_QUEUE_NAME,
    queueNames: [SEMANTIC_QUEUE_NAME],
    minWorkers,
    maxWorkers,
    scaleUpDepth: parsePositiveInteger(
      sourceEnv.SEMANTIC_WORKER_SCALE_UP_DEPTH,
      SEMANTIC_AUTOSCALE_DEFAULTS.scaleUpDepth,
    ),
    scaleUpWaitMs: parsePositiveInteger(
      sourceEnv.SEMANTIC_WORKER_SCALE_UP_WAIT_MS,
      SEMANTIC_AUTOSCALE_DEFAULTS.scaleUpWaitMs,
    ),
    scaleDownIdleMs: parsePositiveInteger(
      sourceEnv.SEMANTIC_WORKER_SCALE_DOWN_IDLE_MS,
      SEMANTIC_AUTOSCALE_DEFAULTS.scaleDownIdleMs,
    ),
    pollIntervalMs: parsePositiveInteger(
      sourceEnv.SEMANTIC_WORKER_POLL_INTERVAL_MS,
      SEMANTIC_AUTOSCALE_DEFAULTS.pollIntervalMs,
    ),
  };
}

export function resolveWorkerAutoscaleConfigs(argv = process.argv, sourceEnv = process.env) {
  const mode = normalizeAutoscaleMode(readArgValue(argv, "--worker-autoscale") ?? sourceEnv.WORKER_AUTOSCALE);
  if (mode !== "auto") {
    return [];
  }

  const selectedProfiles = [
    ...new Set(
      String(
        readArgValue(argv, "--worker-autoscale-profiles") ??
          sourceEnv.WORKER_AUTOSCALE_PROFILES ??
          WORKER_AUTOSCALE_DEFAULT_PROFILES.join(","),
      )
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];

  return selectedProfiles.map((profileName) => {
    const profile = resolveWorkerProfile(profileName);
    if (profile.name === "pipeline") {
      throw new Error("pipeline worker must stay fixed; do not autoscale the orchestration queue");
    }
    const defaults = WORKER_AUTOSCALE_PROFILE_DEFAULTS[profile.name] ?? SEMANTIC_AUTOSCALE_DEFAULTS;
    const minWorkers = Math.max(1, readProfileInteger(sourceEnv, profile.name, "MIN", defaults.minWorkers));
    const maxWorkers = Math.max(minWorkers, readProfileInteger(sourceEnv, profile.name, "MAX", defaults.maxWorkers));
    return {
      mode,
      enabled: true,
      profileName: profile.name,
      queueName: profile.queues[0],
      queueNames: profile.queues,
      minWorkers,
      maxWorkers,
      scaleUpDepth: readProfileInteger(sourceEnv, profile.name, "SCALE_UP_DEPTH", defaults.scaleUpDepth),
      scaleUpWaitMs: readProfileInteger(sourceEnv, profile.name, "SCALE_UP_WAIT_MS", defaults.scaleUpWaitMs),
      scaleDownIdleMs: readProfileInteger(sourceEnv, profile.name, "SCALE_DOWN_IDLE_MS", defaults.scaleDownIdleMs),
      pollIntervalMs: readProfileInteger(sourceEnv, profile.name, "POLL_INTERVAL_MS", defaults.pollIntervalMs),
    };
  });
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
    const childIndex = children.indexOf(child);
    if (childIndex !== -1) {
      children.splice(childIndex, 1);
    }
    if (!shuttingDown && code && code !== 0) {
      console.error(`[${name}] ╨┐╤А╨╛╤Ж╨╡╤Б╤Б ╨╖╨░╨▓╨╡╤А╤И╨╕╨╗╤Б╤П ╤Б ╨║╨╛╨┤╨╛╨╝ ${code}`);
      stopAll(code);
    }
  });
  children.push(child);
  return child;
}
export function buildCeleryWorkerArgs(profileName, options = {}) {
  const profile = resolveWorkerProfile(profileName);
  const hostnameSuffix = options.hostnameSuffix ? `.${String(options.hostnameSuffix)}` : "";
  const args = [
    "-m",
    "celery",
    "-A",
    "app.celery_app:celery_app",
    "worker",
    "--loglevel=info",
    "--hostname",
    `site-audit.${profile.name}${hostnameSuffix}@%h`,
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

function startCeleryWorker(profileName, hostnameSuffix = "") {
  const displaySuffix = hostnameSuffix ? `#${hostnameSuffix}` : "";
  return runProcess(
    `worker:${profileName}${displaySuffix}`,
    resolveBackendPython(),
    buildCeleryWorkerArgs(profileName, { hostnameSuffix }),
    backendDir,
    buildBackendRuntimeEnv(),
  );
}

function createWorkerAutoscaler(apiUrl, config) {
  const workers = new Map();
  let nextWorkerId = 1;
  let timer = null;
  let backlogSince = null;
  let idleSince = null;

  function activeWorkerEntries() {
    for (const [workerId, child] of workers.entries()) {
      if (child.exitCode !== null || child.killed) {
        workers.delete(workerId);
      }
    }
    return [...workers.entries()];
  }

  function startScaledWorker() {
    const workerId = nextWorkerId;
    nextWorkerId += 1;
    const child = startCeleryWorker(config.profileName, String(workerId));
    workers.set(workerId, child);
    child.on("exit", () => {
      workers.delete(workerId);
    });
    console.log(`[worker-autoscale:${config.profileName}] started worker ${workerId}/${config.maxWorkers}`);
  }

  function stopScaledWorker() {
    const entries = activeWorkerEntries();
    if (entries.length <= config.minWorkers) {
      return;
    }
    const [workerId, child] = entries.at(-1);
    console.log(`[worker-autoscale:${config.profileName}] stopping idle worker ${workerId}`);
    child.kill();
    workers.delete(workerId);
  }

  function ensureMinimumWorkers() {
    while (activeWorkerEntries().length < config.minWorkers) {
      startScaledWorker();
    }
  }

  async function fetchQueueSnapshot() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), Math.min(config.pollIntervalMs, 5000));
    try {
      const response = await fetch(`${apiUrl}/health/metrics`, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`health metrics returned ${response.status}`);
      }
      const payload = await response.json();
      const queues = payload?.queue_pressure?.queues ?? {};
      const snapshots = config.queueNames.map((queueName) => queues?.[queueName] ?? {});
      return {
        depth: snapshots.reduce((sum, item) => sum + Number(item.depth ?? 0), 0),
        inflight_tasks: snapshots.reduce((sum, item) => sum + Number(item.inflight_tasks ?? 0), 0),
        pressure_status: snapshots.some((item) => ["stuck", "backlogged"].includes(String(item.pressure_status ?? "")))
          ? "backlogged"
          : snapshots.some((item) => String(item.pressure_status ?? "") === "waiting")
            ? "waiting"
            : snapshots.some((item) => ["busy", "draining"].includes(String(item.pressure_status ?? "")))
              ? "busy"
              : "idle",
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  async function tick() {
    ensureMinimumWorkers();
    let snapshot;
    try {
      snapshot = await fetchQueueSnapshot();
    } catch (error) {
      console.warn(`[worker-autoscale:${config.profileName}] metrics unavailable: ${error instanceof Error ? error.message : String(error)}`);
      return;
    }

    const now = Date.now();
    const depth = Number(snapshot.depth ?? 0);
    const inflight = Number(snapshot.inflight_tasks ?? 0);
    const pressureStatus = String(snapshot.pressure_status ?? "idle");
    const workerCount = activeWorkerEntries().length;
    const hasWaitPressure = depth > 0 && ["waiting", "backlogged", "stuck"].includes(pressureStatus);
    if (hasWaitPressure && backlogSince === null) {
      backlogSince = now;
    }
    if (!hasWaitPressure) {
      backlogSince = null;
    }

    const waitedLongEnough = backlogSince !== null && now - backlogSince >= config.scaleUpWaitMs;
    if ((depth >= config.scaleUpDepth || waitedLongEnough) && workerCount < config.maxWorkers) {
      startScaledWorker();
      backlogSince = now;
      idleSince = null;
      return;
    }

    const idle = depth === 0 && inflight === 0 && !["busy", "draining"].includes(pressureStatus);
    if (idle && idleSince === null) {
      idleSince = now;
    }
    if (!idle) {
      idleSince = null;
    }
    if (idleSince !== null && now - idleSince >= config.scaleDownIdleMs) {
      stopScaledWorker();
      idleSince = now;
    }
  }

  return {
    start() {
      console.log(
        `[worker-autoscale:${config.profileName}] mode=auto queues=${config.queueNames.join(",")} min=${config.minWorkers} max=${config.maxWorkers} depth=${config.scaleUpDepth} wait_ms=${config.scaleUpWaitMs} idle_ms=${config.scaleDownIdleMs}`,
      );
      ensureMinimumWorkers();
      void tick();
      timer = setInterval(() => {
        void tick();
      }, config.pollIntervalMs);
    },
    stop() {
      if (timer !== null) {
        clearInterval(timer);
      }
      for (const [, child] of workers.entries()) {
        child.kill();
      }
      workers.clear();
    },
  };
}

function createSemanticWorkerAutoscaler(apiUrl, config) {
  return createWorkerAutoscaler(apiUrl, config);
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
  const semanticAutoscaleConfig = resolveSemanticAutoscaleConfig(process.argv, process.env);
  const workerAutoscaleConfigs = resolveWorkerAutoscaleConfigs(process.argv, process.env);
  const activeAutoscaleConfigs =
    workerAutoscaleConfigs.length > 0
      ? workerAutoscaleConfigs
      : semanticAutoscaleConfig.enabled
        ? [semanticAutoscaleConfig]
        : [];
  const autoscaledProfiles = new Set(activeAutoscaleConfigs.map((config) => config.profileName));
  console.log("╨Ч╨░╨┐╤Г╤Б╨║ backend ╨╕ frontend ╨╛╨┤╨╜╨╛╨╣ ╨║╨╛╨╝╨░╨╜╨┤╨╛╨╣...");
  console.log(`Backend API: ${apiUrl}`);
  console.log(`Celery worker topology: ${includeWorker ? CELERY_WORKER_PROFILES.map((profile) => profile.name).join(", ") : "disabled"}`);
  if (includeWorker) {
    console.log(
      activeAutoscaleConfigs.length > 0
        ? `Elastic workers: ${activeAutoscaleConfigs
            .map((config) => `${config.profileName} min=${config.minWorkers} max=${config.maxWorkers}`)
            .join("; ")}`
        : "Elastic workers: disabled",
    );
  }
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
    const workerAutoscalers = activeAutoscaleConfigs.map((config) => createWorkerAutoscaler(apiUrl, config));
    for (const profile of CELERY_WORKER_PROFILES) {
      if (autoscaledProfiles.has(profile.name)) {
        continue;
      }
      startCeleryWorker(profile.name);
    }
    for (const autoscaler of workerAutoscalers) {
      autoscaler.start();
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
