import assert from "node:assert/strict";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import { createSiteContentReport, extractAssetPaths, REQUIRED_BUNDLE_FRAGMENTS } from "./site-content-check.mjs";

function createFixtureRoot(name) {
  const root = path.join(process.cwd(), "scripts", `.tmp-${name}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  mkdirSync(path.join(root, "frontend", "dist", "assets"), { recursive: true });
  return root;
}

function writeValidFixture(root) {
  writeFileSync(
    path.join(root, "frontend", "dist", "index.html"),
    [
      '<!doctype html><html><head><title>Site Audit Dashboard</title>',
      '<script type="module" crossorigin src="/assets/app.js"></script>',
      '<link rel="stylesheet" crossorigin href="/assets/app.css">',
      '</head><body><div id="root"></div></body></html>',
    ].join(""),
    "utf8",
  );
  writeFileSync(path.join(root, "frontend", "dist", "assets", "app.css"), ".app-shell{}", "utf8");
  writeFileSync(
    path.join(root, "frontend", "dist", "assets", "app.js"),
    REQUIRED_BUNDLE_FRAGMENTS.map((fragment) => `console.log(${JSON.stringify(fragment)});`).join("\n"),
    "utf8",
  );
}

test("extractAssetPaths reads JS and CSS references from index.html", () => {
  assert.deepEqual(
    extractAssetPaths('<script src="/assets/app.js"></script><link href="/assets/app.css">'),
    ["/assets/app.js", "/assets/app.css"],
  );
});

test("createSiteContentReport accepts a valid production frontend fixture", () => {
  const root = createFixtureRoot("site-check-valid");
  try {
    writeValidFixture(root);
    const report = createSiteContentReport({ rootDir: root });

    assert.equal(report.ok, true);
    assert.deepEqual(report.errors, []);
    assert.equal(report.assetCount, 2);
    assert.equal(report.jsBundleCount, 1);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("createSiteContentReport rejects a bundle without required UI content", () => {
  const root = createFixtureRoot("site-check-invalid");
  try {
    writeValidFixture(root);
    writeFileSync(path.join(root, "frontend", "dist", "assets", "app.js"), "console.log('empty');", "utf8");

    const report = createSiteContentReport({ rootDir: root });

    assert.equal(report.ok, false);
    assert.ok(report.errors.some((error) => error.includes("production bundle не содержит текст интерфейса")));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
