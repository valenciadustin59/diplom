# D39 Model Status In Interface

Local source of truth for GitHub issue `#58`: `D39: Model status in interface`.

## Goal

After D38 published CatBoost v3, the product needs visible model transparency. Users and future Codex agents should not infer the active runtime model only from completed audit internals or artifact files; the interface should show which model is currently serving score calculations.

## Scope

- [x] Create a backend model-status health endpoint.
- [x] Show active model status in the stack/readiness interface.
- [x] Show per-audit model metadata in score explanation when `score_breakdown.model_info` exists.
- [x] Include model metadata in the audit report and exported report builders.
- [x] Keep D39 informational only: no model publish, rollback or scoring behavior changes.
- [x] Add regression tests and production bundle smoke fragments.

## Implementation

Backend:

- Added `GET /health/model`.
- Added `backend/app/model_status.py`.
- The endpoint reads the current `backend/artifacts/page_quality_model.pkl` alias and public sidecar metadata from `backend/artifacts/page_quality_model.metadata.json`.
- The payload includes:
  - runtime status: `active`, `fallback` or `error`;
  - model type, schema version, feature count, artifact version and publish time;
  - dataset version and dataset coverage counts;
  - key metrics summary (`top_3_hit_rate`, `ndcg_at_10`, `mae`);
  - publish decision context from D38 metadata;
  - rollback availability and rollback hash.

Frontend:

- `runtimeApi.getModelStatus()` requests `/health/model`.
- `useRuntimeHealth()` loads model status together with live/ready/metrics diagnostics.
- `RuntimeStatusCompactCard` now shows a compact active-model strip.
- Full stack screen now has an `Активная ML-модель` card with artifact, dataset, features, metrics, publish decision and rollback availability.
- `AuditWorkspace` score breakdown now shows the model that produced the stored score for that audit.
- `AuditReportPage`, Markdown export and HTML export now include model status when audit score breakdown contains model metadata.

## Current D39 Evidence

- Active runtime model detected by `build_model_status_payload()`:
  - status: `active`;
  - model: `CatBoostRegressor`;
  - schema: `v3`;
  - dataset: `dataset-v3-d37`;
  - rollback: available.
- Backend regression: `backend/tests/test_health_api.py` passed with `24 passed`.
- Frontend regression: `npm --prefix frontend run test` passed with `45 passed`.

## Non-Goals

- D39 does not publish another model.
- D39 does not change scoring weights, feature extraction, dataset labels or worker topology.
- D39 does not add automatic rollback controls to the UI; it only shows rollback evidence.
