import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

export const REQUIRED_INDEX_FRAGMENTS = ["Site Audit Dashboard", '<div id="root"></div>', "/assets/"];

export const REQUIRED_BUNDLE_FRAGMENTS = [
  "Новый аудит",
  "Запустить аудит",
  "История аудитов",
  "Рабочее пространство аудита",
  "Отчёт аудита",
  "Скачать Markdown",
  "Конкуренты",
  "Рекомендации",
  "Итоговый score",
  "ML-калибровка",
];

function appendMissingFileError(filePath, label, errors, rootDir) {
  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    errors.push(`${label} не найден: ${path.relative(rootDir, filePath)}`);
    return false;
  }
  return true;
}

function readText(filePath) {
  return readFileSync(filePath, "utf8");
}

export function extractAssetPaths(indexHtml) {
  const matches = [...indexHtml.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)];
  return matches.map((match) => match[1]);
}

export function createSiteContentReport({
  rootDir = process.cwd(),
  requiredIndexFragments = REQUIRED_INDEX_FRAGMENTS,
  requiredBundleFragments = REQUIRED_BUNDLE_FRAGMENTS,
} = {}) {
  const distDir = path.join(rootDir, "frontend", "dist");
  const indexPath = path.join(distDir, "index.html");
  const assetsDir = path.join(distDir, "assets");
  const errors = [];

  if (!appendMissingFileError(indexPath, "frontend production index", errors, rootDir)) {
    return { ok: false, errors, assetCount: 0, jsBundleCount: 0 };
  }

  const indexHtml = readText(indexPath);
  for (const fragment of requiredIndexFragments) {
    if (!indexHtml.includes(fragment)) {
      errors.push(`index.html не содержит обязательный фрагмент: ${fragment}`);
    }
  }

  const assetPaths = extractAssetPaths(indexHtml);
  if (assetPaths.length === 0) {
    errors.push("index.html не подключает production assets.");
  }

  for (const assetPath of assetPaths) {
    appendMissingFileError(path.join(distDir, assetPath), `asset ${assetPath}`, errors, rootDir);
  }

  const jsAssets = existsSync(assetsDir)
    ? readdirSync(assetsDir)
        .filter((fileName) => fileName.endsWith(".js"))
        .map((fileName) => path.join(assetsDir, fileName))
    : [];

  if (jsAssets.length === 0) {
    errors.push("JS bundle не найден в frontend/dist/assets.");
    return { ok: false, errors, assetCount: assetPaths.length, jsBundleCount: 0 };
  }

  const bundleText = jsAssets.map(readText).join("\n");
  for (const fragment of requiredBundleFragments) {
    if (!bundleText.includes(fragment)) {
      errors.push(`production bundle не содержит текст интерфейса: ${fragment}`);
    }
  }

  return {
    ok: errors.length === 0,
    errors,
    assetCount: assetPaths.length,
    jsBundleCount: jsAssets.length,
  };
}

export function runSiteContentCheck({ rootDir = process.cwd(), logger = console } = {}) {
  const report = createSiteContentReport({ rootDir });
  for (const error of report.errors) {
    logger.error(`[site:check] ${error}`);
  }

  if (!report.ok) {
    return 1;
  }

  logger.log("[site:check] Production build и ключевое содержимое интерфейса проверены.");
  logger.log(`[site:check] Проверено assets: ${report.assetCount}, JS bundles: ${report.jsBundleCount}.`);
  return 0;
}

const isDirectExecution = Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectExecution) {
  process.exitCode = runSiteContentCheck();
}
