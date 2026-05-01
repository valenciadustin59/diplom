# D40-D44 Post-Publish Model Operations Backlog

This file is the local source of truth for the active post-D39 backlog. GitHub issues may be inaccessible to other Codex chats without authenticated access, so the tasks are mirrored here.

## Context

D38 published the D37 `pointwise_catboost` candidate as the active runtime artifact at `backend/artifacts/page_quality_model.pkl`. D39 added `GET /health/model` and product UI visibility for the active model in the stack page, score explanation and audit report/export. The next wave should not repeat the CatBoost rollout. It should make the published model observable, safer to operate, and easier to validate in the product.

## Active Issues

- `D40` / GitHub `#59` — open: post-publish model monitoring dashboard.
- `D41` / GitHub `#60` — open: golden query replay guardrails after publish.
- `D42` / GitHub `#61` — open: score confidence and data-quality warnings in audit UX.
- `D43` / GitHub `#62` — open: model registry and rollback evidence UI.
- `D44` / GitHub `#63` — open: second-pass competitor-aware score experiment with SERP-relative features.

## D40: Post-Publish Model Monitoring Dashboard

Goal: add post-publish monitoring for the active CatBoost v3 runtime model so the product can answer which model is serving audits, how many audits it handled, whether scores look stable, and whether runtime quality is drifting after D38/D39.

Scope:

- Build a backend view/model that aggregates recent audits by runtime model metadata from `score_breakdown.model_info`.
- Add model usage counters: audits by model artifact, schema version, status, date window and failure/warning count.
- Add score distribution metrics: average, min/max, p25/p50/p75, low-score count and high-score count for the active model.
- Add competitor coverage metrics: competitors found/analyzed/failed, grouped by model artifact where possible.
- Add a frontend monitoring card or section in the existing `Стек`/runtime area, reusing the D39 model status card rather than creating a separate admin app.
- Keep this informational only: no automatic rollback and no scoring behavior changes.

Acceptance:

- Product UI shows active model usage over recent audits, not only static artifact metadata.
- Empty state is clear when no completed audits have model metadata.
- Old audits without `model_info` do not break the dashboard and are counted separately as legacy/unknown.
- Tests cover aggregation logic and UI rendering.
- Helper docs are updated with D40 evidence after implementation.

## D41: Golden Query Replay Guardrails After Publish

Goal: create a reproducible post-publish replay workflow that reruns a fixed golden query set against the current runtime model and compares evidence with rollback/reference expectations.

Scope:

- Define a small golden query catalog that represents product domains already used in project evidence.
- Add a script that can run replay audits or evaluate stored snapshots without mutating production artifacts.
- Record for each replay item: query, target URL, selected model metadata, score, competitor counts, recommendations count, runtime status and failure context.
- Compare current model evidence against rollback/reference metadata where available.
- Produce JSON and Markdown reports under `backend/artifacts/ranking-benchmarks/` or `output/runtime-smoke/` with clear pass/warn/fail guardrails.
- Do not publish or roll back a model in this task.

Acceptance:

- A single command produces a deterministic replay report from the configured golden set.
- The report includes model artifact/schema/dataset metadata from D39.
- Guardrails include at least: no audit failures, competitor coverage threshold, score boundedness, recommendation availability and model metadata presence.
- The workflow is documented in helper files so another Codex chat can rerun it.
- Tests cover report building and guardrail decision logic without requiring live network by default.

## D42: Score Confidence And Data-Quality Warnings In Audit UX

Goal: make the audit result easier to trust by showing confidence/data-quality context for the score: whether the score is based on complete enough data, whether competitor coverage is sufficient, and whether fetch/model metadata is reliable.

Scope:

- Build a confidence view model from existing data: fetch status, feature schema, heavy analysis presence, competitor coverage, recommendation availability, model metadata presence and warnings/failure context.
- Add backend or frontend pure helpers to classify confidence as high/medium/low/unknown.
- Show confidence in overview/report without overwhelming the score card.
- Add clear warning copy for cases such as: no competitors analyzed, target fetch fallback, missing model metadata, incomplete recommendations and legacy audit.
- Include confidence in report/export where useful.
- No changes to the numeric score formula in this task.

Acceptance:

- Completed audits show a compact score confidence label and reason list.
- Failed/processing/legacy audits degrade gracefully.
- Long warning text does not break layout on narrow resolutions.
- Tests cover confidence classification and key UI states.
- Helper docs explain that D42 is a UX/reliability layer, not retraining.

## D43: Model Registry And Rollback Evidence UI

Goal: turn D38/D39 model metadata into a small product-facing model registry/history view: current model, previous rollback artifact, publish decision and evidence links/metadata in one place.

Scope:

- Extend model status payload or add a registry endpoint that lists current and known versioned artifacts from `backend/artifacts/versions/` plus public metadata sidecars.
- Surface current artifact, rollback artifact, dataset, schema, SHA1, publish decision, smoke evidence path and report path where available.
- Add a UI section under `Стек` for model release history / rollback evidence.
- Provide a rollback dry-run/checklist view only; do not execute rollback from UI.
- Include guardrails that warn if rollback metadata file or SHA1 is missing.

Acceptance:

- UI shows current CatBoost v3 and previous v1 RandomForest rollback artifact as separate records when metadata is present.
- Missing metadata is represented as a warning, not a crash.
- Backend tests cover artifact discovery and metadata normalization.
- Frontend tests cover rendering current/rollback records and narrow-layout behavior.
- Docs clarify that actual rollback remains a controlled engineering operation.

## D44: Second-Pass Competitor-Aware Score Experiment With SERP-Relative Features

Goal: prototype a controlled second-pass scoring experiment that can use the existing `serp_relative` features after competitor aggregation, without replacing the D38 production score by default.

Scope:

- Design a two-stage scoring contract: primary score remains available early; optional second-pass score is computed after competitor aggregation.
- Build dataset/evaluation evidence for using `serp_relative` features without query leakage.
- Train or simulate a non-production second-pass candidate and compare it against the current CatBoost v3 primary model.
- Add guardrails focused on product behavior: top-3, NDCG, MAE, score stability, recommendation consistency and no regression in audits with weak competitor coverage.
- Store candidate/report artifacts separately; do not replace `backend/artifacts/page_quality_model.pkl` in D44.
- Decide at the end whether second-pass scoring is worth a later D45+ publish task.

Acceptance:

- D44 produces a report explaining whether competitor-aware second-pass scoring helps enough to continue.
- Existing primary score path remains unchanged and tested.
- Audits with missing/failed competitors still have a valid primary score.
- Candidate artifacts are clearly marked non-production.
- Docs state that D44 is an experiment/evidence task, not a production rollout.

## Implementation Order

Implement D40 first because monitoring gives the product a baseline after D38/D39. D41 should follow because replay guardrails make future model changes reproducible. D42 then improves user trust in individual audit results. D43 makes release/rollback evidence visible. D44 is deliberately last because it is a modeling experiment and should benefit from the monitoring/replay/confidence context created by D40-D43.

## Current Status

- [x] (2026-05-02) GitHub issues `#59-#63` created for D40-D44.
- [x] (2026-05-02) Local backlog mirror created in this file.
- [ ] D40 implementation.
- [ ] D41 implementation.
- [ ] D42 implementation.
- [ ] D43 implementation.
- [ ] D44 implementation.
