import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const action = process.argv[2] || "up";
const rootDir = process.cwd();
const composeFile = path.join(rootDir, "docker-compose.searxng.yml");

function resolveDockerCommand() {
  const candidates = [
    "docker",
    "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe",
  ];

  for (const candidate of candidates) {
    if (candidate === "docker") {
      const probe = spawnSync(candidate, ["--version"], {
        cwd: rootDir,
        encoding: "utf-8",
        shell: false,
        stdio: "pipe",
      });
      if (probe.status === 0) {
        return candidate;
      }
      continue;
    }

    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return "docker";
}

const dockerCommand = resolveDockerCommand();

function run(command, args) {
  return spawnSync(command, args, {
    cwd: rootDir,
    encoding: "utf-8",
    shell: false,
    stdio: "pipe",
  });
}

const dockerVersion = run(dockerCommand, ["--version"]);
if (dockerVersion.status !== 0) {
  console.error(
    JSON.stringify(
      {
        status: "error",
        action,
        message:
          "Docker не найден. Установите Docker Desktop и снова запустите npm run searxng:up.",
      },
      null,
      2,
    ),
  );
  process.exit(1);
}

const argsByAction = {
  up: ["compose", "-f", composeFile, "up", "-d"],
  down: ["compose", "-f", composeFile, "down"],
  logs: ["compose", "-f", composeFile, "logs", "-f", "searxng"],
};

const args = argsByAction[action];
if (!args) {
  console.error(
    JSON.stringify(
      {
        status: "error",
        action,
        message: "Unsupported action. Use up, down or logs.",
      },
      null,
      2,
    ),
  );
  process.exit(1);
}

const result = run(dockerCommand, args);
if (result.stdout) {
  process.stdout.write(result.stdout);
}
if (result.stderr) {
  process.stderr.write(result.stderr);
}
process.exit(result.status ?? 0);
